// India as a dotted grid (dotted-map), with the two pilot deployments
// marked and a survey line drawn between them when the section scrolls
// into view. Adapted from the sandbox world-map component; light theme,
// subject colors, no basemap tiles.

import { useMemo, useRef, useEffect, useState } from "react";
import DottedMap from "dotted-map";

const CITIES = [
  { id: "delhi", label: "Delhi", lat: 28.61, lng: 77.21 },
  { id: "panaji", label: "Panaji", lat: 15.49, lng: 73.83 },
];

export default function IndiaMap() {
  const { src, viewBox, pins } = useMemo(() => {
    const map = new DottedMap({ height: 80, grid: "diagonal", countries: ["IND"] });
    for (const c of CITIES) {
      map.addPin({
        lat: c.lat,
        lng: c.lng,
        data: c.id,
        svgOptions: { color: "#1c5638", radius: 0.55 },
      });
    }
    const svg = map.getSVG({
      radius: 0.32,
      color: "rgba(24, 36, 32, 0.22)",
      shape: "circle",
      backgroundColor: "transparent",
    });
    const vb = svg.match(/viewBox="([^"]+)"/)?.[1] ?? "0 0 100 80";
    const points = map.getPoints().filter((p) => p.data);
    const pinsById = Object.fromEntries(
      CITIES.map((c) => {
        const p = points.find((pt) => pt.data === c.id);
        return [c.id, { ...c, x: p?.x ?? 0, y: p?.y ?? 0 }];
      })
    );
    return {
      src: `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`,
      viewBox: vb,
      pins: pinsById,
    };
  }, []);

  // draw the connecting line once, when the map first becomes visible
  const rootRef = useRef(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = rootRef.current;
    if (!el) return undefined;
    const io = new IntersectionObserver(
      ([e]) => e.isIntersecting && setSeen(true),
      { threshold: 0.35 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const d = pins.delhi;
  const p = pins.panaji;
  // bulge west over the Arabian Sea so the line doesn't cross the peninsula
  const path = `M ${d.x} ${d.y} Q ${Math.min(d.x, p.x) - 9} ${(d.y + p.y) / 2} ${p.x} ${p.y}`;

  return (
    <div className={`india-map ${seen ? "seen" : ""}`} ref={rootRef}>
      <img src={src} alt="Dotted map of India with Delhi and Panaji marked" draggable={false} />
      <svg viewBox={viewBox} aria-hidden="true">
        <path className="india-map-line" d={path} pathLength="1" />
        {Object.values(pins).map((c) => (
          <g key={c.id}>
            <circle className="india-map-pulse" cx={c.x} cy={c.y} r="1.1" />
            <text
              className="india-map-label"
              x={c.x + 2.4}
              y={c.y + (c.id === "delhi" ? -1 : 1.4)}
            >
              {c.label}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
