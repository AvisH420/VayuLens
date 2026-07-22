# api/

The single HTTP entry point the frontend talks to. The FastAPI gateway aggregates every backend module
and exposes it behind one consistent API, returning the shared [`contracts/`](../contracts/) types.

## Layout

- **`gateway.py`** — the FastAPI app and all routes (`/grid`, `/attribution/{cell}`, `/forecast/{cell}`,
  `/measurements/{cell}`, `/simulate`, `/recommendations/{cell}`, `/chat`, `/advisories/{city}`, `/health`).
- **`demo_engine.py`** — a deterministic simulation that serves every contract shape. It is the always-on
  fallback and the offline demo.
- **`live_data.py`** — serves precomputed real snapshots (from a public data branch, cached) when
  `REAL_DATA=true`, so the site shows fresh real data without a redeploy.
- **`assistant.py`** — wires `/chat` to the RAG assistant (grounded generation via OpenRouter) when
  `REAL_ASSISTANT=true`.
- **`role2_adapter.py`** — maps the analysis modules' output onto the platform contracts.

## Run

```bash
uvicorn api.gateway:app --reload    # http://localhost:8000  ·  interactive docs at /docs
```

Serves the demo engine by default; set `REAL_DATA=true` (with a snapshot present) to serve live data.
