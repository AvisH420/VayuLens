// CPCB AQI bands (National AQI, IND standard) with screen-tuned colors.
// Colors validated for adjacent-CVD separation; always rendered with a
// labeled legend or value, never color alone.

export const AQI_BANDS = [
  { max: 50, label: "Good", color: "#2e8b47" },
  { max: 100, label: "Satisfactory", color: "#93c243" },
  { max: 200, label: "Moderate", color: "#cf9a12" },
  { max: 300, label: "Poor", color: "#dd7233" },
  { max: 400, label: "Very poor", color: "#c74436" },
  { max: 500, label: "Severe", color: "#7e3348" },
];

export function aqiBand(aqi) {
  const v = Math.max(0, Math.min(500, aqi));
  return AQI_BANDS.find((b) => v <= b.max) ?? AQI_BANDS[AQI_BANDS.length - 1];
}

export const SOURCES = [
  { key: "traffic", label: "Traffic", color: "#4a6fb5" },
  { key: "construction", label: "Construction", color: "#b87700" },
  { key: "industry", label: "Industry", color: "#7a5bc7" },
  { key: "burning", label: "Burning", color: "#c14a35" },
  { key: "dust", label: "Dust", color: "#ab8d33" },
];

export const SOURCE_COLOR = Object.fromEntries(
  SOURCES.map((s) => [s.key, s.color])
);

export function dominantSource(shares) {
  return SOURCES.reduce((best, s) =>
    (shares[s.key] ?? 0) > (shares[best.key] ?? 0) ? s : best
  );
}

// MapLibre step expression for coloring by an AQI-valued property.
export function aqiStepExpression(prop) {
  return [
    "step",
    ["get", prop],
    "#2e8b47",
    51, "#93c243",
    101, "#cf9a12",
    201, "#dd7233",
    301, "#c74436",
    401, "#7e3348",
  ];
}
