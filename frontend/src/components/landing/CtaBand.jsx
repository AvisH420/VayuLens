// Closing band. Deliberately owns no WebGL of its own: the band is
// translucent glass over the page-wide shader wash, so its background is
// already animating when the user arrives — nothing mounts, loads or fades
// on approach (a per-section canvas popped in visibly no matter how it was
// preloaded; see CLAUDE.md).

import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

export default function CtaBand() {
  return (
    <section className="cta-band-wrap">
      <div className="cta-band">
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
