"""VayuLens Decision Intelligence API (Step 13).

Versioned FastAPI service. All decision/RAG endpoints live under /v1 so Roles
1/2/4 integrate against a stable contract. A GET /health probe and OpenAPI docs
at /docs are provided.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from rag.config import get_settings
from rag.evaluation import EvalSample as CoreEvalSample
from rag.evaluation import Evaluator
from rag.logging_utils import get_logger
from rag.pipeline import RAGPipeline

from decision.advisory_engine import AdvisoryEngine
from decision.api.deps import (
    get_advisory_engine,
    get_evaluator,
    get_pipeline,
    get_prioritizer,
    get_recommendation_engine,
)
from decision.recommendation_engine import EnforcementPrioritizer, RecommendationEngine
from decision.schemas.models import (
    AdvisoryRequest,
    AdvisoryResponse,
    AskRequest,
    AskResponse,
    EvaluateRequest,
    EvaluateResponse,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    PrioritizeRequest,
    PrioritizeResponse,
    RecommendRequest,
    RecommendResponse,
    RetrievedChunk,
    RetrieveRequest,
    RetrieveResponse,
)

log = get_logger(__name__)
settings = get_settings()

app = FastAPI(
    title=settings.app.name,
    version=settings.app.version,
    description=(
        "VayuLens Role 3 — RAG Knowledge & Agentic Decision Intelligence Layer. "
        "Grounded, cited answers; legally-backed recommendations; enforcement "
        "prioritization; and multilingual advisories."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

v1 = APIRouter(prefix="/v1", tags=["v1"])


@app.get("/health", response_model=HealthResponse)
def health(pipeline: RAGPipeline = Depends(get_pipeline)) -> HealthResponse:
    s = pipeline.settings
    reranker_name = "disabled"
    if pipeline.reranker is not None:
        reranker_name = type(pipeline.reranker).__name__
    return HealthResponse(
        status="ok",
        version=s.app.version,
        indexed_chunks=pipeline.store.count(),
        embedding_provider=s.embeddings.provider,
        vector_backend=s.vector_store.backend,
        llm_provider=s.llm.provider,
        reranker=reranker_name,
    )


@v1.post("/ask", response_model=AskResponse)
def ask(req: AskRequest, pipeline: RAGPipeline = Depends(get_pipeline)) -> AskResponse:
    if req.task == "legal":
        ans = pipeline.legal_reason(req.question, top_k=req.top_k)
    elif req.task == "summarize":
        ans = pipeline.summarize(req.question, top_k=req.top_k)
    else:
        ans = pipeline.ask(
            req.question, top_k=req.top_k, metadata_filter=req.metadata_filter
        )
    return AskResponse(
        answer=ans.answer, confidence=ans.confidence, grounded=ans.grounded,
        refused=ans.refused, citations=ans.citations,
        retrieved_sources=ans.retrieved_sources, reasoning=ans.reasoning,
    )


@v1.post("/retrieve", response_model=RetrieveResponse)
def retrieve(
    req: RetrieveRequest, pipeline: RAGPipeline = Depends(get_pipeline)
) -> RetrieveResponse:
    chunks = pipeline.retrieve(
        req.query, top_k=req.top_k, metadata_filter=req.metadata_filter,
        rerank=req.rerank,
    )
    results = [
        RetrievedChunk(
            text=c.chunk.text, source=c.chunk.source, doc_type=c.chunk.doc_type,
            page=c.chunk.page, section=c.chunk.section, score=round(c.score, 4),
            method=c.retrieval_method,
        )
        for c in chunks
    ]
    return RetrieveResponse(query=req.query, results=results)


@v1.post("/recommend", response_model=RecommendResponse)
def recommend(
    req: RecommendRequest,
    engine: RecommendationEngine = Depends(get_recommendation_engine),
) -> RecommendResponse:
    return engine.recommend(req)


@v1.post("/prioritize", response_model=PrioritizeResponse)
def prioritize(
    req: PrioritizeRequest,
    prioritizer: EnforcementPrioritizer = Depends(get_prioritizer),
) -> PrioritizeResponse:
    return prioritizer.prioritize(req)


@v1.post("/advisory", response_model=AdvisoryResponse)
def advisory(
    req: AdvisoryRequest, engine: AdvisoryEngine = Depends(get_advisory_engine)
) -> AdvisoryResponse:
    return engine.generate(req)


@v1.post("/evaluate", response_model=EvaluateResponse)
def evaluate(
    req: EvaluateRequest, evaluator: Evaluator = Depends(get_evaluator)
) -> EvaluateResponse:
    samples = [
        CoreEvalSample(
            question=s.question, relevant_doc_ids=s.relevant_doc_ids,
            ground_truth=s.ground_truth,
        )
        for s in req.samples
    ]
    result = evaluator.evaluate(samples, req.k_values)
    return EvaluateResponse(**result)


@v1.post("/ingest", response_model=IngestResponse)
def ingest(
    req: IngestRequest, pipeline: RAGPipeline = Depends(get_pipeline)
) -> IngestResponse:
    try:
        if req.directory:
            count = pipeline.index_directory(req.directory)
            detail = {req.directory: count}
        else:
            detail = pipeline.index_corpus()
            count = sum(detail.values())
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e)) from e
    return IngestResponse(indexed_chunks=count, detail=detail)


app.include_router(v1)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {
        "service": settings.app.name,
        "version": settings.app.version,
        "docs": "/docs",
        "health": "/health",
        "api": "/v1",
    }
