// Callback-ref wrapper around @formkit/auto-animate. Guarded so a ref that
// fires on every render only attaches one observer per element. AutoAnimate
// already sits out when the user prefers reduced motion.

import autoAnimate from "@formkit/auto-animate";

export function animate(el) {
  if (el && !el.__autoAnimated) {
    el.__autoAnimated = true;
    autoAnimate(el, { duration: 220, easing: "cubic-bezier(0.2, 0.7, 0.2, 1)" });
  }
}
