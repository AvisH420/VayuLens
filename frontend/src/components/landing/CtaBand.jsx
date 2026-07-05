// Closing band: a slow shader-gradient wash in the site's own colors under
// the final call to action. The WebGL surface is mounted only when the band
// nears the viewport and WebGL is actually available; otherwise a static
// CSS wash stands in.

import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { webglAvailable } from "./webgl.js";

const ShaderWash = lazy(() => import("./ShaderWash.jsx"));

export default function CtaBand({ reduced }) {
  const ref = useRef(null);
  const [near, setNear] = useState(false);
  const canGL = useMemo(webglAvailable, []);

  useEffect(() => {
    const el = ref.current;
    if (!el || !canGL) return undefined;
    const io = new IntersectionObserver(
      ([e]) => e.isIntersecting && setNear(true),
      { rootMargin: "600px" }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [canGL]);

  return (
    <section className="cta-band-wrap">
      <div className="cta-band" ref={ref}>
        {canGL && near && (
          <Suspense fallback={null}>
            <ShaderWash reduced={reduced} />
          </Suspense>
        )}
        <div className="cta-band-inner">
          <p className="eyebrow">Delhi and Panaji today. Any Indian city next.</p>
          <h2>Every city has a source mix. Name yours.</h2>
          <div className="cta-band-actions">
            <Link to="/app" className="btn btn-primary">
              Open the dashboard
              <ArrowRight size={16} strokeWidth={2.2} aria-hidden="true" />
            </Link>
            <a
              href="https://github.com/AvisH420/VayuLens"
              target="_blank"
              rel="noreferrer"
              className="btn btn-ghost"
            >
              Read the repository
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
