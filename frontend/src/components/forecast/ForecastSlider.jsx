// Forecast time slider: scrubs the 72 h horizon in 6 h steps. Drives the
// forecast and what-if map layers.

import { FC_STEP_HOURS, FC_STEPS } from "../../lib/mock.js";

export default function ForecastSlider({ hourIdx, onChange, label }) {
  const hours = hourIdx * FC_STEP_HOURS;
  return (
    <div className="fslider glass" data-lens="control">
      <span className="fslider-label">{label}</span>
      <input
        type="range"
        min={0}
        max={FC_STEPS - 1}
        step={1}
        value={hourIdx}
        onChange={(e) => onChange(+e.target.value)}
        aria-label="Forecast hour"
      />
      <div className="fslider-ticks">
        <span>now</span>
        <span>+24h</span>
        <span>+48h</span>
        <span>+72h</span>
      </div>
      <span className="fslider-value">{hours === 0 ? "now" : `+${hours} h`}</span>
    </div>
  );
}
