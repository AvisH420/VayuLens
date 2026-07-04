// Right side panel. Without a selection: city summary. With a selected cell:
// reading + uncertainty, source attribution, 72 h forecast (with scenario
// overlay when one is active), and grounded recommendations.

import { useEffect, useState } from "react";
import { aqiBand } from "../../lib/aqi.js";
import { getRecommendations } from "../../lib/api.js";
import SourceBars from "../charts/SourceBars.jsx";
import ForecastChart from "../charts/ForecastChart.jsx";

export default function CellPanel({ city, cell, scenario, onClose }) {
  const [recs, setRecs] = useState(null);

  useEffect(() => {
    setRecs(null);
    if (!cell) return;
    let live = true;
    getRecommendations(city.cfg.id, cell.cell_id).then((r) => live && setRecs(r));
    return () => {
      live = false;
    };
  }, [city, cell]);

  if (!cell) {
    const band = aqiBand(city.avgAqi);
    return (
      <aside className="side-panel glass">
        <p className="eyebrow">{city.cfg.name} · city mean</p>
        <div className="panel-hero">
          <span className="panel-aqi" style={{ color: band.color }}>{city.avgAqi}</span>
          <span className="chip">
            <span className="dot" style={{ background: band.color }} />
            {band.label}
          </span>
        </div>
        <p className="panel-note">
          {city.cells.length.toLocaleString()} grid cells · {city.cfg.stations}{" "}
          CAAQMS stations · wind {city.cfg.wind.speed} m/s from {city.cfg.wind.dir}°
        </p>
        <div className="panel-block">
          <h4>City-wide source mix</h4>
          <SourceBars shares={city.avgShares} />
        </div>
        <p className="panel-hint">Click any cell for its attribution, forecast and actions.</p>
      </aside>
    );
  }

  const band = aqiBand(cell.aqi);
  const scenarioSeries = scenario?.results.get(cell.cell_id)?.scenario;

  return (
    <aside className="side-panel glass">
      <div className="panel-top">
        <div>
          <p className="eyebrow">{cell.ward}</p>
          <p className="panel-cellid">cell {cell.cell_id.replace("grid_", "")}</p>
        </div>
        <button className="drawer-close" onClick={onClose} aria-label="Close cell panel">×</button>
      </div>

      <div className="panel-hero">
        <span className="panel-aqi" style={{ color: band.color }}>{cell.aqi}</span>
        <div className="panel-hero-meta">
          <span className="chip">
            <span className="dot" style={{ background: band.color }} />
            {band.label}
          </span>
          <span className="panel-uncertainty">
            PM2.5 {cell.pm25} ±{cell.uncertainty} µg/m³ · quality {cell.quality_score}
          </span>
        </div>
      </div>

      <div className="panel-facts">
        <span>{cell.land_use_class}</span>
        <span>{cell.road_density} km/km² roads</span>
        {cell.industrial_flag && <span>registered industry</span>}
      </div>

      <div className="panel-block">
        <h4>Source attribution</h4>
        <SourceBars shares={cell.shares} confidence={cell.confidence} />
      </div>

      <div className="panel-block">
        <h4>Next 72 h{scenarioSeries ? " · with intervention" : ""}</h4>
        <ForecastChart
          baseline={cell.forecast}
          scenario={scenarioSeries}
          uncertainty={scenarioSeries ? 0 : (1 - cell.quality_score) * 0.4}
        />
      </div>

      <div className="panel-block">
        <h4>Recommended actions</h4>
        {!recs ? (
          <p className="panel-note">Ranking against the regulation corpus…</p>
        ) : (
          <ol className="rec-list">
            {recs.map((r, i) => (
              <li className="rec-item" key={i}>
                <div className="rec-head">
                  <span className="rec-priority">{r.priority_score.toFixed(2)}</span>
                  <p className="rec-action">{r.action}</p>
                </div>
                <p className="rec-just">{r.justification}</p>
                <span className="chip">{r.regulation_citation}</span>
              </li>
            ))}
          </ol>
        )}
      </div>
    </aside>
  );
}
