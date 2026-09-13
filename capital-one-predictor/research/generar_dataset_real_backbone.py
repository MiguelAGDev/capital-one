"""
Genera un dataset MENSUAL (nunca diario -- se elimina ese paso a proposito)
para N PyMEs sinteticas, usando como "columna vertebral" de tendencia y
estacionalidad el indice REAL de ventas al por menor de Mexico (INEGI via
FRED, ver README.md). Cada PyME es una version escalada + ruidosa de ese
mismo patron real, no un patron inventado por negocio como en las pruebas
anteriores.

Salida: dataset_real_backbone.csv -- una fila por (PyME, mes).
"""

from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).parent
INDEX_CSV = BASE_DIR / "mexico_retail_index_fred.csv"
OUT_PATH = BASE_DIR / "dataset_real_backbone.csv"

SEED = 42
N_PYMES = 50                 # mas PyMEs (eran 20, luego 30)
WINDOW_MONTHS = 447          # TODO el historico real disponible (~37 anios, 1986-2023)
SCALE_MIN, SCALE_MAX = 0.5, 2.0

IDIO_PERSISTENCE = 0.6       # momentum idiosincratico por negocio (mas chico que antes:
                              # ahora la mayor parte de la tendencia/estacionalidad viene del indice real)
IDIO_SHOCK_STD = 0.05
MICRO_NOISE_STD = 0.03


def load_index() -> pd.DataFrame:
    idx = pd.read_csv(INDEX_CSV, parse_dates=["observation_date"])
    idx = idx.rename(columns={"observation_date": "date", "MEXSLRTTO01IXOBM": "index_value"})
    idx = idx.dropna().sort_values("date").reset_index(drop=True)
    idx = idx.tail(WINDOW_MONTHS).reset_index(drop=True)
    idx["index_norm"] = idx["index_value"] / idx["index_value"].iloc[0]
    return idx


def simulate_one_pyme(customer_id: str, scale: float, idx_norm: np.ndarray, rng: np.random.Generator) -> pd.DataFrame:
    n = len(idx_norm)

    idio = np.zeros(n)
    prev = 0.0
    for t in range(n):
        shock = rng.normal(0, IDIO_SHOCK_STD)
        prev = IDIO_PERSISTENCE * prev + shock
        idio[t] = prev
    idio_mult = 1 + idio
    micro_noise = 1 + rng.normal(0, MICRO_NOISE_STD, size=n)

    base_monthly_sales = rng.uniform(100_000, 400_000) * scale
    total_deposits = base_monthly_sales * idx_norm * idio_mult * micro_noise
    total_deposits = np.maximum(total_deposits, 0)

    purchase_ratio = rng.uniform(0.35, 0.55)
    total_purchases = total_deposits * purchase_ratio * (1 + rng.normal(0, 0.04, size=n))
    total_purchases = np.maximum(total_purchases, 0)

    bills_base = rng.uniform(9000, 14000) * scale
    bills_amount = bills_base * (1 + rng.normal(0, 0.03, size=n)) * (idx_norm ** 0.2)
    bills_amount = np.maximum(bills_amount, 0)

    net_flow = total_deposits - total_purchases - bills_amount

    return pd.DataFrame({"customer_id": customer_id, "total_deposits": total_deposits.round(2),
                          "total_purchases": total_purchases.round(2), "bills_amount": bills_amount.round(2),
                          "net_flow": net_flow.round(2)})


def main():
    idx = load_index()
    rng = np.random.default_rng(SEED)
    scales = rng.uniform(SCALE_MIN, SCALE_MAX, size=N_PYMES)

    frames = []
    print(f"Backbone real: {idx['date'].min().date()} a {idx['date'].max().date()} ({len(idx)} meses)")
    print(f"Generando {N_PYMES} PyMEs mensuales sobre ese backbone real...")
    for i in range(N_PYMES):
        customer_id = f"pyme_{i + 1:02d}"
        scale = float(scales[i])
        df_i = simulate_one_pyme(customer_id, scale, idx["index_norm"].to_numpy(), rng)
        df_i["date"] = idx["date"].values
        df_i["month"] = idx["date"].dt.month.values
        df_i["year"] = idx["date"].dt.year.values
        frames.append(df_i)

    full = pd.concat(frames, ignore_index=True)
    full = full[["customer_id", "date", "year", "month", "total_deposits", "total_purchases",
                 "bills_amount", "net_flow"]]
    full = full.sort_values(["customer_id", "date"]).reset_index(drop=True)
    full.to_csv(OUT_PATH, index=False)
    print(f"Escrito {OUT_PATH} ({len(full)} filas = {N_PYMES} PyMEs x {len(idx)} meses)")
    print(f"net_flow mensual: min={full['net_flow'].min():.0f}  mean={full['net_flow'].mean():.0f}  max={full['net_flow'].max():.0f}")


if __name__ == "__main__":
    main()
