"""Run the RAG evaluation over data/eval/eval_set.json and write a report.

Usage:
    python scripts/run_eval.py
    python scripts/run_eval.py --out storage/eval_report.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.evaluation import EvalSample, Evaluator
from rag.logging_utils import get_logger
from rag.pipeline import RAGPipeline

log = get_logger("eval")


def _resolve_expected(pipeline: RAGPipeline, expected_docs: list[str]) -> list[str]:
    """Map expected source filenames to the doc_ids present in the index."""
    id_by_source = {c.source: c.doc_id for c in pipeline.store.all_chunks()}
    return [id_by_source[s] for s in expected_docs if s in id_by_source]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run VayuLens RAG evaluation")
    parser.add_argument("--eval-set", default="data/eval/eval_set.json")
    parser.add_argument("--out", default="storage/eval_report.md")
    args = parser.parse_args()

    pipeline = RAGPipeline()
    if pipeline.store.count() == 0:
        log.info("Index empty; ingesting corpus first.")
        pipeline.index_corpus()

    data = json.loads(Path(args.eval_set).read_text(encoding="utf-8"))
    samples = []
    for row in data["samples"]:
        expected = row.get("expected_docs", [])
        rel = row.get("relevant_doc_ids") or _resolve_expected(pipeline, expected)
        samples.append(
            EvalSample(
                question=row["question"], relevant_doc_ids=rel,
                ground_truth=row.get("ground_truth"),
            )
        )

    evaluator = Evaluator(pipeline)
    result = evaluator.evaluate(samples)
    report = evaluator.report(samples)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    (out.parent / "eval_result.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(report)
    log.info("Wrote report to %s", out)


if __name__ == "__main__":
    main()
