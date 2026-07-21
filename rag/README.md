# rag/ — Document ingestion, vector store, retriever, grounded generation, eval

**Owner:** Role 3 (Knowledge & Agents)
**Builds against:** regulatory/policy corpus; output consumed by [`decision/`](../decision/README.md)

## Purpose

Make the platform's advice *grounded* in real regulations and science. A
retrieval-augmented pipeline turns a document corpus into cited, trustworthy
answers — and an eval harness keeps it honest.

- **Document ingestion** — load, chunk, embed regulations / SOPs / reports.
- **Vector store** — index and persist embeddings.
- **Retriever** — fetch the most relevant passages for a query.
- **Grounded generation** — answer with inline citations to sources.
- **Eval** — measure faithfulness, groundedness, retrieval hit-rate.

## Inputs

- A corpus of documents (regulations, policy, scientific literature).
- Natural-language queries (often from [`decision/`](../decision/README.md)).

## Outputs

- Grounded answers `{"answer", "citations"}` with source attribution.
- Eval metric reports.

## Key module

- `pipeline.py` — `ingest_documents`, `retrieve`, `generate_grounded`, `evaluate`.
