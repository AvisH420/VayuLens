// Landing page. Lenis drives inertial scrolling; Motion springs map scroll
// onto the hero handoff (headline out, attribution story in, haze building
// on the globe) and a perspective-tilted statement section. Everything
// content-bearing stays in the document flow and fully static under
// reduced motion.

import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { motion, useMotionValue, useTransform } from "motion/react";
import { ArrowRight } from "lucide-react";
import EarthGlobe from "./EarthGlobe.jsx";
import FeatureGrid from "./FeatureGrid.jsx";
import IndiaMap from "./IndiaMap.jsx";
import DashboardPreview from "./DashboardPreview.jsx";
import CtaBand from "./CtaBand.jsx";
import Spotlight from "./Spotlight.jsx";
import FooterWordmark from "./FooterWordmark.jsx";
import { webglAvailable } from "./webgl.js";

const ShaderWash = lazy(() => import("./ShaderWash.jsx"));
import ForecastChart from "../charts/ForecastChart.jsx";
import SourceBars from "../charts/SourceBars.jsx";
import { buildCity, runScenario } from "../../lib/mock.js";
import { CITIES } from "../../lib/cities.js";
import { aqiBand, dominantSource, SOURCES } from "../../lib/aqi.js";
import "./landing.css";

function nearestCell(city, wardName) {
  const seed = CITIES[city.cfg.id].wards.find((w) => w.name === wardName);
  const cells = city.cells.filter((c) => c.ward === wardName);
  if (!seed || !cells.length) return city.cells[0];
  return cells.reduce((best, c) => {
    const d = (c.lat - seed.lat) ** 2 + (c.lon - seed.lon) ** 2;
    const bd = (best.lat - seed.lat) ** 2 + (best.lon - seed.lon) ** 2;
    return d < bd ? c : best;
  });
}

const DEMO_WARDS = ["Anand Vihar", "Wazirpur", "Dwarka", "Narela"];

const DATA_SOURCES = [
  ["OpenAQ v3", "ground stations"],
  ["CPCB CAAQMS", "official monitors"],
  ["Sentinel-5P", "NO2 · SO2 · aerosol index"],
  ["MODIS AOD", "aerosol optical depth"],
  ["Open-Meteo", "wind · forecasts"],
  ["OpenStreetMap", "land use · roads"],
];

const spring = { type: "spring", stiffness: 70, damping: 18 };

// statement copy, split so each word can stagger in (em: italic emphasis)
const STATEMENT = [
  { text: "India already measures its air well. What a 2024 audit found is that only" },
  { text: "31% of monitored cities", em: true },
  { text: "had any response protocol tied to their readings. The data exists." },
  { text: "The layer that acts on it doesn't.", em: true },
];

function StatementWords({ on }) {
  let i = 0;
  return STATEMENT.map((seg, s) => {
    const words = seg.text.split(" ").map((w) => {
      const el = (
        <span
          className={`st-word ${on ? "in" : ""}`}
          style={{ transitionDelay: `${i * 32}ms` }}
          key={i}
        >
          {w}{" "}
        </span>
      );
      i += 1;
      return el;
    });
    return seg.em ? <em key={`s${s}`}>{words}</em> : words;
  });
}

