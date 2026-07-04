// Lens cursor for the dashboard. A thin glass ring sits exactly at the
// pointer (no lag) and acts like an actual lens: it saturates what is under
// it, and when the map reports a cell beneath ("lens:probe" events from
// MapView) a reading chip appears beside the ring. Over buttons it widens.
// Disabled for touch pointers and reduced motion.

import { useEffect, useRef, useState } from "react";
import { aqiBand } from "../../lib/aqi.js";

export default function LensCursor() {
  const ringRef = useRef(null);
  const [probe, setProbe] = useState(null);
  const [wide, setWide] = useState(false);
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    const coarse = window.matchMedia("(pointer: coarse)").matches;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (coarse || reduced) return;
    setEnabled(true);
    document.documentElement.classList.add("lens-active");

    const onMove = (e) => {
      const el = ringRef.current;
      if (el) el.style.transform = `translate(${e.clientX}px, ${e.clientY}px)`;
      const target = e.target;
      setWide(!!target.closest?.("button, a, [data-lens]"));
    };
    const onProbe = (e) => setProbe(e.detail);
    window.addEventListener("pointermove", onMove, { passive: true });
    window.addEventListener("lens:probe", onProbe);
    return () => {
      document.documentElement.classList.remove("lens-active");
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("lens:probe", onProbe);
    };
  }, []);

  if (!enabled) return null;

  const band = probe ? aqiBand(probe.aqi) : null;

  return (
    <div ref={ringRef} className="lens-ring-wrap" aria-hidden="true">
      <div className={`lens-ring ${wide ? "wide" : ""} ${probe ? "reading" : ""}`} />
      <div className="lens-dot" />
      {probe && !wide && (
        <div className="lens-chip">
          <span className="lens-chip-aqi" style={{ background: band.color }}>
            {probe.aqi}
          </span>
          <span className="lens-chip-text">
            {probe.ward}
            {probe.sub ? ` · ${probe.sub}` : ""}
          </span>
        </div>
      )}
    </div>
  );
}
