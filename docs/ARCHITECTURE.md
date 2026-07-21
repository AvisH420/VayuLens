# VayuLens — Role 3 Architecture

**Role 3: AI / RAG Knowledge & Decision Intelligence Layer**

This service turns raw model outputs (forecasts, source attribution) and dense
regulations into grounded, cited, actionable intelligence — answerable in plain
language and six regional languages.

---

## 1. System context (where Role 3 sits)

```
        ┌─────────────────────────────────────────────────────────────┐
        │                      VayuLens Platform                        │
        │                                                               │
  ┌─────┴──────┐   ┌──────────────┐   ┌────────────────────┐   ┌────────┴───────┐
  │  Role 1    │   │   Role 2     │   │   ROLE 3 (this)    │   │    Role 4      │
  │ Geospatial │──▶│ Attribution  │──▶│  RAG + Decision    │──▶│ React Dashboard│
  │ Data Layer │   │ + Forecasting│   │  Intelligence      │   │                │
  └────────────┘   └──────────────┘   └────────────────────┘   └────────────────┘
     locations,        AQI, source        grounded answers,        renders cited
     population,        %, forecast         recommendations,         answers, maps,
     POIs               weather             priorities, advisories   advisories
```

Role 3 **consumes** Role 1 (location, population, hospitals/schools nearby) and
Role 2 (AQI, source attribution %, forecast, weather) as JSON inputs, and
**produces** grounded decisions that Role 4 renders. Contracts live in
`decision/schemas/models.py` under the versioned `/v1` prefix.

---

## 2. Module map

```
rag/                         Retrieval-Augmented Generation infrastructure
├── parser/                  PDF, DOCX, TXT, HTML, MD, scanned-PDF (OCR) ingestion
├── chunking/                sentence | semantic | heading | sliding | recursive
├── embeddings/              sentence-transformers | hashing fallback (adapter)
├── vector_store/            faiss | chroma | memory  (swappable behind interface)
├── retriever/               dense + BM25 + hybrid fusion + metadata filter + MMR
├── reranker/                CrossEncoder | lexical fallback
├── prompts/                 QA | recommendation | summarize | legal | advisory
├── llm/                     openai | claude | gemini | ollama | extractive (adapter)
├── evaluation/              Recall@K, Precision@K, MRR, faithfulness, groundedness…
└── pipeline.py              Orchestrator: ingest → retrieve → rerank → ground → answer

decision/                    Agentic Decision Intelligence
├── recommendation_engine/   agentic actions (Step 9) + enforcement ranking (Step 10)
├── advisory_engine/         multilingual advisories (Step 11) + locale catalog
├── schemas/                 Pydantic API contracts (the versioned interface)
├── api/                     FastAPI app + dependency wiring
└── utils/                   AQI banding, GRAP-stage mapping, legal urgency
```

---

## 3. RAG data flow

```
 INGEST                                QUERY
 ──────                                ─────
 files ─▶ parser ─▶ elements           question
            │       (text, tables,        │
            ▼        headings, page)       ▼
        chunking ─▶ chunks            ┌────────────────┐
            │       (+ provenance)    │  HybridRetriever│
            ▼                         │  dense + BM25   │
        embeddings ─▶ vectors         │  fusion (α)     │
            │                         │  metadata filter│
            ▼                         │  MMR diversity  │
        vector_store  ◀───────────────┤                │
        (faiss/chroma/memory)         └───────┬────────┘
                                              ▼
                                        reranker (CrossEncoder)
                                              ▼
                                        top context
                                              ▼
                                     ┌──────────────────┐
                                     │ Grounding gate    │
                                     │ confidence ≥ thr? │──no──▶ REFUSE (no hallucination)
                                     └────────┬─────────┘
                                              │ yes
                                              ▼
                                       prompt + LLM adapter
                                              ▼
                              GroundedAnswer{answer, confidence,
                                 citations[source,page,section], sources}
```

---

## 4. Decision flow (agentic)

```
 Role 2 attribution + Role 1 location + AQI + forecast + weather
                              │
                              ▼
        ┌────────────────────────────────────────────┐
        │  RecommendationEngine                        │
        │  1. rank sources by contribution %           │
        │  2. per source → intervention playbook       │
        │  3. RAG-retrieve governing regulation        │
        │  4. LLM composes grounded justification      │
        │  5. priority = f(contribution, GRAP stage)   │
        └────────────────────┬───────────────────────┘
                             ▼
            ActionRecommendation[] { action, priority,
              legal_basis[citations], justification,
              expected_impact, grap_stage, confidence }

 Enforcement targets (clusters, sites, corridors, hotspots)
                              │
                              ▼
        ┌────────────────────────────────────────────┐
        │  EnforcementPrioritizer (weighted, config)   │
        │  score = Σ wᵢ · normalise(featureᵢ)          │
        │  features: pollution, population, hospitals, │
        │            schools, forecast_trend, legal    │
        └────────────────────┬───────────────────────┘
                             ▼
            RankedTarget[] { rank, priority, score,
              component_scores (explainable), rationale }
```

---

## 5. Key design decisions

| Decision | Rationale |
|---|---|
| **Adapter pattern** for embeddings, vector store, reranker, LLM | Swap FAISS↔Chroma or OpenAI↔Claude↔Gemini↔Ollama via config only. No code changes. |
| **Config-first (`config.yaml` + env overrides)** | Every knob (chunk size, top-k, α, thresholds, languages) is declarative and reproducible. |
| **Grounding enforced structurally** | The answer schema *requires* citations; a confidence gate refuses below threshold — hallucination is prevented by construction, not by prompt alone. |
| **Real dependency-free fallbacks** | Hashing embeddings, in-memory cosine store, built-in BM25, lexical reranker, and an extractive LLM let the whole system run and be tested offline. These are functioning implementations, not stubs — production simply flips config to transformer-grade models. |
| **Provenance carried end-to-end** | `source`, `page`, `section`, `doc_type` travel from parser → chunk → citation, so Role 4 can render precise legal references. |
| **Versioned `/v1` API** | Roles 1/2/4 integrate against a stable, additive contract. |

---

## 6. Configuration surface

All in `config/config.yaml`, overridable via `VAYULENS__<SECTION>__<KEY>` env vars:

- `embeddings.provider/model`, `chunking.strategy/chunk_size/overlap`
- `vector_store.backend`, `retriever.mode/top_k/hybrid_alpha/mmr_lambda`
- `reranker.provider/model/top_n`, `grounding.confidence_threshold`
- `llm.provider/model/temperature`, `advisory.supported_languages`
- `decision.weights` (enforcement scoring)
