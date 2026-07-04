// What-if drawer: define an intervention, run POST /simulate (mocked),
// read the result as stat tiles while the map shows the AQI delta field.

import { useState } from "react";
import { ACTIONS } from "../../lib/mock.js";
import { postSimulate } from "../../lib/api.js";

export default function WhatIfPanel({ city, scenario, onScenario, onClose }) {
  const [action, setAction] = useState("halt_construction");
  const [ward, setWard] = useState("all");
  const [days, setDays] = useState(3);
  const [busy, setBusy] = useState(false);

  const run = async () => {
    setBusy(true);
    const result = await postSimulate(city.cfg.id, { action, ward, days });
    setBusy(false);
    onScenario(result);
  };

  return (
    <aside className="drawer drawer-left glass">
      <div className="drawer-head">
        <h3>What-if</h3>
        <button className="drawer-close" onClick={onClose} aria-label="Close what-if panel">×</button>
      </div>
      <p className="drawer-sub">
        Rerun the dispersion model under an intervention and see what it buys,
        in AQI, before anyone signs the order.
      </p>

      <label className="field-label">Intervention</label>
      <div className="action-list">
        {Object.entries(ACTIONS).map(([key, a]) => (
          <button
            key={key}
            className={`action-item ${key === action ? "active" : ""}`}
            onClick={() => setAction(key)}
          >
            <span className="action-title">{a.label}</span>
            <span className="action-detail">{a.detail}</span>
            <span className="action-cite">{a.citation}</span>
          </button>
        ))}
      </div>

      <label className="field-label" htmlFor="wif-zone">Zone</label>
      <select
        id="wif-zone"
        className="field-select"
        value={ward}
        onChange={(e) => setWard(e.target.value)}
      >
        <option value="all">Whole city · {city.cfg.name}</option>
        {city.cfg.wards.map((w) => (
          <option key={w.name} value={w.name}>{w.name}</option>
        ))}
      </select>

      <label className="field-label" htmlFor="wif-days">
        Duration · {days} {days === 1 ? "day" : "days"}
      </label>
      <input
        id="wif-days"
        type="range"
        min={1}
        max={7}
        value={days}
        onChange={(e) => setDays(+e.target.value)}
      />

      <button className="btn btn-primary drawer-run" onClick={run} disabled={busy}>
        {busy ? "Recomputing dispersion…" : "Run scenario"}
      </button>

      {scenario && (
        <div className="sim-result">
          <div className="sim-tiles">
            <div className="sim-tile">
              <span className="sim-tile-value">{scenario.summary.avgDelta48}</span>
              <span className="sim-tile-label">avg ΔAQI in zone at +48 h</span>
            </div>
            <div className="sim-tile">
              <span className="sim-tile-value">{scenario.summary.peakDelta}</span>
              <span className="sim-tile-label">peak cell improvement</span>
            </div>
            <div className="sim-tile">
              <span className="sim-tile-value">~{scenario.summary.onsetHours} h</span>
              <span className="sim-tile-label">to visible effect</span>
            </div>
          </div>
          <p className="sim-note">
            The map now shows the delta field. Blue cells improve; scrub the
            time slider to watch the effect ramp in.
          </p>
          <button className="btn btn-ghost" onClick={() => onScenario(null)}>
            Clear scenario
          </button>
        </div>
      )}
    </aside>
  );
}
