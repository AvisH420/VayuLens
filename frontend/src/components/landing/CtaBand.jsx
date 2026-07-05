// Closing band: a slow shader-gradient wash in the site's own colors under
// the final call to action. The WebGL surface mounts shortly after page load
// (well before the band is reached) so it is already rendering when the user
// arrives; without WebGL a static CSS wash stands in.

import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { webglAvailable } from "./webgl.js";

const ShaderWash = lazy(() => import("./ShaderWash.jsx"));

export default function CtaBand({ reduced }) {
  const [on, setOn] = useState(false);
  const canGL = useMemo(webglAvailable, []);

  useEffect(() => {
    if (!canGL) return undefined;
    const t = setTimeout(() => setOn(true), 1800);
    return () => clearTimeout(t);
  }, [canGL]);

  return (
    <section className="cta-band-wrap">
      <div className="cta-band">
        {on && (
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
