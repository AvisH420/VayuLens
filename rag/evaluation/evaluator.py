"""RAG evaluation (Step 14).

Retrieval metrics: Recall@K, Precision@K, MRR.
Generation metrics: Faithfulness, Context Precision, Answer Relevance,
Groundedness, Hallucination Rate.

All metrics are computed with transparent, dependency-free formulas over the
pipeline's own outputs so the report is reproducible offline. Where an LLM
judge would normally be used, we use lexical-overlap proxies that are honest
about what they measure (documented per metric).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from rag.logging_utils import get_logger
from rag.pipeline import RAGPipeline
from rag.text_utils import content_tokens, split_sentences

log = get_logger(__name__)


@dataclass
class EvalSample:
    question: str
    relevant_doc_ids: list[str] = field(default_factory=list)
    ground_truth: str | None = None


# ----------------------------- retrieval metrics -----------------------------
def recall_at_k(retrieved_ids: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    top = set(retrieved_ids[:k])
    return len(top & relevant) / len(relevant)


def precision_at_k(retrieved_ids: list[str], relevant: set[str], k: int) -> float:
    if k == 0:
        return 0.0
    top = retrieved_ids[:k]
    if not top:
        return 0.0
    return sum(1 for d in top if d in relevant) / len(top)


def reciprocal_rank(retrieved_ids: list[str], relevant: set[str]) -> float:
    for i, d in enumerate(retrieved_ids, start=1):
        if d in relevant:
            return 1.0 / i
    return 0.0


# ----------------------------- generation metrics ----------------------------
def _overlap(a: str, b: str) -> float:
    ta, tb = content_tokens(a), content_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta)


def faithfulness(answer: str, context: str) -> float:
    """Share of answer sentences supported by the retrieved context."""
    sents = split_sentences(answer)
    if not sents:
        return 0.0
    ctx_tokens = content_tokens(context)
    supported = 0
    for s in sents:
        st = content_tokens(s)
        if st and len(st & ctx_tokens) / len(st) >= 0.5:
            supported += 1
    return supported / len(sents)


def context_precision(question: str, contexts: list[str]) -> float:
    """Share of retrieved contexts that are relevant to the question."""
    if not contexts:
        return 0.0
    q = content_tokens(question)
    if not q:
        return 0.0
    relevant = sum(
        1 for c in contexts if len(q & content_tokens(c)) / len(q) >= 0.15
    )
    return relevant / len(contexts)


def answer_relevance(question: str, answer: str) -> float:
    """How much of the question's content the answer addresses."""
    q, a = content_tokens(question), content_tokens(answer)
    if not q:
        return 0.0
    return len(q & a) / len(q)


def groundedness(answer: str, has_citations: bool, faith: float) -> float:
    """Combined grounding signal: citation presence gated by faithfulness."""
    return round((0.5 if has_citations else 0.0) + 0.5 * faith, 4)


def hallucination_rate(faith: float) -> float:
    """Fraction of answer content not supported by context."""
    return round(1.0 - faith, 4)


# ----------------------------------- runner ----------------------------------
class Evaluator:
    def __init__(self, pipeline: RAGPipeline):
        self.pipeline = pipeline

    def evaluate(
        self, samples: list[EvalSample], k_values: list[int] | None = None
    ) -> dict:
        k_values = k_values or self.pipeline.settings.evaluation.k_values
        maxk = max(k_values)
        agg_recall = {k: [] for k in k_values}
        agg_prec = {k: [] for k in k_values}
        rr_list: list[float] = []
        faith_list, ctxp_list, ansrel_list = [], [], []
        ground_list, halluc_list = [], []
        per_sample = []

        # A document can be referenced by its internal doc_id (hash) or by its
        # human-readable source filename (e.g. "GRAP_2023.md"). Citations and
        # every other API surface expose `source`, so callers naturally pass
        # filenames here. Resolve both sides to the internal doc_id so recall /
        # precision / MRR match regardless of which identifier was supplied.
        id_by_source = {c.source: c.doc_id for c in self.pipeline.store.all_chunks()}
        known_ids = set(id_by_source.values())

        def _canonical(ref: str) -> str:
            if ref in known_ids:
                return ref
            return id_by_source.get(ref, ref)

        for s in samples:
            chunks = self.pipeline.retrieve(s.question, top_k=maxk)
            retrieved_ids = [c.chunk.doc_id for c in chunks]
            relevant = {_canonical(r) for r in s.relevant_doc_ids}
            contexts = [c.chunk.text for c in chunks]

            row: dict = {"question": s.question}
            if relevant:
                for k in k_values:
                    r = recall_at_k(retrieved_ids, relevant, k)
                    p = precision_at_k(retrieved_ids, relevant, k)
                    agg_recall[k].append(r)
                    agg_prec[k].append(p)
                    row[f"recall@{k}"] = round(r, 4)
                    row[f"precision@{k}"] = round(p, 4)
                rr = reciprocal_rank(retrieved_ids, relevant)
                rr_list.append(rr)
                row["reciprocal_rank"] = round(rr, 4)

            ans = self.pipeline.ask(s.question, top_k=maxk)
            ctx_joined = "\n".join(contexts)
            faith = faithfulness(ans.answer, ctx_joined) if not ans.refused else 1.0
            ctxp = context_precision(s.question, contexts)
            ansrel = answer_relevance(s.question, ans.answer) if not ans.refused else 0.0
            ground = groundedness(ans.answer, bool(ans.citations), faith)
            halluc = hallucination_rate(faith) if not ans.refused else 0.0

            faith_list.append(faith)
            ctxp_list.append(ctxp)
            ansrel_list.append(ansrel)
            ground_list.append(ground)
            halluc_list.append(halluc)

            row.update(
                refused=ans.refused, confidence=ans.confidence,
                faithfulness=round(faith, 4), context_precision=round(ctxp, 4),
                answer_relevance=round(ansrel, 4), groundedness=ground,
                hallucination_rate=halluc,
            )
            per_sample.append(row)

        def mean(xs: list[float]) -> float:
            return round(sum(xs) / len(xs), 4) if xs else 0.0

        retrieval_metrics: dict[str, float] = {}
        for k in k_values:
            retrieval_metrics[f"recall@{k}"] = mean(agg_recall[k])
            retrieval_metrics[f"precision@{k}"] = mean(agg_prec[k])
        retrieval_metrics["mrr"] = mean(rr_list)

        generation_metrics = {
            "faithfulness": mean(faith_list),
            "context_precision": mean(ctxp_list),
            "answer_relevance": mean(ansrel_list),
            "groundedness": mean(ground_list),
            "hallucination_rate": mean(halluc_list),
        }
        return {
            "num_samples": len(samples),
            "retrieval_metrics": retrieval_metrics,
            "generation_metrics": generation_metrics,
            "per_sample": per_sample,
        }

    def report(self, samples: list[EvalSample], k_values: list[int] | None = None) -> str:
        result = self.evaluate(samples, k_values)
        lines = ["# VayuLens RAG Evaluation Report", ""]
        lines.append(f"Samples: {result['num_samples']}\n")
        lines.append("## Retrieval Metrics")
        for k, v in result["retrieval_metrics"].items():
            lines.append(f"- {k}: {v}")
        lines.append("\n## Generation Metrics")
        for k, v in result["generation_metrics"].items():
            lines.append(f"- {k}: {v}")
        return "\n".join(lines)
