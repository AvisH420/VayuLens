// The animated gradient surface behind the whole landing page (the CTA band
// shows it through translucent glass — it deliberately has no canvas of its
// own). Isolated in its own chunk (lazy-imported) so the shadergradient/
// react-three dependency stays out of the main landing bundle. The
// `.shader-wash` wrapper fades the canvas in slowly once the chunk lands,
// so the surface never pops over the static fallback.

import { ShaderGradientCanvas, ShaderGradient } from "@shadergradient/react";

// Green family only: blue-leaning colors drift purple under the 3d light.
const WASH = { colors: ["#f4f7f1", "#dce9dd", "#b9d4c2"], speed: 0.09, strength: 1.4 };

export default function ShaderWash({ reduced }) {
  const v = WASH;
  return (
    <div className="shader-wash" aria-hidden="true">
      {/* no lazyLoad: the scene must render while still offscreen so it is
          already moving when scrolled to, instead of popping in on arrival */}
      <ShaderGradientCanvas
        style={{ position: "absolute", inset: 0 }}
        pixelDensity={1}
        fov={40}
        pointerEvents="none"
      >
        <ShaderGradient
          control="props"
          type="waterPlane"
          animate={reduced ? "off" : "on"}
          uTime={reduced ? 6 : 0}
          uSpeed={v.speed}
          uStrength={v.strength}
          uDensity={1.2}
          uFrequency={3}
          color1={v.colors[0]}
          color2={v.colors[1]}
          color3={v.colors[2]}
          brightness={1.2}
          reflection={0.05}
          grain="off"
          lightType="3d"
          cDistance={2.6}
          cPolarAngle={95}
          cAzimuthAngle={180}
          cameraZoom={1}
          positionX={0}
          positionY={0}
          positionZ={0}
          rotationX={0}
          rotationY={0}
          rotationZ={0}
        />
      </ShaderGradientCanvas>
    </div>
  );
}
