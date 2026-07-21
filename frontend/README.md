# frontend/ — React app (Vite)

**Owner:** Role 4 (Platform & Frontend)
**Builds against:** the [`api/`](../api/README.md) gateway (JSON typed by `contracts/`)

## Purpose

The user-facing application, in two surfaces:

- **`/`** — landing page: three.js grass-globe hero, live city chips, and
  interactive teasers for attribution, forecasting, the simulator and the
  assistant.
- **`/app`** — the dashboard: full-bleed MapLibre map with the ~1 km grid as
  switchable layers (Live AQI / dominant source / forecast hour / what-if
  delta), a forecast time slider, per-cell inspection (attribution, banded
  forecast, regulation-cited recommendations), the what-if drawer and the
  grounded chat assistant with a multi-language advisory tab.

## Data (currently mocked)

`src/lib/api.js` mirrors `api/gateway.py` route-for-route and serves from
`src/lib/mock.js` (deterministic seeded data in exactly the `contracts/`
shapes). When the FastAPI gateway is live, flip `USE_MOCKS = false` there; the
Vite dev proxy already forwards `/api` to `http://localhost:8000`.

## Component areas

```
src/components/
├── landing/    Landing, GrassGlobe   — marketing page + hero 3D
├── dashboard/  Dashboard, CellPanel  — app shell, cell/city side panel
├── map/        MapView               — MapLibre map + grid layers
├── forecast/   ForecastSlider        — scrub the 72 h horizon
├── whatif/     WhatIfPanel           — configure & run scenarios (/simulate)
├── chat/       ChatPanel             — grounded Q&A + advisories (/chat)
├── charts/     ForecastChart, SourceBars
└── cursor/     WindCursor, LensCursor — landing / dashboard signature cursors
```

## Design notes

- Palette is derived from the subject: vegetation greens, haze blues, and the
  CPCB AQI band colors. Both data palettes (AQI bands, source categories) are
  validated for colorblind-safe adjacent separation; keep the fixed source
  order (traffic, construction, industry, burning, dust) when adding charts.
- Type: Fraunces (display) + Instrument Sans (UI), self-hosted via Fontsource.
- Cursors and the globe respect `prefers-reduced-motion` and disable on touch.

## Run

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173, proxies /api -> http://localhost:8000
```
