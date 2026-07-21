#!/usr/bin/env bash
# Example API requests for the VayuLens Decision Intelligence Layer.
# Start the server first:  uvicorn decision.api.app:app --reload
BASE=${BASE:-http://localhost:8000}

echo "== Health ==""" ; curl -s $BASE/health | jq .

echo "== Ingest corpus =="
curl -s -X POST $BASE/v1/ingest -H 'Content-Type: application/json' -d '{}' | jq .

echo "== Ask (grounded QA) =="
curl -s -X POST $BASE/v1/ask -H 'Content-Type: application/json' -d '{
  "question": "What restrictions apply to construction under GRAP Stage III?"
}' | jq .

echo "== Ask (legal reasoning) =="
curl -s -X POST $BASE/v1/ask -H 'Content-Type: application/json' -d '{
  "question": "Which industries must close under the Air Act when directed?",
  "task": "legal"
}' | jq .

echo "== Retrieve =="
curl -s -X POST $BASE/v1/retrieve -H 'Content-Type: application/json' -d '{
  "query": "industrial closure unapproved fuel", "top_k": 4
}' | jq .

echo "== Recommend (agentic decision) =="
curl -s -X POST $BASE/v1/recommend -H 'Content-Type: application/json' -d '{
  "location": {"name": "Anand Vihar", "population": 250000, "hospitals_nearby": 3, "schools_nearby": 12},
  "current_aqi": 432,
  "source_attribution": [
    {"source": "construction", "contribution_pct": 42},
    {"source": "traffic", "contribution_pct": 28},
    {"source": "industry", "contribution_pct": 18}
  ],
  "forecast": [{"horizon_hours": 24, "aqi": 455}]
}' | jq .

echo "== Prioritize (enforcement ranking) =="
curl -s -X POST $BASE/v1/prioritize -H 'Content-Type: application/json' -d '{
  "current_aqi": 432,
  "targets": [
    {"target_id": "IC1", "name": "Wazirpur Industrial Cluster", "category": "industrial",
     "pollution_contribution_pct": 35, "population_exposed": 180000, "hospitals_nearby": 2,
     "schools_nearby": 8, "forecast_trend": 20},
    {"target_id": "CS1", "name": "Dwarka Expressway Site", "category": "construction",
     "pollution_contribution_pct": 42, "population_exposed": 90000, "hospitals_nearby": 1,
     "schools_nearby": 5, "forecast_trend": 15}
  ]
}' | jq .

echo "== Advisory (multilingual) =="
curl -s -X POST $BASE/v1/advisory -H 'Content-Type: application/json' -d '{
  "location": "Anand Vihar", "current_aqi": 432,
  "audiences": ["citizen", "hospital", "outdoor_worker"],
  "languages": ["en", "hi", "ta"]
}' | jq .

echo "== Evaluate =="
curl -s -X POST $BASE/v1/evaluate -H 'Content-Type: application/json' -d '{
  "samples": [{"question": "construction ban GRAP Stage III", "relevant_doc_ids": []}]
}' | jq .
