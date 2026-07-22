# frontend/

The user-facing application — a React + Vite app over a MapLibre base map — in two surfaces:

- **`/`** — the landing site: a three.js globe hero and interactive teasers for attribution, forecasting,
  the simulator and the assistant.
- **`/app`** — the dashboard: the ~1&nbsp;km grid as switchable layers (Live AQI · dominant source ·
  forecast hour · what-if delta), a forecast time slider, per-cell inspection (attribution, banded
  forecast, regulation-cited recommendations), the what-if drawer, and the grounded chat assistant with
  a multi-language advisory tab.

## Data

`src/lib/api.js` mirrors the gateway routes one-for-one. With `VITE_USE_MOCKS=false` it calls the live
API (`VITE_API_BASE`); otherwise it serves the in-browser mock in `src/lib/mock.js` — identical
`contracts/` shapes, so the UI is always demonstrable.

## Component areas

```
src/components/
├── landing/    Landing + hero
├── dashboard/  Dashboard, CellPanel   — app shell, cell/city side panel
├── map/        MapView                — MapLibre map + grid layers
├── forecast/   ForecastSlider         — scrub the 72 h horizon
├── whatif/     WhatIfPanel            — configure & run scenarios (/simulate)
├── chat/       ChatPanel              — grounded Q&A + advisories (/chat)
└── charts/     ForecastChart, SourceBars
```

## Design

Palette derived from the subject — vegetation greens, haze blues, and the CPCB AQI band colours (both the
AQI-band and source-category palettes are validated for colourblind-safe separation). Type: Fraunces
(display) + Instrument Sans (UI). Motion respects `prefers-reduced-motion`.

## Run

```bash
cd frontend && npm install && npm run dev     # http://localhost:5173 (proxies /api to the gateway)
```
