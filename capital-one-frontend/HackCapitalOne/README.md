# Capital PyMe - Frontend

Dashboard en React + Vite + Tailwind. Consume la API del backend
(`../../capital-one-backend`) a través del cliente en
[src/services/api.js](src/services/api.js):

- `getPredicciones()` → calendario del mes (real vs. proyección).
- `getKpis()` → tarjetas de liquidez, proyección a 30 días y reserva sugerida.
- `getRecomendaciones()` → recomendaciones por lapso del mes.

## Setup

```bash
npm install
npm run dev
```

En desarrollo, `vite.config.js` reenvía las rutas `/api/...` al backend en
`http://127.0.0.1:8000` (ver la sección `server.proxy`), así que **el backend
debe estar corriendo** (`uvicorn app.main:app --reload --port 8000` desde
`capital-one-backend`) antes de abrir el frontend. Sin el backend arriba, el
dashboard muestra una pantalla de error explicando cómo levantarlo.

Para apuntar a un backend en otra URL (por ejemplo en producción), define
`VITE_API_URL` en un archivo `.env`.

---

# React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.
