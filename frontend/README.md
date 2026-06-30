# frontend/ — React app (Vite)

**Owner:** Role 4 (Platform & Frontend)
**Builds against:** the [`api/`](../api/README.md) gateway (JSON typed by `contracts/`)

## Purpose

The user-facing application: an interactive map with layers, a forecast time
slider, a what-if scenario panel, and a grounded chat assistant.

## Inputs

- JSON from the [`api/`](../api/README.md) gateway (grid, measurements,
  attribution, forecast, recommendations, chat).

## Outputs

- The web UI users interact with.

## Component areas

```
src/components/
├── map/        MapView        — map + layers
├── forecast/   ForecastSlider — scrub the 24-72h horizon
├── whatif/     WhatIfPanel    — configure & run scenarios (/simulate)
└── chat/       ChatPanel      — grounded Q&A (/chat)
```

## Run

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173, proxies /api -> http://localhost:8000
```
