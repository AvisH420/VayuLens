// Full-width outline wordmark closing the footer. Adapted from the sandbox
// text-hover-effect: hairline stroke type, with a cursor-following radial
// mask that inks the stroke in the site greens on hover. Static (and still
// legible) without a pointer.

import { useRef, useState } from "react";
import { motion } from "motion/react";

export default function FooterWordmark() {
  const svgRef = useRef(null);
  const [hovered, setHovered] = useState(false);
  const [mask, setMask] = useState({ cx: "50%", cy: "50%" });

  const onMove = (e) => {
    const r = svgRef.current?.getBoundingClientRect();
    if (!r) return;
    setMask({
      cx: `${((e.clientX - r.left) / r.width) * 100}%`,
      cy: `${((e.clientY - r.top) / r.height) * 100}%`,
    });
  };

  return (
    <svg
      ref={svgRef}
      className="footer-wordmark"
      viewBox="0 0 640 110"
      preserveAspectRatio="xMidYMid meet"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onMouseMove={onMove}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="fw-ink" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="640" y2="110">
          <stop offset="0%" stopColor="var(--green-deep)" />
          <stop offset="55%" stopColor="var(--green)" />
          <stop offset="100%" stopColor="#7fa3b6" />
        </linearGradient>
        <motion.radialGradient
          id="fw-reveal"
          gradientUnits="userSpaceOnUse"
          r="26%"
          animate={mask}
          transition={{ duration: 0.25, ease: "easeOut" }}
        >
          <stop offset="0%" stopColor="white" />
          <stop offset="100%" stopColor="black" />
        </motion.radialGradient>
        <mask id="fw-mask">
          <rect x="0" y="0" width="100%" height="100%" fill="url(#fw-reveal)" />
        </mask>
      </defs>
      <text x="50%" y="54%" textAnchor="middle" dominantBaseline="middle" className="fw-base">
        VAYULENS
      </text>
      <text
        x="50%"
        y="54%"
        textAnchor="middle"
        dominantBaseline="middle"
        className="fw-color"
        mask="url(#fw-mask)"
        style={{ opacity: hovered ? 1 : 0 }}
      >
        VAYULENS
      </text>
    </svg>
  );
}
