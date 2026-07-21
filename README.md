# VayuLens — Role 3: AI RAG Knowledge & Decision Intelligence Layer

> Turns pollution forecasts, source attribution, and dense government
> regulations into **grounded, cited answers**, **legally-backed
> recommendations**, **enforcement priorities**, and **multilingual citizen
> advisories** — using Retrieval-Augmented Generation.

This repository implements **only Role 3** of the VayuLens platform (`/rag` and
`/decision`). It exposes clean, versioned FastAPI endpoints that Role 1
(geospatial), Role 2 (attribution + forecasting), and Role 4 (React dashboard)
consume.

---

## ✨ Highlights

- **Full RAG pipeline** — parse (PDF/DOCX/HTML/MD/TXT/scanned-OCR) → 5 chunking
  strategies → embeddings → vector store → hybrid retrieval → reranking →
  grounded generation.
- **Grounding by construction** — every answer carries citations (document,
  page, section), a confidence score, and retrieved sources. Below-threshold
  confidence ⇒ the system **refuses** rather than hallucinates.
- **Adapter everywhere** — embeddings (BGE/E5), vector DB (**FAISS** / **Chroma**),
  reranker (CrossEncoder), and LLM (**OpenAI / Claude / Gemini / Ollama**) are
  all swappable via `config.yaml`. Nothing hardcoded.
- **Agentic decision engine** — maps source attribution → specific actions with
  legal justification, priority, and expected impact.
- **Enforcement prioritization** — ranks industrial clusters, construction
  sites, traffic corridors, and burning hotspots with explainable component
  scores.
- **Multilingual advisories** — English, Hindi, Marathi, Tamil, Bengali, Telugu
  for 5 audiences; extensible catalog.
- **Evaluation** — Recall@K, Precision@K, MRR, faithfulness, context precision,
  answer relevance, groundedness, hallucination rate.
- **Runs anywhere offline** — dependency-free fallbacks (hashing embeddings,
  in-memory cosine store, built-in BM25, lexical reranker, extractive LLM) mean
  `pip install -r requirements.txt` + run. Flip config for production models.

---

## 🚀 Quickstart

```bash
# 1. Install core deps (boots with zero external services)
pip install -r requirements.txt

# 2. Build the index from the bundled regulatory corpus
python scripts/ingest.py

# 3. Run the API
uvicorn decision.api.app:app --reload
#    → http://localhost:8000/docs

# 4. Try it
curl -s -X POST localhost:8000/v1/ask -H 'Content-Type: application/json' \
  -d '{"question":"What restrictions apply to construction under GRAP Stage III?"}' | jq .
```

### With Docker
```bash
docker compose up --build
# API on http://localhost:8000 (index pre-built into the image)
```

---

## 🔧 Going to production quality

The defaults use offline fallbacks so the system runs anywhere. For full quality:

```bash
pip install -r requirements-full.txt   # sentence-transformers, faiss, parsers, LLMs
```

Then edit `config/config.yaml` (or set env vars):

```yaml
embeddings:   { provider: sentence_transformers, model: BAAI/bge-large-en-v1.5 }
vector_store: { backend: faiss }
reranker:     { provider: cross_encoder, model: BAAI/bge-reranker-base }
llm:          { provider: claude, model: claude-sonnet-5 }
```

```bash
export ANTHROPIC_API_KEY=...    # or OPENAI_API_KEY / GOOGLE_API_KEY
# Ollama needs no key; set llm.provider: ollama and run ollama locally.
```

Any value is overridable without editing the file:
`VAYULENS__LLM__PROVIDER=openai VAYULENS__RETRIEVER__TOP_K=10 uvicorn ...`

---

## 📚 API surface (versioned `/v1`)

| Method & path | Purpose |
|---|---|
| `GET  /health` | Liveness + config snapshot |
| `POST /v1/ingest` | (Re)build the vector index |
| `POST /v1/ask` | Grounded QA / legal reasoning / summarization |
| `POST /v1/retrieve` | Raw hybrid retrieval + rerank |
| `POST /v1/recommend` | Agentic, legally-grounded enforcement actions |
| `POST /v1/prioritize` | Rank enforcement targets (explainable) |
| `POST /v1/advisory` | Multilingual, audience-specific advisories |
| `POST /v1/evaluate` | RAG retrieval + generation metrics |

Full reference: [`docs/API.md`](docs/API.md). Example payloads and captured
outputs: [`examples/`](examples/).

---

## 🔌 Integration contract (for Roles 1/2/4)

**Inputs you provide** (see `decision/schemas/models.py`):
- Role 1 → `LocationContext` (name, lat/lon, population, hospitals/schools nearby)
- Role 2 → `SourceContribution[]` (source, contribution_pct), `ForecastPoint[]`,
  `WeatherContext`, `current_aqi`

**Outputs Role 4 renders**: `AskResponse`, `RecommendResponse`,
`PrioritizeResponse`, `AdvisoryResponse` — all carry citations / component
scores / rationale for explainable UI.

---

## 🗂️ Project layout

```
rag/         parser · chunking · embeddings · vector_store · retriever ·
             reranker · prompts · llm · evaluation · pipeline.py · config.py
decision/    recommendation_engine · advisory_engine · api · schemas · utils
data/        regulations/ · interventions/ · eval/
config/      config.yaml            scripts/  ingest.py · run_eval.py
docs/        ARCHITECTURE.md · API.md          tests/    unit + integration
examples/    captured request/response JSON + requests.sh
```

Architecture & diagrams: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## 🧪 Tests & evaluation

```bash
pytest -q                       # 23 unit + integration tests, all offline
python scripts/run_eval.py      # writes storage/eval_report.md
```

Sample offline evaluation (bundled corpus, fallback providers):

| Metric | Value |
|---|---|
| Recall@3 | 1.00 |
| MRR | 0.83 |
| Faithfulness | 0.80 |
| Groundedness | 0.90 |
| Hallucination rate | 0.20 |

(Transformer embeddings + cross-encoder reranking push these substantially
higher — the fallbacks are a floor, not a ceiling.)

---

## 📄 Regulatory corpus

Bundled samples (`data/regulations`, `data/interventions`): GRAP, NCAP,
Air Act 1981, CAQM Dust SOP, CPCB Health Advisory, and a Delhi intervention
report. Drop additional NCAP / GRAP / CPCB / CAQM / EP-Act / Factory-Act PDFs,
DOCX, or HTML into those folders and re-run `python scripts/ingest.py`.

---

## License
Built for the ET AI Hackathon 2026. Uses only public government documents for
the knowledge base.
