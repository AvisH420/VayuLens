# VayuLens Decision API — Reference

Base URL: `http://localhost:8000`
Interactive docs (OpenAPI/Swagger): `GET /docs` · ReDoc: `GET /redoc`

All business endpoints are versioned under `/v1`. `GET /health` and `GET /` are
unversioned operational probes.

---

## Authentication
None at this layer (deploy behind the platform gateway). CORS is open for the
Role 4 dashboard; restrict `allow_origins` in production.

---

## `GET /health`
Liveness + configuration snapshot.

**Response**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "indexed_chunks": 24,
  "embedding_provider": "hash",
  "vector_backend": "memory",
  "llm_provider": "extractive",
  "reranker": "LexicalReranker"
}
```

---

## `POST /v1/ingest`
(Re)build the vector index from the corpus. Body `{}` ingests
`data/regulations` + `data/interventions`; `{"directory": "path"}` ingests one
folder (appended).

**Response** `{ "indexed_chunks": 24, "detail": {"regulations": 20, "interventions": 4} }`

---

## `POST /v1/ask`
Grounded question answering. `task` ∈ `qa` (default) | `legal` | `summarize`.

**Request**
```json
{ "question": "What restrictions apply to construction under GRAP Stage III?",
  "top_k": 8, "task": "qa", "metadata_filter": {"doc_type": "GRAP"} }
```
**Response** (`AskResponse`)
```json
{
  "answer": "Under GRAP Stage III, ... construction and demolition ... banned [1]",
  "confidence": 0.53,
  "grounded": true,
  "refused": false,
  "citations": [
    {"doc_id": "…", "source": "GRAP_2023.md", "doc_type": "GRAP",
     "page": 1, "section": "Stage III — Severe (AQI 401-450)",
     "snippet": "Under GRAP Stage III, there is a ban on construction …",
     "score": 0.55}
  ],
  "retrieved_sources": ["GRAP_2023.md", "Delhi_Interventions_2022.md"],
  "reasoning": "Grounded via qa over 5 reranked sources."
}
```
If confidence < `grounding.confidence_threshold`, `refused=true` and `answer`
carries the refusal message — **no hallucinated content is returned**.

---

## `POST /v1/retrieve`
Raw retrieval (dense + BM25 + hybrid + MMR + optional rerank). Useful for the
dashboard's "show sources" panel.

**Request** `{ "query": "industrial closure unapproved fuel", "top_k": 4, "rerank": true }`
**Response** `RetrieveResponse` — list of `{text, source, doc_type, page, section, score, method}`.

---

## `POST /v1/recommend`
Agentic decision engine. Consumes Role 1 + Role 2 outputs, returns ranked,
legally-grounded enforcement actions.

**Request** (`RecommendRequest`)
```json
{
  "location": {"name": "Anand Vihar", "population": 250000,
               "hospitals_nearby": 3, "schools_nearby": 12},
  "current_aqi": 432,
  "source_attribution": [
    {"source": "construction", "contribution_pct": 42},
    {"source": "traffic", "contribution_pct": 28},
    {"source": "industry", "contribution_pct": 18}
  ],
  "forecast": [{"horizon_hours": 24, "aqi": 455}],
  "weather": {"wind_speed_ms": 1.2, "inversion": true},
  "language": "en"
}
```
**Response** (`RecommendResponse`) — `grap_stage`, `summary`, and
`recommendations[]` each with `action`, `priority`
(`critical|high|medium|low`), `legal_basis[]` (citations), `justification`,
`expected_impact`, `confidence`.

---

## `POST /v1/prioritize`
Enforcement prioritization. Ranks targets by a transparent weighted score.

**Request** (`PrioritizeRequest`)
```json
{
  "current_aqi": 432,
  "targets": [
    {"target_id": "IC1", "name": "Wazirpur Industrial Cluster",
     "category": "industrial", "pollution_contribution_pct": 35,
     "population_exposed": 180000, "hospitals_nearby": 2,
     "schools_nearby": 8, "forecast_trend": 20}
  ]
}
```
**Response** (`PrioritizeResponse`) — `ranked_targets[]` each with `rank`,
`priority`, `score`, `component_scores` (per-factor, explainable), and
`rationale`.

---

## `POST /v1/advisory`
Multilingual, audience-specific advisories.
Audiences: `citizen|hospital|school|outdoor_worker|senior_citizen`.
Languages: `en|hi|mr|ta|bn|te` (extensible).

**Request**
```json
{ "location": "Anand Vihar", "current_aqi": 432,
  "audiences": ["citizen", "hospital"], "languages": ["en", "hi", "ta"] }
```
**Response** (`AdvisoryResponse`) — one `Advisory` per (audience × language) with
`headline`, `message`, `actions[]`, and grounding `citations[]`.

---

## `POST /v1/evaluate`
Runs the evaluation suite over provided samples.

**Request** `{ "samples": [{"question": "...", "relevant_doc_ids": ["<doc_id>"]}], "k_values": [1,3,5] }`
**Response** (`EvaluateResponse`) — `retrieval_metrics` (recall@k, precision@k,
mrr), `generation_metrics` (faithfulness, context_precision, answer_relevance,
groundedness, hallucination_rate), and `per_sample` breakdown.

---

## Error model
Standard FastAPI: `422` for schema validation, `400` for ingestion failures
(`{"detail": "..."}`). Grounding refusals are **200 OK** with `refused=true` —
they are a valid, expected outcome, not an error.