export default function Landing() {
  const delhi = useMemo(() => buildCity("delhi"), []);
  const panaji = useMemo(() => buildCity("panaji"), []);

  const [demoWard, setDemoWard] = useState(DEMO_WARDS[0]);
  const demoCell = useMemo(() => nearestCell(delhi, demoWard), [delhi, demoWard]);
  const demoBand = aqiBand(demoCell.aqi);
  const demoDominant = dominantSource(demoCell.shares);

  const forecastCell = useMemo(() => nearestCell(delhi, "Anand Vihar"), [delhi]);

  // simulator teaser
  const [simOn, setSimOn] = useState(false);
  const [simBusy, setSimBusy] = useState(false);
  const sim = useMemo(
    () => runScenario("delhi", { action: "halt_construction", ward: "Dwarka", days: 3 }),
    []
  );
  const simCell = useMemo(() => nearestCell(delhi, "Dwarka"), [delhi]);
  const simResult = sim.results.get(simCell.cell_id);
  const toggleSim = () => {
    if (simOn) return setSimOn(false);
    setSimBusy(true);
    setTimeout(() => {
      setSimBusy(false);
      setSimOn(true);
    }, 700);
  };

  const reduced = useMemo(
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    []
  );

  // entrance: content settles in once the globe texture is up
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setReady(true), 1400); // fallback
    return () => clearTimeout(t);
  }, []);

  // page-wide shader wash: mounted once the globe has had first claim on the
  // GPU; the static CSS wash stays underneath as the fallback
  const canGL = useMemo(webglAvailable, []);
  const [washOn, setWashOn] = useState(false);
  useEffect(() => {
    if (!canGL) return undefined;
    const t = setTimeout(() => setWashOn(true), 1200);
    return () => clearTimeout(t);
  }, [canGL]);

  useEffect(() => {
    document.title = "VayuLens · Air quality intelligence for Indian cities";
  }, []);

  // nav condenses into a glass pill once the page starts moving
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 40);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);

  // hero scroll choreography: progress measured directly from the stage's
  // bounding rect every scroll frame, mapped 1:1 (no smoothing, no caching)
  const stageRef = useRef(null);
  const stRef = useRef(null);
  const progressRef = useRef(0);
  const [phase2, setPhase2] = useState(false);
  const heroP = useMotionValue(0);
  const stP = useMotionValue(0);

  useEffect(() => {
    if (reduced) return undefined;
    let raf = 0;
    const update = () => {
      raf = 0;
      const stage = stageRef.current;
      if (stage) {
        const total = stage.offsetHeight - window.innerHeight;
        const v = Math.min(1, Math.max(0, -stage.getBoundingClientRect().top / Math.max(1, total)));
        heroP.set(v);
        progressRef.current = v;
        setPhase2(v > 0.48);
      }
      const st = stRef.current;
      if (st) {
        const r = st.getBoundingClientRect();
        const vh = window.innerHeight;
        stP.set(Math.min(1, Math.max(0, (vh - r.top) / (vh + r.height))));
      }
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, [reduced, heroP, stP]);

  const p1Opacity = useTransform(heroP, [0.22, 0.4], [1, 0]);
  const p1Y = useTransform(heroP, [0, 0.42], [0, -70]);
  const p2Opacity = useTransform(heroP, [0.52, 0.68], [0, 1]);
  const p2Y = useTransform(heroP, [0.48, 0.7], [90, 0]);
  const hintOpacity = useTransform(heroP, [0, 0.06], [1, 0]);

  // statement section: gentle rise as it passes; the words themselves fade
  // in staggered (sandbox text-generate pattern), so the container only
  // handles the exit fade at the bottom of the pass
  const stOpacity = useTransform(stP, [0.62, 0.85], [1, 0]);
  const stRotate = useTransform(stP, [0, 1], [7, -3]);
  const stY = useTransform(stP, [0, 1], [40, -40]);

  // one-shot trigger for the word stagger
  const [stSeen, setStSeen] = useState(false);
  useEffect(() => {
    if (reduced) return undefined;
    const el = stRef.current;
    if (!el) return undefined;
    const io = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          setStSeen(true);
          io.disconnect();
        }
      },
      { threshold: 0.35 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [reduced]);

  // heading ink fill on scroll (cheap, shared handler)
  const rootRef = useRef(null);
  useEffect(() => {
    if (reduced) {
      rootRef.current?.classList.add("static-hero");
      return undefined;
    }
    const heads = Array.from(rootRef.current.querySelectorAll(".section-head h2"));
    let raf = 0;
    const update = () => {
      raf = 0;
      const vh = window.innerHeight;
      for (const h of heads) {
        const r = h.getBoundingClientRect();
        const t = Math.min(1, Math.max(0, (vh * 0.85 - r.top) / (vh * 0.38)));
        h.style.setProperty("--fill", (t * 100).toFixed(1));
      }
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("scroll", onScroll);
    };
  }, [reduced]);

  const entrance = (delay) =>
    reduced
      ? {}
      : {
          initial: { opacity: 0, y: 26 },
          animate: ready ? { opacity: 1, y: 0 } : { opacity: 0, y: 26 },
          transition: { ...spring, delay },
        };

  return (
    <div className="landing" ref={rootRef}>
      <div className="landing-wash" aria-hidden="true">
        {washOn && (
          <Suspense fallback={null}>
            <ShaderWash reduced={reduced} variant="page" />
          </Suspense>
        )}
      </div>

      <motion.nav
        className={`landing-nav ${scrolled ? "condensed" : ""}`}
        {...entrance(0.05)}
      >
        <span className="wordmark">
          <span className="wordmark-ring" aria-hidden="true" />
          VayuLens
        </span>
        <div className="nav-links">
          <a href="#attribution">Attribution</a>
          <a href="#forecast">Forecast</a>
          <a href="#simulator">Simulator</a>
          <a href="#assistant">Assistant</a>
        </div>
        <Link to="/app" className="btn btn-primary nav-cta">
          Open the Delhi grid
        </Link>
      </motion.nav>

      {/* ---- pinned hero: scroll builds the haze over north India ---- */}
      <section className="hero-stage" ref={stageRef}>
        <div className="hero-pin">
          <EarthGlobe progressRef={progressRef} onReady={() => setReady(true)} />
          <Spotlight />

          <motion.div
            className={`hero-copy hero-phase1 ${phase2 ? "off" : ""}`}
            style={reduced ? undefined : { opacity: p1Opacity, y: p1Y }}
          >
            <motion.div {...entrance(0.12)}>
              <p className="eyebrow">Urban air quality intelligence · Delhi + Panaji</p>
              <h1>
                India measures its air 900 ways.
                <br />
                <em>VayuLens names what's polluting it.</em>
              </h1>
              <p className="hero-sub">
                A 1 km intelligence grid fused from CAAQMS stations, Sentinel-5P
                and MODIS. Every cell carries a source attribution: traffic,
                construction, industry, burning or dust, with confidence
                attached and a regulation to act on it.
              </p>
              <div className="hero-ctas">
                <Link to="/app" className="btn btn-primary">
                  Open the Delhi grid
                  <ArrowRight size={16} strokeWidth={2.2} aria-hidden="true" />
                </Link>
                <a href="#simulator" className="btn btn-ghost">
                  See a what-if run
                </a>
              </div>
              <div className="hero-live">
                {[
                  { city: "Delhi", aqi: delhi.avgAqi },
                  { city: "Panaji", aqi: panaji.avgAqi },
                ].map(({ city, aqi }) => (
                  <span className="chip" key={city}>
                    <span className="dot" style={{ background: aqiBand(aqi).color }} />
                    {city} · AQI {aqi} · {aqiBand(aqi).label}
                  </span>
                ))}
                <span className="hero-live-note">city means, demo data</span>
              </div>
            </motion.div>
          </motion.div>

          <motion.div
            className={`hero-copy hero-phase2 ${phase2 ? "" : "off"}`}
            style={reduced ? { display: "none" } : { opacity: p2Opacity, y: p2Y }}
          >
            <p className="eyebrow">What the satellites see each winter</p>
            <h2 className="hero-h2">
              The haze that satellites watch build every winter.
              <br />
              <em>This year, every square kilometre of it gets named.</em>
            </h2>
            <div className="hero-mix">
              {SOURCES.map((s) => (
                <span className="chip" key={s.key}>
                  <span className="dot" style={{ background: s.color }} />
                  {s.label} {Math.round(delhi.avgShares[s.key] * 100)}%
                </span>
              ))}
            </div>
            <p className="hero-live-note">Delhi city-wide source mix · demo data</p>
          </motion.div>

          <motion.div
            className="scroll-hint"
            aria-hidden="true"
            style={reduced ? { display: "none" } : { opacity: hintOpacity }}
          >
            <span className="scroll-hint-line" />
            scroll
          </motion.div>
        </div>
      </section>

      {/* ---- the problem, stated plainly ---- */}
      <section className="statement" ref={stRef}>
        <div className="statement-persp">
          <motion.p
            className="statement-text"
            style={
              reduced
                ? undefined
                : { opacity: stOpacity, rotateX: stRotate, y: stY }
            }
          >
            <StatementWords on={reduced || stSeen} />
          </motion.p>
        </div>
      </section>

      {/* ---- data sources strip ---- */}
      <section className="sources-strip">
        <span className="sources-title">Reads from</span>
        <div className="sources-items">
          {DATA_SOURCES.map(([name, role]) => (
            <span className="source-item" key={name}>
              <strong>{name}</strong>
              <span>{role}</span>
            </span>
          ))}
        </div>
      </section>

      {/* ---- capability grid ---- */}
      <section className="section" id="platform">
        <div className="section-head">
          <p className="eyebrow">The platform</p>
          <h2>Eight instruments on one grid.</h2>
        </div>
        <FeatureGrid />
      </section>

      {/* ---- dashboard preview ---- */}
      <section className="section section-preview" id="preview">
        <div className="section-head">
          <p className="eyebrow">The operations view</p>
          <h2>A control room for air, not a wall of numbers.</h2>
          <p className="section-sub">
            The grid, the attribution panel, the simulator and the assistant
            share one screen, built for the officer who has to act on it today.
          </p>
        </div>
        <DashboardPreview reduced={reduced} />
      </section>

      {/* ---- attribution ---- */}
      <section className="section" id="attribution">
        <div className="section-head">
          <p className="eyebrow">Source attribution · the hero feature</p>
          <h2>Not just how bad. Who.</h2>
          <p className="section-sub">
            A red number can't be inspected. VayuLens separates each cell's
            load into five source classes, read from NO2 columns, UV aerosol
            index, land use and point-source registers, so a reading becomes an
            address someone can visit.
          </p>
        </div>
        <div className="attr-demo glass">
          <div className="attr-demo-side">
            <div className="ward-chips">
              {DEMO_WARDS.map((w) => (
                <button
                  key={w}
                  className={`chip ward-chip ${w === demoWard ? "active" : ""}`}
                  onClick={() => setDemoWard(w)}
                >
                  {w}
                </button>
              ))}
            </div>
            <div className="attr-demo-reading">
              <span className="attr-aqi" style={{ color: demoBand.color }}>
                {demoCell.aqi}
              </span>
              <div>
                <span className="chip">
                  <span className="dot" style={{ background: demoBand.color }} />
                  {demoBand.label}
                </span>
                <p className="attr-note">
                  Cell {demoCell.cell_id.replace("grid_", "")} · dominant source:{" "}
                  <strong style={{ color: demoDominant.color }}>
                    {demoDominant.label.toLowerCase()}
                  </strong>
                </p>
              </div>
            </div>
          </div>
          <div className="attr-demo-bars">
            <SourceBars shares={demoCell.shares} confidence={demoCell.confidence} />
          </div>
        </div>
      </section>

      {/* ---- forecast ---- */}
      <section className="section" id="forecast">
        <div className="section-head">
          <p className="eyebrow">Hyperlocal forecasting</p>
          <h2>72 hours ahead, cell by cell.</h2>
          <p className="section-sub">
            Dispersion physics plus a gradient-boosted residual model, scored
            against a persistence baseline. The band is honest uncertainty; it
            widens where the model deserves less trust.
          </p>
        </div>
        <div className="chart-card glass">
          <div className="chart-card-head">
            <span className="chip">
              <span className="dot" style={{ background: aqiBand(forecastCell.aqi).color }} />
              Anand Vihar · cell {forecastCell.cell_id.replace("grid_", "")}
            </span>
            <span className="chart-card-note">±12% band · demo data</span>
          </div>
          <ForecastChart baseline={forecastCell.forecast} uncertainty={0.12} />
        </div>
      </section>

      {/* ---- simulator ---- */}
      <section className="section" id="simulator">
        <div className="section-head">
          <p className="eyebrow">Intervention simulator</p>
          <h2>Halt construction in Dwarka. Watch hour 48.</h2>
          <p className="section-sub">
            Interventions cost money and votes. <code>simulate()</code> reruns
            the dispersion model under a measure and prices it in AQI before
            anyone signs the order.
          </p>
        </div>
        <div className="chart-card glass">
          <div className="chart-card-head sim-head">
            <button
              className={`btn ${simOn ? "btn-primary" : "btn-ghost"} sim-toggle`}
              onClick={toggleSim}
              disabled={simBusy}
            >
              <span className={`sim-switch ${simOn ? "on" : ""}`} aria-hidden="true" />
              {simBusy
                ? "Recomputing dispersion…"
                : simOn
                  ? "Construction halt applied · 3 days"
                  : "Apply GRAP Stage III construction halt"}
            </button>
            {simOn && (
              <span className="sim-delta">
                {sim.summary.avgDelta48} AQI average across Dwarka at +48 h
              </span>
            )}
          </div>
          <ForecastChart
            baseline={simCell.forecast}
            scenario={simOn ? simResult.scenario : undefined}
          />
        </div>
      </section>

      {/* ---- assistant ---- */}
      <section className="section" id="assistant">
        <div className="section-head">
          <p className="eyebrow">Grounded assistant</p>
          <h2>Answers that arrive with the regulation attached.</h2>
          <p className="section-sub">
            Retrieval over GRAP, NCAP and CPCB operating procedures. Every
            answer cites its passages and reports confidence; when retrieval is
            weak, it says so instead of guessing.
          </p>
        </div>
        <div className="chat-mock glass">
          <div className="chat-mock-q">
            Why is Anand Vihar severe today, and what does GRAP require?
          </div>
          <div className="chat-mock-a">
            <p>
              Anand Vihar is in the Severe band (AQI 412), driven by traffic
              (41%) and construction (22%) under stagnant north-westerly winds.
              At this level GRAP Stage III applies: non-exempt construction
              stops, mechanized sweeping intensifies, and BS-III petrol /
              BS-IV diesel cars are barred from the NCT.
            </p>
            <div className="chat-mock-cite">
              <span className="chip">GRAP (CAQM, rev. 2024) · Stage III s.1-4</span>
              <span className="chip">CAQM direction no. 72 · para 3</span>
            </div>
            <div className="chat-mock-conf">
              <span>Confidence</span>
              <div className="meter"><span style={{ width: "89%" }} /></div>
              <span>0.89 · 4 passages</span>
            </div>
          </div>
          <Link to="/app?panel=chat" className="btn btn-ghost chat-mock-cta">
            Ask it about your ward
          </Link>
        </div>
      </section>

      {/* ---- pilot deployments ---- */}
      <section className="section" id="pilots">
        <div className="pilots-grid">
          <div>
            <div className="section-head pilots-head">
              <p className="eyebrow">Pilot deployments</p>
              <h2>Proven at two scales.</h2>
              <p className="section-sub">
                Delhi, a megacity under winter inversion. Panaji, a coastal
                capital an order of magnitude cleaner. The same grid, the same
                attribution engine, runs both without retuning.
              </p>
            </div>
            <div className="pilot-stats">
              {[
                { city: delhi, note: "NCT winter baseline" },
                { city: panaji, note: "coastal monsoon-washed air" },
              ].map(({ city, note }) => (
                <div className="pilot-stat" key={city.cfg.id}>
                  <span className="pilot-stat-city">{city.cfg.name}</span>
                  <span className="pilot-stat-cells">
                    {city.cells.length.toLocaleString()} cells ·{" "}
                    <span style={{ color: aqiBand(city.avgAqi).color }}>
                      AQI {city.avgAqi}
                    </span>
                  </span>
                  <span className="pilot-stat-note">{note}</span>
                </div>
              ))}
            </div>
          </div>
          <IndiaMap />
        </div>
      </section>

      {/* ---- closing call ---- */}
      <CtaBand reduced={reduced} />

      {/* ---- footer ---- */}
      <footer className="landing-footer">
        <div className="footer-grid">
          <div>
            <span className="wordmark">
              <span className="wordmark-ring" aria-hidden="true" />
              VayuLens
            </span>
            <p className="footer-note">
              Built in 20 days by a team of four for the ET AI Hackathon 2026,
              problem statement #5. Data grid, attribution engine, RAG layer
              and this platform, each owned end to end.
            </p>
          </div>
          <div className="footer-meta">
            <span>
              Grid: {delhi.cells.length.toLocaleString()} cells over Delhi ·{" "}
              {panaji.cells.length} over Panaji · 1 km × 1 km
            </span>
            <span>Frontend running on demo data; FastAPI gateway lands next.</span>
            <div className="footer-links">
              <a
                href="https://github.com/AvisH420/VayuLens"
                target="_blank"
                rel="noreferrer"
              >
                Repository
              </a>
              <Link to="/app">Dashboard</Link>
            </div>
          </div>
        </div>
        <FooterWordmark />
      </footer>
    </div>
  );
}
