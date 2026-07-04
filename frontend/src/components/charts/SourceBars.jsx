// Source-attribution bars: one thin rounded bar per source, value as text
// beside the label (never inside the fill), fixed category order and colors.

import { SOURCES } from "../../lib/aqi.js";

export default function SourceBars({ shares, confidence }) {
  const max = Math.max(...SOURCES.map((s) => shares[s.key] ?? 0));
  return (
    <div className="srcbars">
      {SOURCES.map((s) => {
        const v = shares[s.key] ?? 0;
        return (
          <div className="srcbar-row" key={s.key}>
            <span className="dot" style={{ background: s.color }} />
            <span className="srcbar-label">{s.label}</span>
            <div className="srcbar-track">
              <span
                className="srcbar-fill"
                style={{ width: `${(v / max) * 100}%`, background: s.color }}
              />
            </div>
            <span className="srcbar-val">{Math.round(v * 100)}%</span>
          </div>
        );
      })}
      {confidence != null && (
        <div className="srcbar-conf">
          <span>Apportionment confidence</span>
          <div className="meter"><span style={{ width: `${confidence * 100}%` }} /></div>
          <span className="srcbar-val">{Math.round(confidence * 100)}%</span>
        </div>
      )}
    </div>
  );
}
