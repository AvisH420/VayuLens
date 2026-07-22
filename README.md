<div align="center">

# VayuLens

**Hyperlocal air-quality intelligence for Indian cities — from satellite, to street, to policy.**

[Live app](https://vayu-lens.vercel.app) · [API](https://vayulens-api.onrender.com) · Delhi &amp; Panaji · ~1&nbsp;km grid

</div>

---

Indian cities publish a single city-wide AQI number — one figure for millions of people breathing very
different air. VayuLens replaces that with a live, **~1&nbsp;km intelligence grid**, and for every cell it
answers the four questions that actually drive decisions:

- **Sense** — how bad is it, exactly here? A real-time AQI fused from ground stations, satellites and weather models.
- **Attribute** — what is causing it? Per-cell source apportionment across traffic, dust, industry, biomass burning and construction, with a confidence score.
- **Forecast** — where is it heading? A 72-hour AQI trajectory driven by a Gaussian-plume dispersion model over live wind fields.
- **Act** — what should we do? A policy what-if simulator and a regulation-grounded assistant that cite the exact rule (GRAP, CPCB, NCAP) behind every recommendation.

Every number traces back to a source, and every recommendation to a regulation — nothing is fabricated.

## Live data, not a static dataset

A scheduled job pulls current satellite, ground and weather feeds every three hours, fuses them onto the
grid, and publishes a snapshot the site serves in milliseconds. The full pipeline runs offline (the
satellite reductions take minutes); the site stays fast and the data stays fresh. A deterministic demo
engine is always available as a fallback if an upstream feed is unavailable.

## Architecture

```
 Live data sources                Analysis                     Delivery
 ─────────────────                ────────                     ────────
 WAQI · Earth Engine ─▶ ingestion ─▶ data ─▶ attribution ─┐
 Open-Meteo · OSM ·        (pulls)   (grid,                ├─▶ decision ◀─ rag
 OpenAQ · CPCB                       fuse)   forecasting ──┘   (grounded,   (regulation
                                                                cited)       knowledge base)
                                                                   │
                                                                   ▼
                                              api gateway (FastAPI) ─▶ frontend (React + MapLibre)
```

Four modules behind one API, integrated through shared, versioned data **contracts** (`contracts/`).
Each module is developed and tested independently; the contracts guarantee the pieces fit. A full
diagram is in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

**Deployment:** the React frontend runs on Vercel; the FastAPI gateway on Render. A scheduled GitHub
Action runs the real pipeline every three hours and publishes fresh snapshots to a data branch the
gateway reads — so the live site updates without a redeploy.

## Project structure

| Folder | Area | What it does |
| --- | --- | --- |
| [`ingestion/`](ingestion/) | Data | Source connectors (WAQI, Earth Engine, Open-Meteo, OSM, OpenAQ, CPCB), scheduling, raw store |
| [`data/`](data/) | Data | ~1&nbsp;km grid builder, alignment, calibration, inverse-variance fusion, gap-filling |
| [`attribution/`](attribution/) | Analysis | Per-cell source apportionment across six source classes |
| [`forecasting/`](forecasting/) | Analysis | Gaussian-plume dispersion, 72-hour forecast, policy what-if simulator |
| [`rag/`](rag/) | Intelligence | Retrieval-augmented, grounded generation over a regulatory corpus |
| [`decision/`](decision/) | Intelligence | Advisory and recommendation engines, regulation-cited |
| [`api/`](api/) | Platform | FastAPI gateway aggregating every module behind one API |
| [`frontend/`](frontend/) | Platform | React + MapLibre dashboard and landing site |
| [`contracts/`](contracts/) | Shared | Pydantic schemas every module reads and writes |
| [`docs/`](docs/) | Shared | Architecture reference |

## Team

| Area | Member |
| --- | --- |
| Data ingestion &amp; fusion (`ingestion/`, `data/`) | Rudra Singh |
| Attribution &amp; forecasting (`attribution/`, `forecasting/`) | Anuvi Pareek |
| RAG &amp; decision intelligence (`rag/`, `decision/`) | Dhareet Shah |
| Platform &amp; frontend (`api/`, `frontend/`) | Jugraj Singh Bhatia |

## Running locally

**Backend** (Python 3.11+):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.gateway:app --reload          # http://localhost:8000  ·  docs at /docs
```

The gateway serves the deterministic demo engine out of the box. To serve real data, set `REAL_DATA=true`
with a snapshot present (see the live-data layer in `api/live_data.py`); to enable the grounded assistant,
set `REAL_ASSISTANT=true` and provide an `OPEN_ROUTER_API_KEY`.

**Frontend** (Node 18+):

```bash
cd frontend
npm install
npm run dev                               # http://localhost:5173
```

The Vite dev server proxies `/api` to the gateway. Set `VITE_USE_MOCKS=false` to call the live API
instead of the in-browser mock.

**Real-data pipeline** (optional): with live-API credentials in a root `.env`
(`WAQI_TOKEN`, `GEE_PROJECT_ID`, a GEE service-account key, `OPENAQ_API_KEY`) and `USE_MOCK=false`,
`python scripts/build_snapshot.py` runs the full Role 1→2 chain and writes a real snapshot the API can serve.

## Tech stack

React 18 · Vite · MapLibre GL · FastAPI · Pydantic · Google Earth Engine · WAQI · Open-Meteo · OpenStreetMap ·
hybrid retrieval (dense + BM25) · Claude via OpenRouter · Vercel · Render · GitHub Actions.

---

<div align="center"><sub>VayuLens · ET AI Hackathon 2026</sub></div>
