# Simulación con backbone real (INEGI vía FRED)

## Fuente de datos real

`mexico_retail_index_fred.csv` — serie **MEXSLRTTO01IXOBM**, "Sales: Retail
Trade: Total Retail Trade: Volume for Mexico", **sin ajuste estacional**,
mensual, índice 2015=100. Descargada de FRED (Federal Reserve Bank of St.
Louis): https://fred.stlouisfed.org/series/MEXSLRTTO01IXOBM

Origen último del dato: OECD Main Economic Indicators, con base en las
encuestas de comercio al por menor de **INEGI** (México). Cubre 1986-01 a
2023-03 (37+ años). Es real: incluye el crash real de ~28% de abril 2020
(COVID) y el pico real de diciembre todos los años — nada de esto está
inventado.

## Por qué se usa como "backbone"

En vez de que la tendencia y estacionalidad de las PyMEs sintéticas salgan
de una fórmula inventada (como en `simulacion_20_pymes/`), aquí el
crecimiento mes a mes de CADA PyME sigue el crecimiento REAL del sector
retail mexicano (con ruido idiosincrático propio por negocio encima). Esto
responde directamente a la pregunta de la conversación: "de dónde saco
tendencia real para más PyMEs en 10+ años" — la respuesta es esta serie.

## Qué se elimina respecto a los experimentos anteriores

Por indicación explícita: **ya no se simula a nivel diario**. Los
experimentos anteriores (`simulacion_20_pymes/`, no incluidos aquí) generaban
1826-3650 días por PyME y LUEGO agregaban a bloques de 30 días. Aquí el
dataset se genera **directamente a granularidad mensual** (una fila = un
negocio, un mes), igual que la serie real que lo alimenta.

## Resultado del barrido de modelos (`evaluar_modelos.py`, ver `resumen_evaluacion.csv`)

Con 50 PyMEs sintéticas sobre el histórico completo de INEGI (1986-2023, 37
años), evaluación one-step-ahead sobre los últimos 12 meses:

| Modelo | Error relativo |
|---|---|
| Naive (repetir mes anterior) | 14.15% |
| Naive estacional (mismo mes, año pasado) | 13.90% |
| SARIMAX log(net_flow) | 10.19% |
| LightGBM % de cambio | 9.95% |
| **LightGBM nivel absoluto (ganador)** | **9.75%** |

Ganó el nivel absoluto por márgen chico — con suficiente historia (37 años),
el problema de "los árboles no extrapolan" deja de pegar tan fuerte, porque
el modelo ya vio casi todo el rango de valores posible.

## Por qué esto vive en `research/` y no se sirve directo

Este dataset es de **50 PyMEs sintéticas**, no del cliente real. Lo que se
usa en producción (`app/monthly_model.py`) es la **técnica validada aquí**
(agregación mensual, lags propios, factor de estacionalidad real de INEGI),
aplicada al histórico real del único cliente (`dataset_daily.csv`) — no
estos datos sintéticos. Por eso el índice real de INEGI
(`mexico_retail_index_fred.csv`) también vive una copia en la raíz del
backend: ahí sí es un input real del modelo en producción.
