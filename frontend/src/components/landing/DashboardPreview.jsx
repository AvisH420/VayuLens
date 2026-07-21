// The operations view, shown as a screen that straightens out of a shallow
// perspective tilt as it scrolls in (sandbox container-scroll pattern,
// driven by the same manual rAF progress the hero uses — no useScroll).

import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { motion, useMotionValue, useTransform } from "motion/react";

export default function DashboardPreview({ reduced }) {
  const ref = useRef(null);
  const p = useMotionValue(reduced ? 1 : 0);

  useEffect(() => {
    if (reduced) return undefined;
    let raf = 0;
    const update = () => {
      raf = 0;
      const el = ref.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      const vh = window.innerHeight;
      // 0 when the card's top enters the viewport, 1 by its upper third
      p.set(Math.min(1, Math.max(0, (vh - r.top) / (vh * 0.72))));
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, [reduced, p]);

  const rotateX = useTransform(p, [0, 1], [16, 0]);
  const scale = useTransform(p, [0, 1], [0.94, 1]);
  const shadowA = useTransform(p, [0, 1], [0.12, 0.3]);
  const boxShadow = useTransform(
    shadowA,
    (a) => `0 42px 90px -38px rgba(24, 36, 32, ${a.toFixed(3)})`
  );

  return (
    <div className="preview-persp" ref={ref}>
      <motion.div
        className="preview-frame"
        style={reduced ? undefined : { rotateX, scale, boxShadow }}
      >
        <div className="preview-chrome" aria-hidden="true">
          <span />
          <span />
          <span />
          <em>vayulens.app/grid</em>
        </div>
        <img
          src="/dashboard_preview.png"
          alt="VayuLens dashboard: the Delhi grid colored by live AQI, with the source attribution panel open"
          loading="lazy"
        />
      </motion.div>
      <Link to="/app" className="btn btn-primary preview-cta">
        Open the live grid
        <ArrowRight size={16} strokeWidth={2.2} aria-hidden="true" />
      </Link>
    </div>
  );
}
