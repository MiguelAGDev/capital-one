"""
Barrido completo de modelos sobre el dataset con backbone real (30 PyMEs,
12 anios, mensual nativo -- sin pasar por diario). Evalua, en orden de
complejidad creciente:

  1. Naive "repetir el mes pasado"        (piso de referencia obligatorio)
  2. Naive estacional "mismo mes, anio pasado"
  3. LightGBM, target = nivel absoluto de net_flow (pool de 30 PyMEs)
  4. LightGBM, target = % de cambio vs mes anterior (pool de 30 PyMEs)
  5. SARIMAX sobre log(net_flow), estacionalidad anual, por PyME

Evaluacion: ONE-STEP-AHEAD (walk-forward) en los ultimos 12 meses -- en
cada mes de test se usa el valor REAL del mes anterior (ya conocido en la
practica una vez que ese mes ya paso), nunca la propia prediccion
encadenada. Es el mismo protocolo que se uso para comparar los
experimentos anteriores, para que los numeros sean comparables entre si.
"""

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor, early_stopping, log_evaluation
from sklearn.metrics import mean_squared_error
from statsmodels.tsa.statespace.sarimax import SARIMAX

warnings.filterwarnings("ignore")

BASE_DIR = Path(__file__).parent
DATASET = BASE_DIR / "dataset_real_backbone.csv"
N_TEST_MONTHS = 12


def rel_error(real, pred):
    real = np.asarray(real, dtype=float)
    pred = np.asarray(pred, dtype=float)
    rmse = float(np.sqrt(np.mean((real - pred) ** 2)))
    return rmse, rmse / real.mean() * 100


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["customer_id", "date"]).reset_index(drop=True)
    g = df.groupby("customer_id")["net_flow"]
    df["net_flow_lag_1"] = g.shift(1)
    df["net_flow_lag_3"] = g.shift(3)
    df["net_flow_lag_12"] = g.shift(12)
    df["net_flow_ma_3"] = g.shift(1).rolling(3).mean().reset_index(level=0, drop=True)
    df["pct_change"] = g.pct_change()
    gp = df.groupby("customer_id")["pct_change"]
    df["pct_change_lag_1"] = gp.shift(1)
    df["pct_change_lag_3"] = gp.shift(3)
    df["pct_change_ma_3"] = gp.shift(1).rolling(3).mean().reset_index(level=0, drop=True)
    df["deposits_lag_1"] = df.groupby("customer_id")["total_deposits"].shift(1)
    df["purchases_lag_1"] = df.groupby("customer_id")["total_purchases"].shift(1)
    df["bills_lag_1"] = df.groupby("customer_id")["bills_amount"].shift(1)
    return df


