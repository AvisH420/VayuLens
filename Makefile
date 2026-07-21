# VayuLens Role 3 — developer convenience targets
.PHONY: install install-full ingest run eval test docker lint clean

install:
	pip install -r requirements.txt

install-full:
	pip install -r requirements-full.txt

ingest:
	python scripts/ingest.py

run:
	uvicorn decision.api.app:app --host 0.0.0.0 --port 8000 --reload

eval:
	python scripts/run_eval.py

test:
	pytest -q

docker:
	docker compose up --build

lint:
	ruff check rag decision scripts tests || true

clean:
	rm -rf storage .pytest_cache **/__pycache__
