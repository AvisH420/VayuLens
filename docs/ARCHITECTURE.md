# VayuLens — Architecture

VayuLens is four independent modules behind one API, integrated through a set of shared, versioned data
**contracts**. Each module owns its own folder and can be developed and tested in isolation; the
contracts guarantee the pieces fit together.

## Data & module flow

```
 Live data sources                Analysis                     Delivery
 WAQI · Earth Engine ─▶ ingestion ─▶ data ─▶ attribution ─┐
 Open-Meteo · OSM ·        (pulls)   (grid,                ├─▶ decision ◀─ rag
 OpenAQ · CPCB                       fuse)   forecasting ──┘   (grounded,   (regulation KB)
                                                                cited)
                                                                   │
                                                                   ▼
                                              api gateway (FastAPI) ─▶ frontend (React + MapLibre)
```

1. **ingestion → data** — raw pulls (ground stations, Earth Engine satellite, weather, OSM land use) are
   snapped to the ~1&nbsp;km grid, calibrated, fused by inverse-variance weighting, and gap-filled into
   `Measurement` records with a quality score.
2. **data → attribution / forecasting** — measurements plus static grid context drive per-cell source
   apportionment and a 72-hour Gaussian-plume forecast, and power the policy what-if simulator.
3. **attribution / forecasting + rag → decision** — analysis plus a grounded regulatory knowledge base
   produce regulation-cited `Recommendation`s and public advisories.
4. **api → frontend** — the FastAPI gateway aggregates every module behind one API; the React app renders
   the map, forecast slider, what-if panel and grounded assistant.

## Deployment topology

```
 Frontend  Vercel (React + Vite)  ──calls──▶  Backend  Render (FastAPI gateway)
                                                  │ serves the contract shapes from either:
                                                  ├─ demo_engine   — deterministic simulation (fallback)
                                                  └─ real snapshot — live data, refreshed offline
 GitHub Action (every 3h) ─▶ runs the real pipeline on live APIs ─▶ writes a snapshot
                          ─▶ publishes to a public data branch the gateway reads (cached)
```

The full real pipeline (satellite reductions + fusion) takes minutes — too slow for a web request — so it
runs offline on a schedule and publishes a precomputed snapshot the API serves instantly. The site stays
fast, the data stays fresh (three-hourly), and the deterministic demo engine is always available as a
fallback. Data updates reach the site without a redeploy.

## Shared contracts

`GridCell`, `Measurement`, `Attribution`, `Forecast`, `Recommendation` (see
[`contracts/`](../contracts/README.md)). These are the integration seam between the four modules; every
cross-module value is one of these Pydantic shapes.

## Module ownership

| Module | Area | Owner |
| --- | --- | --- |
| `ingestion/`, `data/` | Data ingestion & fusion | Rudra Singh |
| `attribution/`, `forecasting/` | Attribution & forecasting | Anuvi Pareek |
| `rag/`, `decision/` | RAG & decision intelligence | Dhareet Shah |
| `api/`, `frontend/` | Platform & frontend | Jugraj Singh Bhatia |