def main():
    df = pd.read_csv(DATASET, parse_dates=["date"])
    df = build_features(df)
    df["customer_id_cat"] = df["customer_id"].astype("category")

    n_months = df["date"].nunique()
    dates_sorted = sorted(df["date"].unique())
    split_date = dates_sorted[n_months - N_TEST_MONTHS]
    train_mask = df["date"] < split_date
    test_mask = ~train_mask

    resultados = {}

    # --- 1. Naive: repetir el mes anterior ---
    real = df.loc[test_mask, "net_flow"].to_numpy()
    pred_naive_last = df.loc[test_mask, "net_flow_lag_1"].to_numpy()
    rmse, err = rel_error(real, pred_naive_last)
    resultados["1. Naive (repetir mes anterior)"] = err
    print(f"1. Naive ultimo valor:        RMSE={rmse:,.0f}  error_relativo={err:.2f}%")

    # --- 2. Naive estacional: mismo mes, anio pasado ---
    pred_naive_season = df.loc[test_mask, "net_flow_lag_12"].to_numpy()
    rmse, err = rel_error(real, pred_naive_season)
    resultados["2. Naive estacional (mismo mes, anio pasado)"] = err
    print(f"2. Naive estacional (lag 12): RMSE={rmse:,.0f}  error_relativo={err:.2f}%")

    # --- 3. LightGBM, nivel absoluto ---
    feat_nivel = ["customer_id_cat", "month", "net_flow_lag_1", "net_flow_lag_3",
                  "net_flow_lag_12", "net_flow_ma_3", "deposits_lag_1", "purchases_lag_1", "bills_lag_1"]
    X, y = df[feat_nivel], df["net_flow"]
    model = LGBMRegressor(objective="regression", learning_rate=0.05, num_leaves=31, n_estimators=400, verbosity=-1)
    model.fit(X[train_mask], y[train_mask], eval_set=[(X[test_mask], y[test_mask])],
              eval_metric="rmse", callbacks=[early_stopping(25), log_evaluation(0)])
    pred = model.predict(X[test_mask])
    rmse, err = rel_error(real, pred)
    resultados["3. LightGBM nivel absoluto"] = err
    print(f"3. LightGBM nivel absoluto:   RMSE={rmse:,.0f}  error_relativo={err:.2f}%")

    # --- 4. LightGBM, % de cambio ---
    feat_pct = ["customer_id_cat", "month", "pct_change_lag_1", "pct_change_lag_3", "pct_change_ma_3",
                "deposits_lag_1", "purchases_lag_1", "bills_lag_1"]
    Xp, yp = df[feat_pct], df["pct_change"]
    model_pct = LGBMRegressor(objective="regression", learning_rate=0.05, num_leaves=15,
                               min_child_samples=5, n_estimators=400, verbosity=-1)
    model_pct.fit(Xp[train_mask], yp[train_mask], eval_set=[(Xp[test_mask], yp[test_mask])],
                   eval_metric="rmse", callbacks=[early_stopping(25), log_evaluation(0)])
    pct_pred = model_pct.predict(Xp[test_mask])
    net_flow_lag1_actual = df.loc[test_mask, "net_flow_lag_1"].to_numpy()
    pred_pct = net_flow_lag1_actual * (1 + pct_pred)
    rmse, err = rel_error(real, pred_pct)
    resultados["4. LightGBM % de cambio"] = err
    print(f"4. LightGBM % de cambio:      RMSE={rmse:,.0f}  error_relativo={err:.2f}%")

    df.loc[test_mask, "pred_nivel"] = pred
    df.loc[test_mask, "pred_pctchange"] = pred_pct

    # --- 5. SARIMAX log(net_flow), por PyME, estacionalidad anual ---
    sarimax_errors = []
    for customer_id, g in df.groupby("customer_id"):
        g = g.sort_values("date").reset_index(drop=True)
        y_log = np.log(g["net_flow"].astype(float))
        n = len(g)
        train_end = n - N_TEST_MONTHS
        y_train, y_test = y_log.iloc[:train_end], y_log.iloc[train_end:]
        month = g["month"]
        exog = pd.DataFrame({
            "month_sin": np.sin(2 * np.pi * month / 12), "month_cos": np.cos(2 * np.pi * month / 12),
        })
        exog_train, exog_test = exog.iloc[:train_end], exog.iloc[train_end:]
        try:
            fit = SARIMAX(y_train, exog=exog_train, order=(1, 1, 1), seasonal_order=(1, 1, 1, 12),
                           enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)
            pred_log = fit.get_forecast(steps=len(y_test), exog=exog_test).predicted_mean
            pred_sx = np.exp(pred_log.values)
        except Exception:
            pred_sx = np.full(len(y_test), np.exp(y_train.iloc[-1]))
        real_sx = np.exp(y_test.values)
        rmse_i = float(np.sqrt(np.mean((real_sx - pred_sx) ** 2)))
        sarimax_errors.append(rmse_i / real_sx.mean() * 100)
    err = float(np.mean(sarimax_errors))
    resultados["5. SARIMAX log(net_flow)"] = err
    print(f"5. SARIMAX log(net_flow):    error_relativo promedio={err:.2f}%  (mediana={np.median(sarimax_errors):.2f}%)")

    print("\n=== RESUMEN (dataset real backbone, 30 PyMEs, 12 anios, mensual nativo) ===")
    for k, v in resultados.items():
        print(f"  {k}: {v:.2f}%")

    pd.Series(resultados).to_csv(BASE_DIR / "resumen_evaluacion.csv", header=["error_relativo_pct"])
    df.to_csv(BASE_DIR / "dataset_con_predicciones.csv", index=False)


if __name__ == "__main__":
    main()
