// Shared probe: can this browser give us a WebGL context at all? Used to
// decide whether the shader washes mount or their static CSS stand-ins hold.

export function webglAvailable() {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}
