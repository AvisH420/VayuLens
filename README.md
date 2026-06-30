# VayuLens

**AI-powered urban air-quality intelligence platform.**

VayuLens fuses ground sensors, satellite products, and meteorology onto a ~1km
city grid, attributes pollution to its sources, forecasts where it's heading,
and turns that into grounded, regulation-cited recommendations — surfaced
through an API and an interactive map UI.

> ⚠️ This repository is **scaffolding only**: structure, stubs, and docs. No
> real implementation yet. Backend stubs raise `NotImplementedError`; frontend
> components are empty.

## Architecture — data flow

```
            ┌─────────────────────────────────────────────────────────┐
ingestion ─▶│  data  ├─▶ attribution ─┐                                │
(raw pulls) │ (grid, │                ├─▶ decision ◀─ rag (grounded KB) │
            │ fusion)├─▶ forecasting ─┘     │                          │
            └─────────────────────────────┬─┴──────────────────────────┘
                                          ▼
                                    api (gateway) ─▶ frontend (map/forecast/whatif/chat)
```

In words:

1. **ingestion → data** — raw pulls (incl. GEE satellite) are calibrated and
   fused onto the ~1km grid as `Measurement`s.
2. **data → attribution / forecasting** — measurements drive source
   apportionment and 24-72h forecasts.
3. **attribution / forecasting + rag → decision** — insights plus a grounded
   knowledge base produce regulation-cited `Recommendation`s.
4. **everything → api → frontend** — the FastAPI gateway aggregates all modules;
   the React app renders the map, forecast slider, what-if panel, and chat.

All cross-module data uses the shared shapes in [`contracts/`](contracts/README.md).

## Folder ownership

| Folder           | Role   | Owner area                  | Purpose                                                |
| ---------------- | ------ | --------------------------- | ------------------------------------------------------ |
| [`data/`](data/) | Role 1 | Data Engineer               | Source connectors, ~1km grid builder, calibration/fusion |
| [`ingestion/`](ingestion/) | Role 1 | Data Engineer     | Schedulers, raw pulls, GEE satellite pipeline          |
| [`attribution/`](attribution/) | Role 2 | Modeling        | Source-attribution engine                              |
| [`forecasting/`](forecasting/) | Role 2 | Modeling        | Dispersion model, 24-72h forecast, `simulate(scenario)`|
| [`rag/`](rag/)   | Role 3 | Knowledge & Agents          | Doc ingestion, vector store, retriever, grounded gen, eval |
| [`decision/`](decision/) | Role 3 | Knowledge & Agents  | Agentic recommendations, enforcement priority, multi-language advisories |
| [`api/`](api/)   | Role 4 | Platform & Frontend         | FastAPI gateway aggregating all modules                |
| [`frontend/`](frontend/) | Role 4 | Platform & Frontend | React app — map, layers, forecast slider, what-if, chat |
| [`contracts/`](contracts/) | shared | all roles         | Shared data schemas every role builds against          |
| [`docs/`](docs/) | shared | all roles                   | Architecture notes                                     |

## Local setup

### Backend (Python 3.11+)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run the API gateway (stubs raise NotImplementedError for now)
uvicorn api.gateway:app --reload   # http://localhost:8000
```

### Frontend (Node 18+)

```bash
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

The Vite dev server proxies `/api` → `http://localhost:8000`.

## Repo conventions

- Cross-module data shapes live in [`contracts/`](contracts/README.md).
  **Changing a schema requires telling the group first.**
- Each top-level folder is owned by exactly one role and has its own `README.md`.
