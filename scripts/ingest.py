"""CLI to (re)build the vector index from the data/ corpus.

Usage:
    python scripts/ingest.py            # index data/regulations + data/interventions
    python scripts/ingest.py --dir path # index a specific directory
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.logging_utils import get_logger
from rag.pipeline import RAGPipeline

log = get_logger("ingest")


def main() -> None:
    parser = argparse.ArgumentParser(description="VayuLens corpus ingestion")
    parser.add_argument("--dir", help="Specific directory to ingest", default=None)
    args = parser.parse_args()

    pipeline = RAGPipeline()
    if args.dir:
        count = pipeline.index_directory(args.dir)
        log.info("Indexed %d chunks from %s", count, args.dir)
    else:
        detail = pipeline.index_corpus()
        log.info("Indexed corpus: %s (total=%d)", detail, sum(detail.values()))
    log.info("Vector store now holds %d chunks.", pipeline.store.count())


if __name__ == "__main__":
    main()
