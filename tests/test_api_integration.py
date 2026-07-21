"""Integration tests hitting the FastAPI app via TestClient."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from decision.api.app import app

    c = TestClient(app)
    c.post("/v1/ingest", json={})
    return c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["indexed_chunks"] > 0


def test_ask_endpoint(client):
    r = client.post("/v1/ask", json={"question": "construction ban GRAP Stage III"})
    assert r.status_code == 200
    body = r.json()
    assert body["grounded"] is True
    assert body["citations"]


def test_retrieve_endpoint(client):
    r = client.post("/v1/retrieve", json={"query": "industrial closure", "top_k": 3})
    assert r.status_code == 200
    assert len(r.json()["results"]) <= 3


def test_recommend_endpoint(client):
    r = client.post("/v1/recommend", json={
        "location": {"name": "Anand Vihar"},
        "current_aqi": 432,
        "source_attribution": [{"source": "construction", "contribution_pct": 42}],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["grap_stage"] == "Stage III"
    assert body["recommendations"]


def test_prioritize_endpoint(client):
    r = client.post("/v1/prioritize", json={
        "current_aqi": 432,
        "targets": [
            {"target_id": "A", "name": "A", "category": "industrial",
             "pollution_contribution_pct": 35, "population_exposed": 180000},
            {"target_id": "B", "name": "B", "category": "construction",
             "pollution_contribution_pct": 10, "population_exposed": 1000},
        ],
    })
    assert r.status_code == 200
    ranked = r.json()["ranked_targets"]
    assert ranked[0]["rank"] == 1


def test_advisory_endpoint(client):
    r = client.post("/v1/advisory", json={
        "location": "Anand Vihar", "current_aqi": 432,
        "audiences": ["citizen"], "languages": ["en", "hi"],
    })
    assert r.status_code == 200
    assert len(r.json()["advisories"]) == 2


def test_evaluate_endpoint(client):
    r = client.post("/v1/evaluate", json={
        "samples": [{"question": "construction ban", "relevant_doc_ids": []}],
    })
    assert r.status_code == 200
    body = r.json()
    assert "faithfulness" in body["generation_metrics"]
