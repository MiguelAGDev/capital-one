"""Motor de pronostico MENSUAL con backbone real de INEGI, para el cliente
real (dataset_daily.csv, un solo negocio).

Por que existe este modulo: la comparacion de modelos en
`research/evaluar_modelos.py` (ver tambien `research/README.md`) mostro que,
para forecast a 30+ dias, el enfoque ganador es:

  - Agregar a bloques MENSUALES en vez de predecir dia por dia.
  - Target = nivel absoluto de net_flow del mes (gano la ronda final con
    suficiente historial; ver research/README.md).
  - Features: mes calendario + lags/medias del propio net_flow mensual +
    montos del mes anterior + un factor de estacionalidad REAL derivado del
    indice de ventas al por menor de INEGI (via FRED), en vez de asumir
    estacionalidad a mano.

Este modulo NO forma un calendario dia por dia -- eso lo hace
`daily_model.py`, que usa el total de cada mes que este modulo predice como
ancla y reparte ese total entre los dias con los patrones diarios de
siempre.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

BASE_DIR = Path(__file__).resolve().parent.parent
INEGI_INDEX_CSV = BASE_DIR / "data" / "mexico_retail_index_fred.csv"

MONTHLY_FEATURES = [
    "month", "inegi_seasonal_factor",
    "net_flow_lag_1", "net_flow_lag_3", "net_flow_lag_12", "net_flow_ma_3",
    "deposits_lag_1", "purchases_lag_1", "bills_lag_1",
]
MONTHLY_TARGET = "net_flow"
HOLDOUT_MONTHS = 6  # solo para reportar un RMSE honesto; el modelo de produccion se reentrena con todo


def _lgbm_params() -> dict:
    return dict(objective="regression", learning_rate=0.05, num_leaves=15,
                min_child_samples=3, n_estimators=300, verbosity=-1)


def load_inegi_seasonal_profile(path: Path = INEGI_INDEX_CSV) -> dict[int, float]:
    """Factor de estacionalidad REAL por mes (1-12): promedio historico del
    indice de ventas al por menor de INEGI para ese mes, normalizado contra
    el promedio anual. >1 = mes tipicamente fuerte (ej. diciembre), <1 = mes
    tipicamente flojo (ej. enero). No depende de que fechas exactas cubra el
    indice -- es un patron estacional, no un nivel."""
    idx = pd.read_csv(path, parse_dates=["observation_date"])
    idx = idx.rename(columns={"observation_date": "date", idx.columns[1]: "index_value"}).dropna()
    idx["month"] = idx["date"].dt.month
    by_month = idx.groupby("month")["index_value"].mean()
    factor = (by_month / idx["index_value"].mean()).to_dict()
    return {m: float(factor.get(m, 1.0)) for m in range(1, 13)}


def build_monthly_frame(df_daily: pd.DataFrame, seasonal_profile: dict[int, float]) -> pd.DataFrame:
    """Agrega el dataset diario del cliente real a meses calendario completos
    (se descarta el mes final si esta incompleto -- eso se maneja aparte en
    el forecast) y arma las features de forecast real (solo pasado)."""
    df = df_daily.copy()
    df["year_month"] = df["date"].dt.to_period("M")

    monthly = df.groupby("year_month").agg(
        total_deposits=("total_deposits", "sum"),
        total_purchases=("total_purchases", "sum"),
        bills_amount=("bills_amount", "sum"),
        net_flow=("net_flow", "sum"),
        n_days=("date", "count"),
    ).reset_index()
    monthly["month_start"] = monthly["year_month"].dt.to_timestamp()
    monthly["days_in_month"] = monthly["month_start"].dt.days_in_month
    monthly["is_complete"] = monthly["n_days"] >= monthly["days_in_month"]
    monthly["month"] = monthly["month_start"].dt.month
    monthly["inegi_seasonal_factor"] = monthly["month"].map(seasonal_profile)

    monthly["net_flow_lag_1"] = monthly["net_flow"].shift(1)
    monthly["net_flow_lag_3"] = monthly["net_flow"].shift(3)
    monthly["net_flow_lag_12"] = monthly["net_flow"].shift(12)
    monthly["net_flow_ma_3"] = monthly["net_flow"].shift(1).rolling(3).mean()
    monthly["deposits_lag_1"] = monthly["total_deposits"].shift(1)
    monthly["purchases_lag_1"] = monthly["total_purchases"].shift(1)
    monthly["bills_lag_1"] = monthly["bills_amount"].shift(1)
    return monthly


def train_monthly_model(monthly: pd.DataFrame) -> dict:
    """Entrena sobre los meses COMPLETOS (se descarta el mes final si esta a
    medias). Devuelve el modelo de produccion (entrenado con todo el
    historial) mas un RMSE honesto sobre un holdout de los ultimos
    HOLDOUT_MONTHS meses completos."""
    complete = monthly[monthly["is_complete"]].dropna(subset=["net_flow_lag_1"]).reset_index(drop=True)

    X, y = complete[MONTHLY_FEATURES], complete[MONTHLY_TARGET]
    rmse = None
    if len(complete) > HOLDOUT_MONTHS + 6:
        split = len(complete) - HOLDOUT_MONTHS
        eval_model = LGBMRegressor(**_lgbm_params())
        eval_model.fit(X.iloc[:split], y.iloc[:split])
        pred = eval_model.predict(X.iloc[split:])
        rmse = float(np.sqrt(np.mean((y.iloc[split:].to_numpy() - pred) ** 2)))

    prod_model = LGBMRegressor(**_lgbm_params())
    prod_model.fit(X, y)

    return {"model": prod_model, "rmse": rmse, "n_months_train": len(complete)}


def forecast_months(monthly: pd.DataFrame, model, seasonal_profile: dict[int, float], n_months: int) -> list[dict]:
    """Forecast recursivo mes a mes: cada mes futuro usa SOLO meses ya
    conocidos (reales o ya predichos por este mismo forecast), nunca
    informacion del propio mes que se esta prediciendo -- mismo protocolo
    validado en research/evaluar_modelos.py."""
    history = monthly[["month_start", "net_flow", "total_deposits", "total_purchases", "bills_amount"]].copy()
    # Si el ultimo mes esta incompleto, no cuenta como observacion mensual
    # cerrada para el historial de lags -- se excluye y se reconstruye aparte.
    if len(monthly) and not bool(monthly["is_complete"].iloc[-1]):
        history = history.iloc[:-1]

    net_flows = list(history["net_flow"])
    deposits = list(history["total_deposits"])
    purchases = list(history["total_purchases"])
    bills = list(history["bills_amount"])
    last_month_start = history["month_start"].iloc[-1] if len(history) else monthly["month_start"].iloc[-1]

    results = []
    for i in range(1, n_months + 1):
        target_month = (last_month_start + pd.DateOffset(months=i))
        lag1 = net_flows[-1]
        lag3 = net_flows[-3] if len(net_flows) >= 3 else np.nan
        lag12 = net_flows[-12] if len(net_flows) >= 12 else np.nan
        ma3 = float(np.mean(net_flows[-3:])) if len(net_flows) >= 3 else np.nan

        x = pd.DataFrame([{
            "month": target_month.month,
            "inegi_seasonal_factor": seasonal_profile.get(target_month.month, 1.0),
            "net_flow_lag_1": lag1, "net_flow_lag_3": lag3, "net_flow_lag_12": lag12,
            "net_flow_ma_3": ma3,
            "deposits_lag_1": deposits[-1], "purchases_lag_1": purchases[-1], "bills_lag_1": bills[-1],
        }])[MONTHLY_FEATURES]

        pred_net_flow = float(model.predict(x)[0])
        results.append({"month_start": target_month, "net_flow": pred_net_flow})

        net_flows.append(pred_net_flow)
        # Para meses mas alla del primero no conocemos deposits/purchases/bills
        # reales todavia -- se asume que siguen el promedio reciente (solo se
        # usan como features de "monto del mes anterior", no como target).
        deposits.append(deposits[-1])
        purchases.append(purchases[-1])
        bills.append(bills[-1])

    return results
