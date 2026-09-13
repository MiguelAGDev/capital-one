"""Genera la gráfica de tendencia de liquidez (SVG) que consume el backend.

Se dibuja a mano (sin matplotlib/plotly) para no añadir dependencias
pesadas al paquete -- mismo criterio que ya usaba el prototipo original
(`prueba.py`) para su gráfica de real vs. predicho.

Muestra el saldo acumulado (`running_balance`): tramo histórico real (línea
sólida) empalmado con el tramo proyectado por `get_forecast()` (línea
punteada), con una marca vertical en "hoy" -- es la métrica que de verdad le
importa al dueño del negocio (ver research/README.md: error <0.2% en el
saldo acumulado, vs. ~30% en el flujo diario individual).
"""

from __future__ import annotations

import pandas as pd

from .daily_model import get_forecast, get_state

COLOR_REAL = "#0D233A"
COLOR_PROYECCION = "#D01C1F"
COLOR_GRID = "#E2E8F0"
COLOR_TEXT = "#64748B"
COLOR_BG = "#FFFFFF"


def _scale(value, low, high, start, end):
    if high == low:
        return (start + end) / 2
    return end - (value - low) / (high - low) * (end - start)


def render_liquidity_svg(
    days_history: int = 60,
    days_forecast: int = 30,
    width: int = 1200,
    height: int = 340,
) -> str:
    state = get_state()
    df = state["df"]

    hist = df.tail(days_history)[["date", "running_balance"]].copy()
    hist_points = [
        {"date": r["date"], "balance": float(r["running_balance"])}
        for _, r in hist.iterrows()
    ]

    forecast = get_forecast(days_forecast)
    forecast_points = [
        {"date": pd.to_datetime(f["date"]), "balance": f["running_balance"]}
        for f in forecast
    ]

    # Empalma el último punto real como inicio del tramo proyectado para que
    # las dos líneas se vean conectadas, sin hueco visual en "hoy".
    proyeccion_points = ([hist_points[-1]] if hist_points else []) + forecast_points
    today = hist_points[-1]["date"] if hist_points else None

    all_points = hist_points + forecast_points
    if not all_points:
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"></svg>'

    left, right = 70, width - 30
    top, bottom = 50, height - 50
    n = len(all_points)
    x_step = (right - left) / max(n - 1, 1)

    balances = [p["balance"] for p in all_points]
    minimum, maximum = min(balances), max(balances)
    pad = (maximum - minimum) * 0.1 or max(abs(maximum), 1) * 0.1

    date_to_x = {p["date"]: left + i * x_step for i, p in enumerate(all_points)}

    def to_polyline(points):
        return " ".join(
            f'{date_to_x[p["date"]]:.1f},{_scale(p["balance"], minimum - pad, maximum + pad, top, bottom):.1f}'
            for p in points
        )

    real_line = to_polyline(hist_points)
    proyeccion_line = to_polyline(proyeccion_points)

    grid_lines = []
    for frac in (0, 0.25, 0.5, 0.75, 1):
        y = top + frac * (bottom - top)
        value = maximum + pad - frac * (maximum - minimum + 2 * pad)
        grid_lines.append(
            f'<line x1="{left}" x2="{right}" y1="{y:.1f}" y2="{y:.1f}" stroke="{COLOR_GRID}" stroke-width="1"/>'
            f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" font-size="11" '
            f'font-family="sans-serif" fill="{COLOR_TEXT}">${value:,.0f}</text>'
        )

    today_x = date_to_x.get(today)
    today_marker = ""
    if today_x is not None:
        today_marker = (
            f'<line x1="{today_x:.1f}" x2="{today_x:.1f}" y1="{top}" y2="{bottom}" '
            f'stroke="{COLOR_TEXT}" stroke-width="1" stroke-dasharray="3,3"/>'
            f'<text x="{today_x:.1f}" y="{top - 12}" text-anchor="middle" font-size="11" '
            f'font-family="sans-serif" font-weight="bold" fill="{COLOR_TEXT}">HOY</text>'
        )

    def date_label(p):
        return p["date"].strftime("%d %b")

    first_label = date_label(all_points[0])
    last_label = date_label(all_points[-1])

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="{COLOR_BG}"/>
<text x="{left}" y="25" font-size="15" font-family="sans-serif" font-weight="bold" fill="{COLOR_REAL}">
  Tendencia de Liquidez -- Histórico y Proyección
</text>
{''.join(grid_lines)}
{today_marker}
<polyline points="{real_line}" fill="none" stroke="{COLOR_REAL}" stroke-width="2.5" stroke-linejoin="round"/>
<polyline points="{proyeccion_line}" fill="none" stroke="{COLOR_PROYECCION}" stroke-width="2.5"
  stroke-dasharray="6,4" stroke-linejoin="round"/>
<circle cx="{date_to_x[all_points[-1]["date"]]:.1f}" cy="{_scale(all_points[-1]["balance"], minimum - pad, maximum + pad, top, bottom):.1f}"
  r="4" fill="{COLOR_PROYECCION}"/>
<text x="{left}" y="{bottom + 30}" font-size="11" font-family="sans-serif" fill="{COLOR_TEXT}">{first_label}</text>
<text x="{right}" y="{bottom + 30}" text-anchor="end" font-size="11" font-family="sans-serif" fill="{COLOR_TEXT}">{last_label}</text>
<g transform="translate({right - 230}, 25)">
  <line x1="0" y1="-4" x2="20" y2="-4" stroke="{COLOR_REAL}" stroke-width="2.5"/>
  <text x="26" y="0" font-size="11" font-family="sans-serif" fill="{COLOR_TEXT}">Histórico real</text>
  <line x1="130" y1="-4" x2="150" y2="-4" stroke="{COLOR_PROYECCION}" stroke-width="2.5" stroke-dasharray="6,4"/>
  <text x="156" y="0" font-size="11" font-family="sans-serif" fill="{COLOR_TEXT}">Proyección (modelo)</text>
</g>
</svg>'''
    return svg
