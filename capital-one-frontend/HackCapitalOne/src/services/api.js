// Cliente para la API del backend (FastAPI).
//
// En desarrollo, las rutas relativas /api/... son reenviadas al backend por
// el proxy configurado en vite.config.js, así que no hace falta CORS ni
// codificar una URL absoluta. En producción se puede sobreescribir con la
// variable de entorno VITE_API_URL si el backend vive en otro dominio.
const API_BASE = import.meta.env.VITE_API_URL || '/api';

async function apiGet(path, params = {}) {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null)
  ).toString();
  const url = `${API_BASE}${path}${query ? `?${query}` : ''}`;

  let response;
  try {
    response = await fetch(url);
  } catch (err) {
    throw new Error(`No se pudo conectar con el backend (${url}): ${err.message}`);
  }

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(`Error ${response.status} en ${url}: ${detail || response.statusText}`);
  }

  return response.json();
}

/** Días del mes con su flujo neto real (histórico) o proyectado (modelo). */
export function getPredicciones({ year, month } = {}) {
  return apiGet('/predicciones', { year, month });
}

/** KPIs para las tarjetas superiores del dashboard. */
export function getKpis() {
  return apiGet('/kpis');
}

/** Recomendaciones por lapso del mes (1-7, 8-15, 16-22, 23-fin). */
export function getRecomendaciones({ year, month } = {}) {
  return apiGet('/recomendaciones', { year, month });
}

/** URL de la gráfica SVG de tendencia de liquidez (histórico + proyección),
 *  para usar directo como `src` de un <img>. */
export function getGraficaUrl({ daysHistory, daysForecast } = {}) {
  const query = new URLSearchParams(
    Object.entries({ days_history: daysHistory, days_forecast: daysForecast })
      .filter(([, v]) => v !== undefined && v !== null)
  ).toString();
  return `${API_BASE}/grafica${query ? `?${query}` : ''}`;
}
