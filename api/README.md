# api/ — FastAPI gateway

**Owner:** Role 4 (Platform & Frontend)
**Builds against:** every `contracts/` schema; aggregates all backend modules

## Purpose

The single HTTP entry point the frontend talks to. It aggregates and exposes the
outputs of every backend module behind one consistent API, returning the shared
`contracts/` types.

## Inputs

- HTTP requests from [`frontend/`](../frontend/README.md).
- In-process / service calls to `data`, `attribution`, `forecasting`, `rag`,
  `decision`.

## Outputs

- JSON responses typed by `contracts/` schemas.

## Endpoints (live, served by the demo engine)

| Method | Path                        | Returns                                                  |
| ------ | --------------------------- | -------------------------------------------------------- |
| GET    | `/health`                   | liveness + cell counts per city                           |
| GET    | `/grid?city=`               | full city payload (cfg + enriched cells + city means)     |
| GET    | `/measurements/{cell_id}`   | `list[Measurement]`                                       |
| GET    | `/attribution/{cell_id}`    | `Attribution`                                             |
| GET    | `/forecast/{cell_id}`       | `Forecast`                                                |
| POST   | `/simulate`                 | per-cell counterfactuals + summary (`SimulationResult`)   |
| GET    | `/recommendations/{cell_id}`| `list[Recommendation]`                                    |
| POST   | `/chat`                     | grounded answer + citations (`ChatAnswer`)                |
| GET    | `/advisories/{city}`        | citizen advisories keyed by language                      |

Contracts models are returned verbatim where they fit; gateway-local
envelopes (`SimulationResult`, `ChatAnswer`) wrap them where the frontend
needs more than a bare list. `contracts/` itself is untouched.

## Run

```bash
# once: from the repo root
python3 -m venv .venv
.venv/bin/pip install "fastapi>=0.110" "uvicorn[standard]>=0.29" "pydantic>=2.6"

# every time
.venv/bin/uvicorn api.gateway:app --reload    # http://127.0.0.1:8000/docs
```

The frontend hits it through the Vite `/api` proxy — start the dev server
with `VITE_USE_MOCKS=false npm run dev` and every async call site switches
from `lib/mock.js` to the gateway with no UI changes.

## Key modules

- `gateway.py` — the FastAPI `app`, all routes implemented.
- `demo_engine.py` — deterministic Python port of `frontend/src/lib/mock.js`
  (same mulberry32 RNG, numerically identical grid). Each handler swaps its
  engine call for the real module (data/attribution/forecasting/rag/decision)
  as those land; response shapes stay fixed.
