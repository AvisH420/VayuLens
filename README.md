# Contributor Git Workflow

> **👩‍💻 FOR DEVELOPERS — team workflow.** `main` is protected: you cannot push to it
> directly. All work goes through a branch and a pull request that must be approved
> before it merges. Follow the steps below.

## 1. One-time setup

```bash
# Clone the repo and enter it
git clone https://github.com/<owner>/VayuLens.git
cd VayuLens

# Python env + backend deps
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Frontend deps
cd frontend && npm install && cd ..
```

## 2. Start a new piece of work

Always branch from an up-to-date `main`:

```bash
git checkout main
git pull origin main
git checkout -b feature/<your-area>
```

Agreed branch names (one per role-owned area):

```
feature/data        feature/attribution   feature/forecast   feature/rag
feature/decision    feature/api           feature/frontend
```

Work **only inside the folder(s) your role owns** — that way branches touch
different files and never conflict.

## 3. While working

Commit in small, clear steps:

```bash
git add -A
git commit -m "clear message about what changed"
```

Push your branch:

```bash
git push -u origin feature/<your-area>
# after the first push, just: git push
```

## 4. Keep your branch fresh (do this if main has moved on)

```bash
git checkout main
git pull origin main
git checkout feature/<your-area>
git merge main
```

Resolve any conflicts, commit, and push. Doing this regularly avoids painful merges.

## 5. Open a pull request

- Push, then go to the repo on GitHub and click **"Compare & pull request"**.
- Set the **base** branch to `main` and the **compare** branch to your feature branch.
- Write a short description of what you built and which contract(s) you touched.
- The PR **cannot be merged until the code owner approves it** — that approval is
  required, so request their review and wait for the green check.

## 6. After approval

- The code owner (or the PR author, once approved) clicks **"Squash and merge"**.
- Delete the merged branch on GitHub, then locally:

```bash
git checkout main
git pull origin main
git branch -d feature/<your-area>
```

## Golden rules

- **Never** commit directly to `main`.
- Only edit files inside your role's folder(s); if you need a change in a shared file
  under `contracts/`, **message the group first**.
- Pull `main` before starting anything new.
- Keep PRs small and focused so reviews are fast.

---

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
| [`data/`](data/) | Role 1(Rudra) | Data Engineer               | Source connectors, ~1km grid builder, calibration/fusion |
| [`ingestion/`](ingestion/) | Role 1(Rudra) | Data Engineer     | Schedulers, raw pulls, GEE satellite pipeline          |
| [`attribution/`](attribution/) | Role 2(Anuvi) | Modeling        | Source-attribution engine                              |
| [`forecasting/`](forecasting/) | Role 2(Anuvi) | Modeling        | Dispersion model, 24-72h forecast, `simulate(scenario)`|
| [`rag/`](rag/)   | Role 3(Dhareet) | Knowledge & Agents          | Doc ingestion, vector store, retriever, grounded gen, eval |
| [`decision/`](decision/) | Role 3(Dhareet) | Knowledge & Agents  | Agentic recommendations, enforcement priority, multi-language advisories |
| [`api/`](api/)   | Role 4(Jugraj) | Platform & Frontend         | FastAPI gateway aggregating all modules                |
| [`frontend/`](frontend/) | Role 4(Jugraj) | Platform & Frontend | React app — map, layers, forecast slider, what-if, chat |
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
