// 72 h AQI forecast line chart (SVG). One series by default; a second
// "scenario" series renders as emphasis against the grayed baseline.
// Crosshair + tooltip on hover, direct labels at line ends, hairline grid.

import { useMemo, useRef, useState } from "react";
import { FC_STEP_HOURS } from "../../lib/mock.js";

const W = 560;
const H = 210;
const PAD = { top: 16, right: 74, bottom: 26, left: 38 };

export default function ForecastChart({ baseline, scenario, uncertainty = 0 }) {
  const [hover, setHover] = useState(null);
  const svgRef = useRef(null);

  const { scaleX, scaleY, ticksY } = useMemo(() => {
    const all = [...baseline, ...(scenario ?? [])];
    const max = Math.max(...all) * 1.12;
    const min = Math.max(0, Math.min(...all) * 0.82);
    const sx = (i) =>
      PAD.left + (i / (baseline.length - 1)) * (W - PAD.left - PAD.right);
    const sy = (v) =>
      PAD.top + (1 - (v - min) / (max - min)) * (H - PAD.top - PAD.bottom);
    const step = Math.max(20, Math.round((max - min) / 3 / 20) * 20);
    const ticks = [];
    for (let v = Math.ceil(min / step) * step; v <= max; v += step) ticks.push(v);
    return { scaleX: sx, scaleY: sy, ticksY: ticks };
  }, [baseline, scenario]);

  const path = (vals) =>
    vals.map((v, i) => `${i ? "L" : "M"}${scaleX(i).toFixed(1)},${scaleY(v).toFixed(1)}`).join(" ");

  const band = useMemo(() => {
    if (!uncertainty) return null;
    const up = baseline.map((v, i) => `${i ? "L" : "M"}${scaleX(i).toFixed(1)},${scaleY(v * (1 + uncertainty)).toFixed(1)}`);
    const dn = [...baseline]
      .map((v, i) => ({ v, i }))
      .reverse()
      .map(({ v, i }) => `L${scaleX(i).toFixed(1)},${scaleY(v * (1 - uncertainty)).toFixed(1)}`);
    return [...up, ...dn, "Z"].join(" ");
  }, [baseline, uncertainty, scaleX, scaleY]);

  const onMove = (e) => {
    const rect = svgRef.current.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * W;
    const i = Math.round(
      ((x - PAD.left) / (W - PAD.left - PAD.right)) * (baseline.length - 1)
    );
    setHover(Math.max(0, Math.min(baseline.length - 1, i)));
  };

  const hourLabel = (i) => (i === 0 ? "now" : `+${i * FC_STEP_HOURS}h`);
  const hasScenario = !!scenario;
  const baseColor = hasScenario ? "#9aa8a0" : "#2f7d4f";

  return (
    <div className="fchart">
      {hasScenario && (
        <div className="fchart-legend">
          <span className="chip"><span className="dot" style={{ background: baseColor }} />Baseline</span>
          <span className="chip"><span className="dot" style={{ background: "#2f7d4f" }} />With intervention</span>
        </div>
      )}
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
        role="img"
        aria-label="AQI forecast over the next 72 hours"
      >
        {ticksY.map((v) => (
          <g key={v}>
            <line x1={PAD.left} x2={W - PAD.right} y1={scaleY(v)} y2={scaleY(v)} stroke="rgba(24,36,32,0.08)" />
            <text x={PAD.left - 8} y={scaleY(v) + 4} textAnchor="end" fontSize="10.5" fill="#75837a">{v}</text>
          </g>
        ))}
        {[0, 4, 8, 12].map((i) => (
          <text key={i} x={scaleX(i)} y={H - 8} textAnchor="middle" fontSize="10.5" fill="#75837a">
            {hourLabel(i)}
          </text>
        ))}

        {band && <path d={band} fill="rgba(47,125,79,0.10)" />}
        <path d={path(baseline)} fill="none" stroke={baseColor} strokeWidth="2" strokeLinejoin="round" />
        {hasScenario && (
          <path d={path(scenario)} fill="none" stroke="#2f7d4f" strokeWidth="2" strokeLinejoin="round" />
        )}

        {/* direct labels at line ends */}
        <text x={scaleX(baseline.length - 1) + 8} y={scaleY(baseline.at(-1)) + 4} fontSize="11" fontWeight="600" fill="#45544c">
          {baseline.at(-1)}{hasScenario ? " base" : ""}
        </text>
        {hasScenario && (
          <text x={scaleX(scenario.length - 1) + 8} y={scaleY(scenario.at(-1)) + 4} fontSize="11" fontWeight="600" fill="#1c5638">
            {scenario.at(-1)}
          </text>
        )}

        {hover !== null && (
          <g>
            <line x1={scaleX(hover)} x2={scaleX(hover)} y1={PAD.top} y2={H - PAD.bottom} stroke="rgba(24,36,32,0.25)" strokeDasharray="3 3" />
            <circle cx={scaleX(hover)} cy={scaleY(baseline[hover])} r="4" fill={baseColor} stroke="#fff" strokeWidth="2" />
            {hasScenario && (
              <circle cx={scaleX(hover)} cy={scaleY(scenario[hover])} r="4" fill="#2f7d4f" stroke="#fff" strokeWidth="2" />
            )}
          </g>
        )}
      </svg>
      {hover !== null && (
        <div className="fchart-tip glass">
          <strong>{hourLabel(hover)}</strong>
          <span>AQI {baseline[hover]}{hasScenario ? ` → ${scenario[hover]}` : ""}</span>
        </div>
      )}
    </div>
  );
}
