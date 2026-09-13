"""API FastAPI que conecta el modelo de flujo de caja con el dashboard (frontend).

Ejecutar en desarrollo:
    uvicorn app.main:app --reload --port 8000

Documentación interactiva una vez levantado: http://localhost:8000/docs
"""

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from capital_one_predictor import render_liquidity_svg

from app import model

app = FastAPI(title="Capital PyMe - Liquidity Engine API", version="0.1.0")

# Orígenes del frontend en desarrollo (Vite). Se listan explícitamente en vez
# de usar "*" porque el frontend puede necesitar enviar credenciales/cookies
# en el futuro, lo cual es incompatible con allow_origins=["*"].
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/predicciones")
def predicciones(year: int | None = None, month: int | None = None):
    """Días del mes con su flujo neto: 'real' (histórico) o 'proyeccion' (modelo)."""
    state = model.get_state()
    last_date = state["df"]["date"].max()
    year = year or int(last_date.year)
    month = month or int(last_date.month)
    if not (1 <= month <= 12):
        raise HTTPException(status_code=400, detail="month debe estar entre 1 y 12")
    return model.get_calendar(year, month)


@app.get("/api/kpis")
def kpis():
    """Indicadores para las tarjetas superiores del dashboard."""
    return model.get_kpis()


@app.get("/api/recomendaciones")
def recomendaciones(year: int | None = None, month: int | None = None):
    """Recomendaciones por lapso del mes (1-7, 8-15, 16-22, 23-fin)."""
    state = model.get_state()
    last_date = state["df"]["date"].max()
    year = year or int(last_date.year)
    month = month or int(last_date.month)
    if not (1 <= month <= 12):
        raise HTTPException(status_code=400, detail="month debe estar entre 1 y 12")
    return model.get_recomendaciones(year, month)


@app.get("/api/grafica")
def grafica(days_history: int = 60, days_forecast: int = 30):
    """Gráfica SVG de tendencia de liquidez (histórico real + proyección)."""
    svg = render_liquidity_svg(days_history=days_history, days_forecast=days_forecast)
    return Response(content=svg, media_type="image/svg+xml")
