// Soft light shafts angling across the hero, like low sun through haze.
// Adapted from the sandbox spotlight: same rotated radial-gradient geometry,
// re-tinted for a light page (faint haze blue, multiply-free low alphas) and
// driven by CSS keyframes instead of Motion. Purely decorative.

export default function Spotlight() {
  return (
    <div className="spotlight" aria-hidden="true">
      <div className="spotlight-side spotlight-left">
        <span className="spotlight-beam spotlight-beam-a" />
        <span className="spotlight-beam spotlight-beam-b" />
      </div>
      <div className="spotlight-side spotlight-right">
        <span className="spotlight-beam spotlight-beam-a" />
        <span className="spotlight-beam spotlight-beam-b" />
      </div>
    </div>
  );
}
