// API client. Route names and shapes mirror api/gateway.py one-to-one.
// USE_MOCKS serves everything from lib/mock.js; flip it off once the
// FastAPI gateway is live and the same call sites hit /api/* unchanged.

import {
  buildCity,
  runScenario,
  recommendationsFor,
  chatAnswer,
} from "./mock.js";

const USE_MOCKS = true;

const latency = () =>
  new Promise((r) => setTimeout(r, 120 + Math.random() * 180));

async function real(path, opts) {
  const res = await fetch(`/api${path}`, opts);
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
  if (!USE_MOCKS) return real(`/forecast/${cellId}`);
  await latency();
  const cell = buildCity(cityId).cells.find((c) => c.cell_id === cellId);
  return { cell_id: cellId, horizon: cell.forecast };
}

export async function postSimulate(cityId, scenario) {
  if (!USE_MOCKS)
    return real(`/simulate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ city: cityId, ...scenario }),
    });
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
