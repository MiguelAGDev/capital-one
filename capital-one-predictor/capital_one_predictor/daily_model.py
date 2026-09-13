"""Entrena el motor diario y combina su forma con el motor mensual
(`monthly_model.py`) para producir el forecast que consume el backend.

Dos motores, no uno:

1. **Motor diario** (este archivo, el original `prueba.py`): un
   `LGBMRegressor` que predice `net_flow` a partir de `day_of_week`, `month`,
   `is_weekend`, `is_holiday` y los montos del propio día -- es un modelo
   explicativo/nowcasting, no un forecast real a futuro. Le da la *forma*
   diaria: estima depósitos/compras por promedio histórico según día de la
   semana, y facturas por "bucket" (día 1, 15, 20 o fin de mes, el patrón
   quincenal de nómina/obligaciones fijas).

2. **Motor mensual** (`monthly_model.py`): agrega el histórico a meses
   calendario y predice el *total* de cada mes con lags propios más un
   factor de estacionalidad real de INEGI/FRED. Es el que se validó como
   confiable a 30+ días (ver `research/README.md` y
   `research/evaluar_modelos.py`) -- un forecast diario recursivo se desvía
   rápido, así que no se usa el motor 1 para acumular más allá de unos
   pocos días.

`get_forecast()` combina ambos: genera la forma diaria cruda con el motor 1,
y reescala el total de cada mes para que coincida con lo que predice el
motor 2.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pandas as pd
from lightgbm import LGBMRegressor, early_stopping, log_evaluation
from sklearn.metrics import mean_squared_error

from . import monthly_model

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET = BASE_DIR / "data" / "dataset_daily.csv"

TARGET = "net_flow"
FEATURES = [
    "day_of_week", "month", "is_weekend", "is_holiday",
    "total_deposits", "total_purchases", "bills_amount",
]

FORECAST_HORIZON_DAYS = 60

_state_lock = threading.Lock()
_state: dict | None = None
_forecast_cache: list[dict] | None = None


def _lgbm_params() -> dict:
    return dict(
        objective="regression",
        learning_rate=0.05,
        num_leaves=31,
        n_estimators=200,
        verbosity=-1,
    )


def lapso_index(day_of_month: int) -> int:
    """Bucket de quincena: 0 = días 1-7, 1 = 8-15, 2 = 16-22, 3 = 23-fin.
    Expuesto públicamente porque el backend lo reusa para agrupar el
    calendario en recomendaciones."""
    if day_of_month <= 7:
        return 0
    if day_of_month <= 15:
        return 1
    if day_of_month <= 22:
        return 2
    return 3


def _load_and_train() -> dict:
    df = pd.read_csv(DATASET, parse_dates=["date"])
    df = df.sort_values("date").reset_index(drop=True)

    X, y = df[FEATURES], df[TARGET]
    split_index = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split_index], X.iloc[split_index:]
    y_train, y_test = y.iloc[:split_index], y.iloc[split_index:]

    eval_model = LGBMRegressor(**_lgbm_params())
    eval_model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        eval_metric="rmse",
        callbacks=[early_stopping(20), log_evaluation(0)],
    )
    rmse = float(mean_squared_error(y_test, eval_model.predict(X_test)) ** 0.5)

    # Modelo "de producción": se reentrena con todo el histórico disponible
    # para maximizar la señal usada en la proyección hacia adelante.
    prod_model = LGBMRegressor(**_lgbm_params())
    prod_model.fit(X, y)

    deposits_by_dow = df.groupby("day_of_week")["total_deposits"].mean().to_dict()
    purchases_by_dow = df.groupby("day_of_week")["total_purchases"].mean().to_dict()

    billed = df[df["bills_amount"] > 0].copy()
    billed["bucket"] = billed["day_of_month"].apply(
        lambda d: "month_end" if d >= 28 else str(int(d))
    )
    bills_by_bucket = billed.groupby("bucket")["bills_amount"].mean().to_dict()

    df["lapso"] = df["day_of_month"].apply(lapso_index)
    df["year_month"] = df["date"].dt.to_period("M")
    hist_lapso_sums = df.groupby(["year_month", "lapso"])["net_flow"].sum().reset_index()
    lapso_baseline = hist_lapso_sums.groupby("lapso")["net_flow"].agg(["mean", "std"]).to_dict("index")

    # --- Motor mensual (ver monthly_model.py): ancla la magnitud del
    # pronóstico a 30+ días con el enfoque validado en research/. ---
    seasonal_profile = monthly_model.load_inegi_seasonal_profile()
    monthly = monthly_model.build_monthly_frame(df, seasonal_profile)
    monthly_train = monthly_model.train_monthly_model(monthly)

    return {
        "df": df,
        "model": prod_model,
        "rmse": rmse,
        "deposits_by_dow": deposits_by_dow,
        "purchases_by_dow": purchases_by_dow,
        "bills_by_bucket": bills_by_bucket,
        "lapso_baseline": lapso_baseline,
        "net_flow_std": float(df["net_flow"].std()),
        "monthly": monthly,
        "monthly_model": monthly_train["model"],
        "monthly_rmse": monthly_train["rmse"],
        "monthly_n_train": monthly_train["n_months_train"],
        "seasonal_profile": seasonal_profile,
    }


def get_state() -> dict:
    global _state
    if _state is None:
        with _state_lock:
            if _state is None:
                _state = _load_and_train()
    return _state


def _estimate_bills_amount(date: pd.Timestamp, bills_by_bucket: dict) -> float:
    dom = date.day
    last_day = date.days_in_month
    if dom == 1:
        bucket = "1"
    elif dom == 15:
        bucket = "15"
    elif dom == 20:
        bucket = "20"
    elif dom == last_day:
        bucket = "month_end"
    else:
        return 0.0
    return float(bills_by_bucket.get(bucket, 0.0))


def get_forecast(horizon: int = FORECAST_HORIZON_DAYS) -> list[dict]:
    """Proyecta `horizon` días hacia adelante desde el último día con datos reales.

    En dos pasos: (1) se genera la FORMA diaria cruda con los mismos
    patrones históricos de siempre (día de semana / bucket de facturas);
    (2) el total de cada mes calendario dentro del horizonte se reescala
    para coincidir con la predicción del motor mensual (`monthly_model.py`),
    que es el que se validó como confiable a 30+ días. El día individual
    sigue viniendo del patrón histórico -- lo que cambia es que la SUMA del
    mes ya no se acumula desde un forecast diario recursivo (que se desvía),
    sino que está anclada al modelo mensual.
    """
    global _forecast_cache
    if _forecast_cache is not None and len(_forecast_cache) >= horizon:
        return _forecast_cache[:horizon]

    state = get_state()
    df = state["df"]
    last_row = df.iloc[-1]
    last_date = last_row["date"]
    balance = float(last_row["running_balance"])

    mean_deposits = df["total_deposits"].mean()
    mean_purchases = df["total_purchases"].mean()

    # --- 1) forma diaria cruda (patrones históricos, igual que antes) ---
    raw_rows = []
    for i in range(1, horizon + 1):
        date = last_date + pd.Timedelta(days=i)
        dow = (date.weekday() + 1) % 7
        is_weekend = int(dow in (0, 6))
        deposits = float(state["deposits_by_dow"].get(dow, mean_deposits))
        purchases = float(state["purchases_by_dow"].get(dow, mean_purchases))
        bills = _estimate_bills_amount(date, state["bills_by_bucket"])
        raw_rows.append({
            "date": date, "dow": dow, "is_weekend": is_weekend,
            "deposits": deposits, "raw_net_flow": deposits - purchases - bills,
        })
    raw_df = pd.DataFrame(raw_rows)
    raw_df["year_month"] = raw_df["date"].dt.to_period("M")

    # --- 2) anclar cada mes calendario al total del motor mensual (INEGI real) ---
    n_months_needed = raw_df["year_month"].nunique()
    monthly_forecast = monthly_model.forecast_months(
        state["monthly"], state["monthly_model"], state["seasonal_profile"], n_months_needed,
    )
    monthly_target = {}
    for mf in monthly_forecast:
        period = pd.Period(mf["month_start"], freq="M")
        already_realized = float(df.loc[df["date"].dt.to_period("M") == period, "net_flow"].sum())
        monthly_target[period] = mf["net_flow"] - already_realized  # resta lo ya ocurrido si es el mes en curso

    adjusted = []
    for period, group in raw_df.groupby("year_month"):
        target = monthly_target.get(period)
        adjustment = (target - group["raw_net_flow"].sum()) if target is not None else 0.0
        weight_denom = group["deposits"].sum() or 1.0
        for _, r in group.iterrows():
            w = r["deposits"] / weight_denom
            adjusted.append({**r.to_dict(), "net_flow": r["raw_net_flow"] + adjustment * w})
    adjusted.sort(key=lambda r: r["date"])

    rows = []
    for r in adjusted:
        balance += r["net_flow"]
        rows.append({
            "date": r["date"].strftime("%Y-%m-%d"),
            "day_of_week": int(r["dow"]),
            "day_of_month": int(r["date"].day),
            "month": int(r["date"].month),
            "year": int(r["date"].year),
            "is_weekend": bool(r["is_weekend"]),
            "net_flow": round(float(r["net_flow"]), 2),
            "running_balance": round(balance, 2),
        })

    _forecast_cache = rows
    return rows[:horizon]
