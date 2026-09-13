# Capital PyMe - Backend

API en FastAPI que sirve el modelo de flujo de caja consumido por el
dashboard del frontend. El modelo en sí (datos, entrenamiento, evaluación)
vive en el repo hermano **[`capital-one-predictor`](../capital-one-predictor)**
— este repo solo le da forma de API a lo que ese paquete calcula.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt   # incluye `-e ../capital-one-predictor`
```

Requiere que `../capital-one-predictor` exista como carpeta hermana (mismo
nivel que `capital-one-backend/`).

## Levantar la API

```bash
uvicorn app.main:app --reload --port 8000
```

- Docs interactivas: http://localhost:8000/docs
- El frontend (Vite) espera la API en `http://127.0.0.1:8000` y la consume vía
  el proxy `/api` configurado en `vite.config.js`.

## Endpoints

| Endpoint             | Descripción                                                                 |
|-----------------------|------------------------------------------------------------------------------|
| `GET /api/health`     | Chequeo de salud.                                                            |
| `GET /api/predicciones?year=&month=` | Días del mes con flujo neto `real` (histórico) o `proyeccion` (modelo). Sin parámetros, usa el último mes con datos. |
| `GET /api/kpis`       | Liquidez actual, proyección a 30 días y reserva sugerida.                    |
| `GET /api/recomendaciones?year=&month=` | Recomendaciones por lapso del mes (1-7, 8-15, 16-22, 23-fin), calculadas contra el promedio histórico de cada lapso. |

## Cómo funciona el modelo

Ver **[`capital-one-predictor/README.md`](../capital-one-predictor/README.md)**
para la arquitectura completa (motor diario + motor mensual anclado al
índice real de ventas al por menor de INEGI/FRED, y por qué se diseñó así).

`app/model.py` en este repo solo:

- Llama a `capital_one_predictor.get_state()` / `get_forecast()`.
- Arma el calendario día a día (`get_calendar`), los KPIs del dashboard
  (`get_kpis`) y las recomendaciones por lapso con texto/color para la UI
  (`get_recomendaciones`).

No entrena nada ni toca datos crudos — eso es responsabilidad exclusiva del
paquete `capital_one_predictor`.
