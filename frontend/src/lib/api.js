// API client. Route names and shapes mirror api/gateway.py one-to-one.
// Mocks (lib/mock.js) are the default; run with VITE_USE_MOCKS=false and
// the same call sites hit the FastAPI gateway through the Vite /api proxy
// (see vite.config.js — start it with: uvicorn api.gateway:app --reload).

import {
  buildCity,
  runScenario,
  recommendationsFor,
  chatAnswer,
} from "./mock.js";

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS !== "false";

// Where the gateway lives. Defaults to "/api", which the Vite dev proxy
// forwards to localhost:8000. In production set VITE_API_BASE to the
// deployed gateway origin (e.g. https://vayulens-api.onrender.com) — the
// browser then calls it directly and the gateway's CORS_ORIGINS must list
// the frontend domain. Trailing slashes are trimmed so the joined path
// never ends up with a double slash.
const API_BASE = (import.meta.env.VITE_API_BASE || "/api").replace(/\/+$/, "");

const latency = () =>
  new Promise((r) => setTimeout(r, 120 + Math.random() * 180));

async function real(path, opts) {
  const res = await fetch(`${API_BASE}${path}`, opts);
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

export async function getGrid(cityId) {
  if (!USE_MOCKS) return real(`/grid?city=${cityId}`);
  await latency();
  return buildCity(cityId);
}

export async function getAttribution(cityId, cellId) {
  if (!USE_MOCKS) return real(`/attribution/${cellId}`);
  await latency();
  const cell = buildCity(cityId).cells.find((c) => c.cell_id === cellId);
  return { cell_id: cellId, sources: cell.shares, confidence: cell.confidence };
}

export async function getForecast(cityId, cellId) {
  if (!USE_MOCKS) {
    // gateway returns contracts/forecast.py points [{t, aqi}]
    const f = await real(`/forecast/${cellId}`);
    return { cell_id: f.cell_id, horizon: f.horizon.map((p) => Math.round(p.aqi)) };
  }
  await latency();
  const cell = buildCity(cityId).cells.find((c) => c.cell_id === cellId);
  return { cell_id: cellId, horizon: cell.forecast };
}

export async function postSimulate(cityId, scenario) {
  if (!USE_MOCKS) {
    const sim = await real(`/simulate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ city: cityId, ...scenario }),
    });
    // results arrive as a plain JSON object; downstream expects a Map
    return { ...sim, results: new Map(Object.entries(sim.results)) };
  }
  await new Promise((r) => setTimeout(r, 650 + Math.random() * 350));
  return runScenario(cityId, scenario);
}

export async function getRecommendations(cityId, cellId) {
  if (!USE_MOCKS) return real(`/recommendations/${cellId}`);
  await latency();
  const cell = buildCity(cityId).cells.find((c) => c.cell_id === cellId);
  return recommendationsFor(cell);
}

export async function postChat(query) {
  if (!USE_MOCKS)
    return real(`/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
  await new Promise((r) => setTimeout(r, 700 + Math.random() * 500));
  return chatAnswer(query);
}
