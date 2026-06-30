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

## Endpoints (stubbed)

| Method | Path                        | Returns                  |
| ------ | --------------------------- | ------------------------ |
| GET    | `/grid`                     | `list[GridCell]`         |
| GET    | `/measurements/{cell_id}`   | `list[Measurement]`      |
| GET    | `/attribution/{cell_id}`    | `Attribution`            |
| GET    | `/forecast/{cell_id}`       | `Forecast`               |
| POST   | `/simulate`                 | `list[Forecast]`         |
| GET    | `/recommendations/{cell_id}`| `list[Recommendation]`   |
| POST   | `/chat`                     | grounded answer + cites  |

## Run (once implemented)

```bash
uvicorn api.gateway:app --reload
```

## Key module

- `gateway.py` — the FastAPI `app` and route stubs.
