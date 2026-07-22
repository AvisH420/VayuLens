# rag/

Makes the platform's advice *grounded* in real regulations and science. A retrieval-augmented pipeline
turns a curated corpus of Indian air-quality regulation into cited, trustworthy answers — and refuses
rather than guess when the corpus doesn't cover a question.

## Pipeline

document parsing → chunking → embeddings → hybrid retrieval → reranking → grounded generation

- **`parser/`, `chunking/`** — load and split documents (regulations, SOPs, intervention playbooks).
- **`embeddings/`** — transformer embeddings when available, with a zero-dependency hashing fallback so
  the pipeline runs anywhere.
- **`vector_store/`** — a JSON-persisted store with cosine search.
- **`retriever/`** — **hybrid retrieval**: dense + BM25 with score fusion and MMR diversification.
- **`reranker/`** — cross-encoder reranking, with a lexical fallback.
- **`llm/`** — a provider-agnostic LLM layer (OpenAI, Claude, Gemini, Ollama, OpenRouter, and an
  extractive no-API fallback). In production it uses **Claude via OpenRouter**.
- **`prompts/`, `evaluation/`** — grounding prompts (which instruct the model to cite sources and reply
  `INSUFFICIENT_CONTEXT` when it cannot answer) and a faithfulness/retrieval eval harness.

## Entry point

`pipeline.py` — `RAGPipeline` (index a corpus, then `ask` / `recommend` / `advisory`), returning a
`GroundedAnswer` with the answer, confidence, and citations.
