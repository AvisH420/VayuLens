// Capability grid. Hairline-divided 4x2, one icon per capability, with a
// quiet accent bar that appears on hover. Adapted from the sandbox
// features-section pattern, restyled to the VayuLens tokens.

import {
  Crosshair,
  ChartLine,
  FlaskConical,
  MessageSquareQuote,
  Satellite,
  Languages,
  Gauge,
  Wind,
} from "lucide-react";

const FEATURES = [
  {
    icon: Crosshair,
    title: "Source attribution",
    body: "Each cell separates its load into traffic, construction, industry, burning and dust, so a reading becomes an address.",
  },
  {
    icon: ChartLine,
    title: "72-hour forecasts",
    body: "Dispersion physics plus a learned residual, scored against a persistence baseline, cell by cell.",
  },
  {
    icon: FlaskConical,
    title: "What-if simulator",
    body: "Rerun the model under a GRAP measure and price the intervention in AQI before anyone signs the order.",
  },
  {
    icon: MessageSquareQuote,
    title: "Grounded assistant",
    body: "Answers cite GRAP, NCAP and CPCB passages, and abstain when retrieval is weak instead of guessing.",
  },
  {
    icon: Satellite,
    title: "Fused observation",
    body: "CAAQMS stations, Sentinel-5P columns and MODIS optical depth reconciled onto one 1 km grid.",
  },
  {
    icon: Wind,
    title: "Dispersion aware",
    body: "Wind decides where a plume travels next; the grid reads Open-Meteo fields natively.",
  },
  {
    icon: Gauge,
    title: "Honest uncertainty",
    body: "Every number ships with a quality score, and forecast bands widen where the model deserves less trust.",
  },
  {
    icon: Languages,
    title: "Citizen advisories",
    body: "Ward-level guidance in English, Hindi and Konkani, generated from the same live grid.",
  },
];

export default function FeatureGrid() {
  return (
    <div className="feature-grid">
      {FEATURES.map(({ icon: Icon, title, body }, i) => (
        <div className={`feature-cell ${i < 4 ? "top-row" : ""}`} key={title}>
          <span className="feature-accent" aria-hidden="true" />
          <Icon className="feature-icon" size={22} strokeWidth={1.7} />
          <h3 className="feature-title">{title}</h3>
          <p className="feature-body">{body}</p>
        </div>
      ))}
    </div>
  );
}
