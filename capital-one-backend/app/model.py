"""Le da forma de dashboard a lo que calcula `capital_one_predictor`
(calendario, KPIs, recomendaciones con texto/color) -- este archivo ya NO
entrena nada ni toca los datos crudos, eso vive en el repo
`capital-one-predictor` (ver su README.md para la arquitectura de los dos
motores: diario + mensual anclado al índice real de INEGI/FRED).
"""

from __future__ import annotations

import calendar as _calendar

from capital_one_predictor import get_forecast, get_state, lapso_index

_LAPSO_TITULOS = [
    "Optimización inicial y arranque de cobros",
    "Reserva oportuna para presión de nómina",
    "Auditoría de suscripciones y gastos recurrentes",
    "Fondeo de reserva fiscal oportuna",
]
_LAPSO_ACCIONES = [
    "Ver reporte de costos fijos",
    "Autorizar fondo de reserva",
    "Revisar suscripciones fijas",
    "Configurar reserva fiscal",
]
_LAPSO_BADGE = [
    "bg-emerald-100 text-emerald-800",
    "bg-red-100 text-[#D01C1F]",
    "bg-amber-100 text-amber-800",
    "bg-blue-100 text-[#0D233A]",
]


def get_calendar(year: int, month: int) -> dict:
    state = get_state()
    df = state["df"]
    last_actual_date = df["date"].max()

    actual_rows = df[(df["date"].dt.year == year) & (df["date"].dt.month == month)]
    dias = {}
    for _, r in actual_rows.iterrows():
        dias[int(r["day_of_month"])] = {
            "date": r["date"].strftime("%Y-%m-%d"),
            "day": int(r["day_of_month"]),
            "day_of_week": int(r["day_of_week"]),
            "tipo": "real",
            "net_flow": round(float(r["net_flow"]), 2),
            "running_balance": round(float(r["running_balance"]), 2),
            "is_today": r["date"] == last_actual_date,
        }

    for f in get_forecast():
        if f["year"] == year and f["month"] == month and f["day_of_month"] not in dias:
            dias[f["day_of_month"]] = {
                "date": f["date"],
                "day": f["day_of_month"],
                "day_of_week": f["day_of_week"],
                "tipo": "proyeccion",
                "net_flow": f["net_flow"],
                "running_balance": f["running_balance"],
                "is_today": False,
            }

    return {
        "year": year,
        "month": month,
        "today": last_actual_date.strftime("%Y-%m-%d"),
        "dias": [dias[d] for d in sorted(dias)],
    }


def get_kpis() -> dict:
    state = get_state()
    df = state["df"]
    last_row = df.iloc[-1]
    liquidez_actual = round(float(last_row["running_balance"]), 2)

    forecast_30 = get_forecast(30)
    proyeccion_30_dias = forecast_30[-1]["running_balance"] if forecast_30 else liquidez_actual
    net_flows_30 = [f["net_flow"] for f in forecast_30]
    min_net = min(net_flows_30) if net_flows_30 else 0

    if min_net < 0:
        reserva_sugerida = round(abs(min_net) * 1.5, 2)
    else:
        reserva_sugerida = round(1.5 * state["net_flow_std"], 2)

    variacion_pct = (
        round((proyeccion_30_dias - liquidez_actual) / liquidez_actual * 100, 2)
        if liquidez_actual else None
    )

    return {
        "liquidez_actual": liquidez_actual,
        "fecha_corte": last_row["date"].strftime("%Y-%m-%d"),
        "proyeccion_30_dias": proyeccion_30_dias,
        "variacion_pct_30_dias": variacion_pct,
        "reserva_sugerida": reserva_sugerida,
        "rmse_modelo": round(state["rmse"], 2),
        "rmse_modelo_mensual": round(state["monthly_rmse"], 2) if state["monthly_rmse"] is not None else None,
    }


def get_recomendaciones(year: int, month: int) -> list[dict]:
    calendario = get_calendar(year, month)
    baseline = get_state()["lapso_baseline"]

    last_day = _calendar.monthrange(year, month)[1]
    rangos = [
        (0, "Días 1 al 7 (Inicio de Mes)"),
        (1, "Días 8 al 15 (Mitad de Mes y Nómina)"),
        (2, "Días 16 al 22 (Recuperación y Estabilidad)"),
        (3, f"Días 23 al {last_day} (Cierre de Mes y Obligaciones)"),
    ]

    sums = {idx: 0.0 for idx, _ in rangos}
    for dia in calendario["dias"]:
        sums[lapso_index(dia["day"])] += dia["net_flow"]

    recomendaciones = []
    for idx, rango in rangos:
        current_sum = round(sums[idx], 2)
        base = baseline.get(idx, {"mean": current_sum, "std": 0})
        mean_b = base["mean"] if base["mean"] == base["mean"] else current_sum  # NaN guard
        std_b = base["std"] if base["std"] == base["std"] and base["std"] else 1.0
        z = (current_sum - mean_b) / std_b

        if current_sum < 0 or z <= -1:
            tipo = "danger"
        elif z <= -0.3:
            tipo = "warning"
        else:
            tipo = "safe"

        if tipo == "danger":
            mensaje = (
                f"Se proyecta un flujo neto de ${current_sum:,.2f} en este lapso, por debajo de tu "
                f"promedio histórico (${mean_b:,.2f}). Se recomienda separar una reserva preventiva "
                f"de ${abs(min(current_sum - mean_b, current_sum)):,.2f} antes de que termine el periodo."
            )
        elif tipo == "warning":
            mensaje = (
                f"Flujo neto proyectado de ${current_sum:,.2f}, un margen más ajustado que tu promedio "
                f"histórico (${mean_b:,.2f}) para este lapso. Vale la pena revisar gastos recurrentes."
            )
        else:
            mensaje = (
                f"Flujo neto proyectado de ${current_sum:,.2f}, en línea con tu comportamiento histórico "
                f"(${mean_b:,.2f}) para este lapso. Buen momento para reforzar tus reservas."
            )

        recomendaciones.append({
            "id": f"lapso-{idx + 1}",
            "rango": rango,
            "tipo": tipo,
            "titulo": _LAPSO_TITULOS[idx],
            "mensaje": mensaje,
            "accion": _LAPSO_ACCIONES[idx],
            "badgeColor": _LAPSO_BADGE[idx],
            "flujo_neto_proyectado": current_sum,
            "promedio_historico": round(mean_b, 2),
        })

    return recomendaciones
