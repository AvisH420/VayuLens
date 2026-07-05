// Full-width outline wordmark closing the footer. Two stroked layers: the
// hairline base and a green-gradient version that inks in on hover — a
// single CSS opacity crossfade, no per-frame work (the cursor-following
// mask from the sandbox original re-rasterized the text every mousemove
// and dragged the whole page down in Safari).

export default function FooterWordmark() {
  return (
    <svg
      className="footer-wordmark"
      viewBox="0 0 640 110"
      preserveAspectRatio="xMidYMid meet"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="fw-ink" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="640" y2="110">
          <stop offset="0%" stopColor="var(--green-deep)" />
          <stop offset="55%" stopColor="var(--green)" />
          <stop offset="100%" stopColor="#7fa3b6" />
        </linearGradient>
      </defs>
      <text x="50%" y="54%" textAnchor="middle" dominantBaseline="middle" className="fw-base">
        VAYULENS
      </text>
      <text x="50%" y="54%" textAnchor="middle" dominantBaseline="middle" className="fw-color">
        VAYULENS
      </text>
    </svg>
  );
}
