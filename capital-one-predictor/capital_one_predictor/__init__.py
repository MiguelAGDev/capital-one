"""Motor de pronóstico de flujo de caja para Capital PyMe.

API pública que consume el backend:

    from capital_one_predictor import get_state, get_forecast, lapso_index

Ver README.md para la arquitectura (motor diario + motor mensual anclado al
índice real de INEGI/FRED) y `research/` para la evidencia de por qué se
diseñó así.
"""

from .chart import render_liquidity_svg
from .daily_model import FORECAST_HORIZON_DAYS, get_forecast, get_state, lapso_index

__all__ = [
    "get_state", "get_forecast", "lapso_index", "FORECAST_HORIZON_DAYS",
    "render_liquidity_svg",
]
