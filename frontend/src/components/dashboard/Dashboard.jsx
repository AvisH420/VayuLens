// Dashboard: full-bleed map with glass chrome. City + layer switching, the
// forecast time slider, cell inspection, the what-if drawer and the
// assistant drawer. Lens cursor everywhere.

import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { FlaskConical, MessageSquareQuote } from "lucide-react";
import MapView from "../map/MapView.jsx";
import CellPanel from "./CellPanel.jsx";
import WhatIfPanel from "../whatif/WhatIfPanel.jsx";
import ChatPanel from "../chat/ChatPanel.jsx";
import ForecastSlider from "../forecast/ForecastSlider.jsx";
import LensCursor from "../cursor/LensCursor.jsx";
import { buildCity } from "../../lib/mock.js";
import { getGrid } from "../../lib/api.js";
import { AQI_BANDS, SOURCES } from "../../lib/aqi.js";
import "./dashboard.css";

const LAYERS = [
  { key: "aqi", label: "Live AQI" },
  { key: "sources", label: "Sources" },
  { key: "forecast", label: "Forecast" },
];

export default function Dashboard() {
  const [params] = useSearchParams();
  const [cityId, setCityId] = useState("delhi");
  const [flyNonce, setFlyNonce] = useState(0);
  const [layer, setLayer] = useState("aqi");
  const [hourIdx, setHourIdx] = useState(0);
  const [selectedId, setSelectedId] = useState(null);
  const [scenario, setScenario] = useState(null);
  const [whatifOpen, setWhatifOpen] = useState(params.get("panel") === "whatif");
  const [chatOpen, setChatOpen] = useState(params.get("panel") === "chat");

  // Both grids live on the map at once; cityId just tracks the viewport.
  // Start with the instant client-side build so the map paints immediately,
  // then swap in the grid from the API (real snapshot data when
  // VITE_USE_MOCKS=false; identical mock otherwise). On error we keep the
  // initial build, so the dashboard never blanks.
  const [cities, setCities] = useState(() => ({
    delhi: buildCity("delhi"),
    panaji: buildCity("panaji"),
  }));

  useEffect(() => {
    let alive = true;
    Promise.all([getGrid("delhi"), getGrid("panaji")])
      .then(([delhi, panaji]) => {
        if (alive && delhi && panaji) setCities({ delhi, panaji });
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  const city = cities[cityId];

  // a selected cell may belong to either city
  const { cell, cellCity } = useMemo(() => {
    for (const c of Object.values(cities)) {
      const hit = c.cells.find((x) => x.cell_id === selectedId);
      if (hit) return { cell: hit, cellCity: c };
    }
    return { cell: null, cellCity: city };
  }, [cities, selectedId, city]);

  useEffect(() => {
    document.title = `VayuLens · ${city.cfg.name} grid`;
  }, [city]);

  const activeLayer = scenario ? "whatif" : layer;
  const sliderVisible = activeLayer === "forecast" || activeLayer === "whatif";

  // button: fly there. Panning there yourself does the same via onViewCity.
  const switchCity = (id) => {
    setCityId(id);
    setFlyNonce((n) => n + 1);
    setSelectedId(null);
  };

  const applyScenario = (result) => {
    setScenario(result);
    if (result) setHourIdx(8); // land on +48 h where the effect is legible
  };

  return (
    <div className="dashboard">
      <LensCursor />
      <MapView
        cities={cities}
        cityId={cityId}
        flyNonce={flyNonce}
        onViewCity={setCityId}
        layer={activeLayer}
        hourIdx={hourIdx}
        scenario={scenario}
        selectedId={selectedId}
        onSelect={setSelectedId}
      />

      <header className="dash-topbar glass">
        <Link to="/" className="wordmark">
          <span className="wordmark-ring" aria-hidden="true" />
          VayuLens
        </Link>

        <div className="seg" role="group" aria-label="City">
          {["delhi", "panaji"].map((id) => (
            <button
              key={id}
              className={cityId === id ? "active" : ""}
              onClick={() => switchCity(id)}
            >
              {id === "delhi" ? "Delhi" : "Panaji"}
            </button>
          ))}
        </div>

        <div className="seg" role="group" aria-label="Map layer">
          {LAYERS.map((l) => (
            <button
              key={l.key}
              className={!scenario && layer === l.key ? "active" : ""}
              onClick={() => {
                setLayer(l.key);
                setScenario(null);
                if (l.key !== "forecast") setHourIdx(0);
              }}
            >
              {l.label}
            </button>
          ))}
          {scenario && <button className="active">Δ What-if</button>}
        </div>

        <div className="dash-actions">
          <button
            className={`btn btn-ghost dash-action ${whatifOpen ? "on" : ""}`}
            onClick={() => {
              setWhatifOpen(!whatifOpen);
              setChatOpen(false);
            }}
          >
            <FlaskConical size={14} strokeWidth={2} aria-hidden="true" />
            What-if
          </button>
          <button
            className={`btn btn-ghost dash-action ${chatOpen ? "on" : ""}`}
            onClick={() => {
              setChatOpen(!chatOpen);
              setWhatifOpen(false);
            }}
          >
            <MessageSquareQuote size={14} strokeWidth={2} aria-hidden="true" />
            Assistant
          </button>
        </div>
      </header>

      {/* legend */}
      <div className="legend glass">
        {activeLayer === "sources" ? (
          SOURCES.map((s) => (
            <span className="legend-item" key={s.key}>
              <span className="dot" style={{ background: s.color }} />
              {s.label}
            </span>
          ))
        ) : activeLayer === "whatif" ? (
          <>
            <span className="legend-item">
              <span className="legend-swatch" style={{ background: "#3987e5" }} />
              improves
            </span>
            <span className="legend-item">
              <span className="legend-swatch" style={{ background: "#edece6" }} />
              unchanged
            </span>
            <span className="legend-item">
              <span className="legend-swatch" style={{ background: "#c74436" }} />
              worsens
            </span>
          </>
        ) : (
          AQI_BANDS.map((b) => (
            <span className="legend-item" key={b.label}>
              <span className="legend-swatch" style={{ background: b.color }} />
              {b.label}
            </span>
          ))
        )}
      </div>

      {sliderVisible && (
        <ForecastSlider
          hourIdx={hourIdx}
          onChange={setHourIdx}
          label={scenario ? "Δ field" : "Forecast"}
        />
      )}

      <CellPanel
        city={cell ? cellCity : city}
        cell={cell}
        scenario={scenario}
        onClose={() => setSelectedId(null)}
      />

      {whatifOpen && (
        <WhatIfPanel
          city={city}
          scenario={scenario}
          onScenario={applyScenario}
          onClose={() => setWhatifOpen(false)}
        />
      )}
      {chatOpen && <ChatPanel city={city} onClose={() => setChatOpen(false)} />}
    </div>
  );
}
