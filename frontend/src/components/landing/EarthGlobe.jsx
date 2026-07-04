// Hero 3D: the Earth (4K texture from Design/earth), India facing the
// camera. Scroll drives the honest version of the pollution story: the
// grey winter haze band that satellites actually see over the
// Indo-Gangetic plain builds up, a faint particulate field thickens, and
// the planet dims. No props, no gimmicks: no rim shaders, no satellites.
// Renders a single static frame under reduced motion.

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";

const EARTH_R = 1.35;

// A full-globe veil of dirty air, painted in equirectangular space:
// wind-sheared streaks (wider than tall, like sheared aerosol layers),
// slightly denser in the mid-latitudes where most emissions live, thin at
// the poles. Two of these, drifting at different speeds, read as a slowly
// moving smog layer rather than a static tint.
function makeHazeTexture(seed) {
  const W = 2048;
  const H = 1024;
  const c = document.createElement("canvas");
  c.width = W;
  c.height = H;
  const ctx = c.getContext("2d");
  let s = seed;
  const rand = () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };

  // soft radial-gradient streaks; the gradient is defined inside the
  // translated/scaled space so it hugs each ellipse (no ctx.filter — it is
  // unsupported in Safari)
  for (let i = 0; i < 340; i++) {
    const x = rand() * W;
    const y = rand() * H;
    // density peaks in the industrialized mid-latitudes, fades at poles
    const lat = Math.abs(y / H - 0.5) * 2; // 0 equator -> 1 pole
    const band = Math.max(0.15, 1 - Math.abs(lat - 0.35) * 1.7);
    const rx = 70 + rand() * 170; // sheared: wide
    const ry = 12 + rand() * 30; //          and flat
    const a = (0.26 + rand() * 0.34) * band;
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(rx, ry);
    const g = ctx.createRadialGradient(0, 0, 0, 0, 0, 1);
    g.addColorStop(0, `rgba(176, 166, 146, ${a.toFixed(3)})`);
    g.addColorStop(0.55, `rgba(176, 166, 146, ${(a * 0.55).toFixed(3)})`);
    g.addColorStop(1, "rgba(176, 166, 146, 0)");
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(0, 0, 1, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.wrapS = THREE.RepeatWrapping;
  return tex;
}

// soft photographic glow behind the planet (a sprite, not a rim shader)
function makeGlowTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 256;
  const ctx = c.getContext("2d");
  const g = ctx.createRadialGradient(128, 128, 0, 128, 128, 128);
  g.addColorStop(0, "rgba(168, 190, 205, 0.55)");
  g.addColorStop(0.55, "rgba(168, 190, 205, 0.16)");
  g.addColorStop(1, "rgba(168, 190, 205, 0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 256, 256);
  return new THREE.CanvasTexture(c);
}

export default function EarthGlobe({ progressRef, onReady }) {
  const mountRef = useRef(null);
  const [fallback, setFallback] = useState(false);
  const onReadyRef = useRef(onReady);
  onReadyRef.current = onReady;

  useEffect(() => {
    const mount = mountRef.current;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 60);
    camera.position.set(0, 0, 7.2);

    // no WebGL (disabled GPU, crashed GPU process) -> static pre-rendered globe
    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: true,
        preserveDrawingBuffer: true,
      });
    } catch {
      setFallback(true);
      onReadyRef.current?.();
      return undefined;
    }
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    mount.appendChild(renderer.domElement);

    scene.add(new THREE.HemisphereLight(0xf4f8ff, 0xdde6dc, 1.0));
    const sun = new THREE.DirectionalLight(0xfff3dd, 1.9);
    sun.position.set(3.5, 1.2, 3.2);
    scene.add(sun);

    const world = new THREE.Group();
    scene.add(world);

    const tilt = new THREE.Group();
    tilt.rotation.z = THREE.MathUtils.degToRad(-12);
    world.add(tilt);

    let renderFrameOnce = () => {};
    const tex = new THREE.TextureLoader().load("/earth_4k.jpg", () => {
      onReadyRef.current?.();
      if (reduced) renderFrameOnce();
    });
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = renderer.capabilities.getMaxAnisotropy?.() ?? 8;
    const earthMat = new THREE.MeshStandardMaterial({
      map: tex,
      roughness: 0.96,
      metalness: 0,
    });
    const earth = new THREE.Mesh(new THREE.SphereGeometry(EARTH_R, 96, 96), earthMat);
    tilt.add(earth);

    // two drifting haze layers over the whole planet
    const hazeMatA = new THREE.MeshBasicMaterial({
      map: makeHazeTexture(7919),
      transparent: true,
      opacity: 0,
      depthWrite: false,
    });
    const hazeA = new THREE.Mesh(
      new THREE.SphereGeometry(EARTH_R * 1.008, 96, 96),
      hazeMatA
    );
    tilt.add(hazeA);
    const hazeMatB = new THREE.MeshBasicMaterial({
      map: makeHazeTexture(104729),
      transparent: true,
      opacity: 0,
      depthWrite: false,
    });
    const hazeB = new THREE.Mesh(
      new THREE.SphereGeometry(EARTH_R * 1.016, 96, 96),
      hazeMatB
    );
    tilt.add(hazeB);

    // fine particulate field: a sparse dust shell, only legible up close
    const pGeo = new THREE.BufferGeometry();
    const P_N = 550;
    const pPos = new Float32Array(P_N * 3);
    for (let i = 0; i < P_N; i++) {
      const u = Math.random() * 2 - 1;
      const th = Math.random() * Math.PI * 2;
      const rr = EARTH_R * (1.03 + Math.random() * 0.14);
      const s = Math.sqrt(1 - u * u);
      pPos[i * 3] = s * Math.cos(th) * rr;
      pPos[i * 3 + 1] = u * rr;
      pPos[i * 3 + 2] = s * Math.sin(th) * rr;
    }
    pGeo.setAttribute("position", new THREE.BufferAttribute(pPos, 3));
    const pMat = new THREE.PointsMaterial({
      color: 0x8d8271,
      size: 0.014,
      transparent: true,
      opacity: 0,
      depthWrite: false,
    });
    const particulates = new THREE.Points(pGeo, pMat);
    world.add(particulates);

    // soft glow sprite behind the planet
    const glow = new THREE.Sprite(
      new THREE.SpriteMaterial({
        map: makeGlowTexture(),
        transparent: true,
        opacity: 0.7,
        depthWrite: false,
      })
    );
    glow.scale.setScalar(EARTH_R * 4.4);
    glow.position.z = -0.4;
    world.add(glow);

    // India toward the camera; verified against the texture's equirect frame
    const INDIA_Y = -2.97;
    earth.rotation.y = INDIA_Y;

    let compact = false;
    const layout = () => {
      const w = mount.clientWidth || 1;
      const h = mount.clientHeight || 1;
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      compact = w < 900;
      world.position.x = compact ? 0 : 1.95;
      world.position.y = compact ? 0.55 : -0.08;
      const s = compact ? 0.72 : 1;
      world.scale.set(s, s, s);
    };
    layout();
    const ro = new ResizeObserver(layout);
    ro.observe(mount);

    let targetX = 0;
    let targetY = 0;
    const onPointer = (e) => {
      targetX = (e.clientX / window.innerWidth - 0.5) * 0.1;
      targetY = (e.clientY / window.innerHeight - 0.5) * 0.06;
    };
    if (!reduced) window.addEventListener("pointermove", onPointer, { passive: true });

    let raf;
    let running = true;
    const clock = new THREE.Clock();
    const renderFrame = () => {
      const dt = Math.min(0.05, clock.getDelta());
      const t = clock.elapsedTime;
      const p = progressRef?.current ?? 0;

      // calm: India stays in view, the globe only breathes
      earth.rotation.y = INDIA_Y + Math.sin(t * 0.05) * 0.04 + p * 0.1;
      particulates.rotation.y += dt * 0.008;

      // the dirty air drifts: two layers, slightly different speeds
      hazeA.rotation.y += dt * 0.011;
      hazeB.rotation.y -= dt * 0.007;

      const hazeTarget = Math.min(1, Math.max(0, (p - 0.12) / 0.5));
      hazeMatA.opacity += (hazeTarget - hazeMatA.opacity) * 0.07;
      hazeMatB.opacity += (hazeTarget * 0.85 - hazeMatB.opacity) * 0.07;
      pMat.opacity += (hazeTarget * 0.4 - pMat.opacity) * 0.07;

      // the planet dims under the veil; the glow cools off
      const h = hazeMatA.opacity;
      earthMat.color.setRGB(1 - h * 0.2, 1 - h * 0.24, 1 - h * 0.3);
      glow.material.opacity = 0.7 - h * 0.3;

      camera.position.z = 7.2 - p * 0.5;
      world.rotation.y += (targetX - world.rotation.y) * 0.04;
      world.rotation.x += (targetY - world.rotation.x) * 0.04;

      renderer.render(scene, camera);
      if (running && !reduced) raf = requestAnimationFrame(renderFrame);
    };
    renderFrameOnce = () => renderer.render(scene, camera);

    if (reduced) {
      renderFrameOnce();
    } else {
      raf = requestAnimationFrame(renderFrame);
    }

    const io = new IntersectionObserver(([entry]) => {
      running = entry.isIntersecting;
      if (running && !reduced) {
        cancelAnimationFrame(raf);
        raf = requestAnimationFrame(renderFrame);
      }
    });
    io.observe(mount);

    return () => {
      running = false;
      cancelAnimationFrame(raf);
      io.disconnect();
      ro.disconnect();
      window.removeEventListener("pointermove", onPointer);
      renderer.dispose();
      mount.removeChild(renderer.domElement);
    };
  }, [progressRef]);

  return (
    <div ref={mountRef} className="globe-stage" aria-hidden="true">
      {fallback && (
        <img src="/earth_fallback.png" alt="" className="globe-fallback" />
      )}
    </div>
  );
}
