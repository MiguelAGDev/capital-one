# Capital One Predictor

Motor de pronóstico de flujo de caja para Capital PyMe — separado de
`capital-one-backend` y `capital-one-frontend` para que el ciclo de vida del
modelo (datos, entrenamiento, evaluación) no viva mezclado con el del
servicio que lo expone.

## Qué hay aquí

```
capital_one_predictor/
  daily_model.py     # motor diario (forma) + combina con el motor mensual
  monthly_model.py   # motor mensual, ancla la magnitud a 30+ días (backbone real INEGI/FRED)
data/
  dataset_daily.csv             # histórico real del único cliente (un negocio, ~5 años)
  mexico_retail_index_fred.csv  # índice real de ventas al por menor de México (INEGI, vía FRED)
research/
  ...                 # la evidencia: comparación de 5 modelos contra baselines ingenuos
                       # (ver research/README.md) que llevó a diseñar el motor mensual así
```

## Por qué dos motores

1. **Diario** (`daily_model.py`): `LGBMRegressor` explicativo/nowcasting —
   predice `net_flow` del día a partir de sus propios montos
   (depósitos/compras/facturas) más calendario. Le da la *forma* al
   calendario día a día (promedios por día de semana, "buckets" de
   facturación en los días 1/15/20/fin de mes).
2. **Mensual** (`monthly_model.py`): agrega a meses calendario y predice el
   *total* de cada mes con lags propios + un factor de estacionalidad real
   sacado del índice de INEGI. Es el que se validó como confiable a 30+ días
   (ver `research/`) — un forecast diario recursivo se desvía rápido.

`get_forecast()` combina ambos: la forma día a día viene del motor 1, pero
el total de cada mes se reescala para coincidir con el motor 2.

## Cómo lo consume el backend

```bash
# en el venv de capital-one-backend
pip install -e ../capital-one-predictor
```

```python
from capital_one_predictor import get_state, get_forecast, lapso_index
```

`capital-one-backend` solo le da forma de API (calendario, KPIs,
recomendaciones con textos/colores para el dashboard) a lo que este paquete
calcula — no entrena ni conoce los datos crudos.

## Uso directo (sin backend)

```bash
pip install -r requirements.txt
python -c "from capital_one_predictor import get_forecast; print(get_forecast(30)[:3])"
```

## `research/`

Los experimentos que llevaron a diseñar el motor mensual así (comparación
contra SARIMAX y contra un baseline ingenuo, con 50 PyMEs sintéticas sobre
el backbone real de INEGI, 37 años de historia) — ver `research/README.md`.
No se ejecutan en producción, son la evidencia de la elección.
