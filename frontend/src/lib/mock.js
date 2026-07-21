// Deterministic mock backend. Generates data in exactly the shapes of
// contracts/ (GridCell, Measurement, Attribution, Forecast, Recommendation)
// so swapping in the real FastAPI gateway later changes nothing downstream.

import { CITIES } from "./cities.js";
import { SOURCES } from "./aqi.js";

// ---- seeded RNG (mulberry32) so every reload shows the same city ----

function hashSeed(str) {
  let h = 1779033703;
  for (let i = 0; i < str.length; i++) {
    h = Math.imul(h ^ str.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  return h >>> 0;
}

function rng(seedStr) {
  let a = hashSeed(seedStr);
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ---- spatial helpers ----

const KM_PER_DEG_LAT = 111;

function distKm(lat1, lon1, lat2, lon2) {
  const dy = (lat2 - lat1) * KM_PER_DEG_LAT;
  const dx = (lon2 - lon1) * KM_PER_DEG_LAT * Math.cos((lat1 * Math.PI) / 180);
  return Math.sqrt(dx * dx + dy * dy);
}

const KIND_TO_SHARE_BIAS = {
  traffic: { traffic: 0.5, dust: 0.12 },
  industry: { industry: 0.55, traffic: 0.1 },
  construction: { construction: 0.5, dust: 0.2 },
  burning: { burning: 0.55, dust: 0.1 },
  dust: { dust: 0.5, construction: 0.15 },
};

// Forecast horizon: 13 steps of 6 h = now .. +72 h.
export const FC_STEPS = 13;
export const FC_STEP_HOURS = 6;

// Diurnal shape: traffic peaks ~8-10 and ~19-22, cleaner mid-afternoon.
function diurnal(hourOfDay) {
  const morning = Math.exp(-((hourOfDay - 9) ** 2) / 18);
  const evening = Math.exp(-((hourOfDay - 20.5) ** 2) / 14);
  return 0.88 + 0.22 * morning + 0.3 * evening;
}

// ---- city build (memoized) ----

const cityCache = {};

export function buildCity(cityId) {
  if (cityCache[cityId]) return cityCache[cityId];
  const cfg = CITIES[cityId];
  const rand = rng(cityId);
  const cells = [];
  const nowHour = 11; // demo clock: late morning IST

  for (let lat = cfg.bbox.latMin; lat < cfg.bbox.latMax; lat += cfg.latStep) {
    for (let lon = cfg.bbox.lonMin; lon < cfg.bbox.lonMax; lon += cfg.lonStep) {
      const cLat = lat + cfg.latStep / 2;
      const cLon = lon + cfg.lonStep / 2;
      const r = rand;

      // nearest ward seed -> ward assignment
      let ward = cfg.wards[0];
      let wardD = Infinity;
      for (const w of cfg.wards) {
        const d = distKm(cLat, cLon, w.lat, w.lon);
        if (d < wardD) {
          wardD = d;
          ward = w;
        }
      }

      // pollution field: city base with edge falloff + hotspot gaussians
      const dCenter = distKm(cLat, cLon, cfg.center[1], cfg.center[0]);
      let aqi = cfg.baseAqi * Math.max(0.45, 1 - dCenter / 55);
      const shareW = { traffic: 0.2, construction: 0.12, industry: 0.08, burning: 0.08, dust: 0.18 };
      for (const w of cfg.wards) {
        const d = distKm(cLat, cLon, w.lat, w.lon);
        const g = w.amp * Math.exp(-(d * d) / (2 * 3.2 ** 2));
        aqi += g;
        const bias = KIND_TO_SHARE_BIAS[w.kind];
        for (const [k, v] of Object.entries(bias)) {
          shareW[k] += (v * g) / (w.amp + 1);
        }
      }
      aqi = Math.round(Math.min(485, Math.max(18, aqi * (0.9 + r() * 0.2))));

      // normalize shares
      const total = Object.values(shareW).reduce((a, b) => a + b, 0);
      const shares = {};
      for (const s of SOURCES) shares[s.key] = +(shareW[s.key] / total).toFixed(3);

      const roadDensity = +(2 + shareW.traffic * 14 + r() * 3).toFixed(1);
      const industrialFlag = shareW.industry > 0.28;
      const landUse = industrialFlag
        ? "industrial"
        : shareW.construction > 0.3
          ? "mixed"
          : roadDensity > 7
            ? "commercial"
            : r() > 0.75
              ? "green"
              : "residential";

      // quality: better near hotspot seeds (stations cluster there)
      const quality = +Math.min(0.95, Math.max(0.55, 0.95 - wardD * 0.03 - r() * 0.1)).toFixed(2);

      // 72 h forecast at 6 h steps: diurnal cycle + city trend + noise
      const trendPeak = cityId === "delhi" ? 1.14 : 1.03; // stagnant air mid-window
      const forecast = [];
      for (let i = 0; i < FC_STEPS; i++) {
        const h = i * FC_STEP_HOURS;
        const hod = (nowHour + h) % 24;
        const trend =
          1 + (trendPeak - 1) * Math.sin(Math.min(Math.PI, (h / 72) * Math.PI));
        const v = aqi * diurnal(hod) * trend * (0.97 + r() * 0.06);
        forecast.push(Math.round(Math.min(500, Math.max(12, v))));
      }

      const pm25 = +(aqi * 0.55 * (0.9 + r() * 0.2)).toFixed(1);
      cells.push({
        cell_id: `grid_${cLat.toFixed(3)}_${cLon.toFixed(3)}`,
        lat: +cLat.toFixed(4),
        lon: +cLon.toFixed(4),
        bounds: [lon, lat, lon + cfg.lonStep, lat + cfg.latStep],
        ward: ward.name,
        land_use_class: landUse,
        road_density: roadDensity,
        industrial_flag: industrialFlag,
        aqi,
        shares,
        confidence: +(0.55 + quality * 0.4 - (shares[dominantKey(shares)] < 0.35 ? 0.12 : 0)).toFixed(2),
        quality_score: quality,
        uncertainty: +(pm25 * (1 - quality) * 0.9).toFixed(1),
        pm25,
        pm10: +(pm25 * 1.7).toFixed(1),
        no2: +(12 + shares.traffic * 90 * (aqi / 200)).toFixed(1),
        aod: +(pm25 / 65).toFixed(2),
        forecast,
      });
    }
  }

  const avgAqi = Math.round(cells.reduce((a, c) => a + c.aqi, 0) / cells.length);
  const avgShares = {};
  for (const s of SOURCES) {
    avgShares[s.key] = +(
      cells.reduce((a, c) => a + c.shares[s.key], 0) / cells.length
    ).toFixed(3);
  }
  const built = { cfg, cells, avgAqi, avgShares, nowHour };
  cityCache[cityId] = built;
  return built;
}

function dominantKey(shares) {
  return Object.entries(shares).sort((a, b) => b[1] - a[1])[0][0];
}

// ---- what-if simulator (mock of POST /simulate) ----

export const ACTIONS = {
  halt_construction: {
    label: "Halt construction",
    detail: "Stop all C&D activity and truck movement at registered sites",
    source: "construction",
    efficacy: 0.8,
    spill: 0.3,
    citation: "GRAP Stage III · CAQM order s.11(1)",
  },
  odd_even: {
    label: "Odd-even traffic scheme",
    detail: "Restrict private vehicles by plate parity, 7am-8pm",
    source: "traffic",
    efficacy: 0.45,
    spill: 0.45,
    citation: "GRAP Stage IV · Motor Vehicles Act s.115",
  },
  industry_curbs: {
    label: "Industrial fuel curbs",
    detail: "Suspend non-PNG industrial units in the zone",
    source: "industry",
    efficacy: 0.7,
    spill: 0.35,
    citation: "Air Act 1981 s.31A · GRAP Stage III",
  },
  burning_ban: {
    label: "Open-burning enforcement",
    detail: "Patrol and fine open waste and biomass burning",
    source: "burning",
    efficacy: 0.65,
    spill: 0.25,
    citation: "SWM Rules 2016 r.15 · NGT order 2016",
  },
};

export function runScenario(cityId, { action, ward, days }) {
  const { cells } = buildCity(cityId);
  const act = ACTIONS[action];
  const horizonH = Math.min(72, days * 24);
  const results = new Map();
  let zoneCells = 0;
  let sumDelta48 = 0;
  let peak = 0;

  for (const cell of cells) {
    const inZone = ward === "all" || cell.ward === ward;
    const strength = inZone ? 1 : act.spill * 0.4;
    const share = cell.shares[act.source];
    const scenario = cell.forecast.map((v, i) => {
      const h = i * FC_STEP_HOURS;
      // effect ramps in over ~12 h (dispersion lag), out after the window
      const ramp =
        h <= 0 ? 0 : Math.min(1, h / 12) * (h <= horizonH ? 1 : Math.max(0, 1 - (h - horizonH) / 18));
      return Math.round(v * (1 - share * act.efficacy * strength * ramp));
    });
    const delta = scenario.map((v, i) => v - cell.forecast[i]);
    results.set(cell.cell_id, { scenario, delta });
    if (inZone) {
      zoneCells++;
      sumDelta48 += delta[8]; // +48 h
      peak = Math.min(peak, Math.min(...delta));
    }
  }

  return {
    action: act,
    ward,
    days,
    results,
    summary: {
      zoneCells,
      avgDelta48: zoneCells ? Math.round(sumDelta48 / zoneCells) : 0,
      peakDelta: peak,
      onsetHours: 12,
    },
  };
}

// ---- recommendations (mock of GET /recommendations/{cell_id}) ----

const REC_TEMPLATES = {
  traffic: (c) => ({
    action: `Divert heavy vehicles off the ${c.ward} corridor and run PUC checks at entry points`,
    justification: `Traffic contributes ${Math.round(c.shares.traffic * 100)}% of the load in this cell; NO2 at ${c.no2} µg/m³ confirms a combustion signature.`,
    regulation_citation: "GRAP Stage II s.6 · CMVR r.115(7)",
  }),
  construction: (c) => ({
    action: `Inspect active construction sites in ${c.ward} for dust-control compliance; halt non-compliant sites`,
    justification: `Construction accounts for ${Math.round(c.shares.construction * 100)}% here, consistent with high AOD against a moderate NO2 column.`,
    regulation_citation: "C&D Waste Rules 2016 r.4 · GRAP Stage III",
  }),
  industry: (c) => ({
    action: `Audit fuel use at registered units near ${c.ward}; enforce PNG switchover or suspend operations`,
    justification: `Industrial share is ${Math.round(c.shares.industry * 100)}% with a registered source inside the cell.`,
    regulation_citation: "Air Act 1981 s.31A · CAQM direction 2023",
  }),
  burning: (c) => ({
    action: `Deploy night patrols against open waste burning in ${c.ward}; issue on-the-spot fines`,
    justification: `Burning contributes ${Math.round(c.shares.burning * 100)}%; elevated UV aerosol index flags fresh smoke.`,
    regulation_citation: "SWM Rules 2016 r.15 · NGT order of 22.12.2016",
  }),
  dust: (c) => ({
    action: `Schedule mechanized sweeping and water sprinkling on arterial roads in ${c.ward}`,
    justification: `Road and soil dust make up ${Math.round(c.shares.dust * 100)}% of the coarse fraction (PM10/PM2.5 ratio ${(c.pm10 / c.pm25).toFixed(1)}).`,
    regulation_citation: "GRAP Stage I s.9 · NCAP city action plan",
  }),
};

export function recommendationsFor(cell) {
  return Object.entries(cell.shares)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([key, share]) => ({
      cell_id: cell.cell_id,
      ...REC_TEMPLATES[key](cell),
      priority_score: +Math.min(1, share * (cell.aqi / 320)).toFixed(2),
      source: key,
    }));
}

// ---- grounded chat (mock of POST /chat) ----

const CHAT_ANSWERS = [
  {
    match: /grap|severe|stage|mandat|protocol/i,
    text:
      "Anand Vihar is in the Severe band (AQI 412) mainly because of traffic (41%) and construction (22%) under stagnant north-westerly winds. At this level GRAP Stage III is in force: it mandates a halt on non-exempt construction and demolition, intensified mechanized road sweeping, and a ban on BS-III petrol / BS-IV diesel cars in the NCT. Stage IV triggers if AQI holds above 450 for 24 h.",
    citations: [
      { doc: "GRAP (CAQM, rev. 2024)", ref: "Stage III, s.1-4" },
      { doc: "CAQM direction no. 72", ref: "para 3" },
    ],
    confidence: 0.89,
    retrieved: 4,
  },
  {
    match: /construction|dust|c&d|site/i,
    text:
      "Construction dust is regulated by the C&D Waste Management Rules 2016: sites over 20,000 m² need dust screens, covered storage, and wheel-washing. Under GRAP Stage III all non-exempt C&D activity must stop. VayuLens flags 3 cells in Dwarka where the construction share exceeds 35% while AQI is Poor or worse; those sites are the highest-priority inspections today.",
    citations: [
      { doc: "C&D Waste Rules 2016", ref: "r.4(1), r.4(3)" },
      { doc: "GRAP (CAQM, rev. 2024)", ref: "Stage III, s.1" },
    ],
    confidence: 0.84,
    retrieved: 5,
  },
  {
    match: /school|child|advisory|health|outdoor|elderly/i,
    text:
      "For today's Very Poor band in most of central Delhi, the standard health advisory applies: schools should suspend outdoor assembly and sports (CBSE circular under GRAP Stage III makes this binding when invoked), outdoor workers should get N95 masks and staggered shifts, and people with cardiac or respiratory conditions should avoid morning hours, when the surface inversion holds pollutants low. Ward-level advisories in Hindi are available in the Advisory tab.",
    citations: [
      { doc: "MoHFW health advisory on air pollution, 2023", ref: "s.2" },
      { doc: "GRAP (CAQM, rev. 2024)", ref: "Stage III, s.8" },
    ],
    confidence: 0.81,
    retrieved: 3,
  },
  {
    match: /panaji|goa|clean|contrast/i,
    text:
      "Panaji sits in the Satisfactory band today (city mean AQI 78); the sea breeze at 4 m/s keeps dispersion strong. The main local signal is construction around Porvorim and Taleigao, at roughly a quarter of the local load. No GRAP-equivalent action is warranted; the NCAP city plan for Panaji focuses on road-dust control and construction-site norms.",
    citations: [
      { doc: "NCAP city action plan, Panaji", ref: "s.3.2" },
      { doc: "GSPCB ambient bulletin", ref: "Jul 2026" },
    ],
    confidence: 0.77,
    retrieved: 3,
  },
  {
    match: /inspect|enforce|priorit|fine|penal/i,
    text:
      "Today's enforcement queue ranks Wazirpur first: the industrial share there is 48% with AQI 388, and Air Act s.31A lets the board order closure or fuel restrictions directly. Second is the Anand Vihar corridor for PUC and heavy-vehicle checks, third the Narela periphery for open-burning patrols, where the UV aerosol index has been elevated for 36 h. Each entry in the queue carries the exact clause that authorizes the action.",
    citations: [
      { doc: "Air (Prevention & Control) Act 1981", ref: "s.31A" },
      { doc: "CAQM enforcement SOP", ref: "s.5" },
    ],
    confidence: 0.86,
    retrieved: 5,
  },
];

export function chatAnswer(query) {
  const hit = CHAT_ANSWERS.find((a) => a.match.test(query));
  if (hit) {
    const { match, ...rest } = hit;
    return rest;
  }
  return {
    text:
      "I can't ground an answer for that in the indexed corpus (retrieval confidence 0.31, below the 0.55 answer threshold), so I won't guess. I can answer reliably about GRAP stages and triggers, construction-dust rules, health advisories, enforcement priorities, and today's readings for Delhi and Panaji.",
    citations: [],
    confidence: 0.31,
    retrieved: 1,
    abstained: true,
  };
}

// ---- citizen advisories (multi-language, per the Role 3 contract) ----

export const ADVISORIES = {
  delhi: {
    en: {
      headline: "Very Poor air over most of Delhi today",
      body:
        "Keep children indoors during morning school hours; the inversion traps pollutants until about 11am. Outdoor workers should use N95 masks. Avoid burning waste; report it on 311. Conditions ease slightly after tomorrow evening's wind shift.",
      groups: ["Schools: move assembly and sports indoors", "Outdoor workers: N95, staggered shifts", "Elderly & cardiac patients: avoid 6-10am outdoors"],
    },
    hi: {
      headline: "आज दिल्ली की हवा गंभीर रूप से खराब",
      body:
        "सुबह के स्कूल समय में बच्चों को घर के अंदर रखें; लगभग 11 बजे तक प्रदूषण नीचे टिका रहता है। बाहर काम करने वाले N95 मास्क पहनें। कूड़ा न जलाएं; 311 पर सूचना दें।",
      groups: ["स्कूल: सभा और खेल अंदर करें", "बाहरी कामगार: N95 मास्क", "बुजुर्ग: सुबह 6-10 बजे बाहर न निकलें"],
    },
  },
  panaji: {
    en: {
      headline: "Satisfactory air across Panaji",
      body:
        "No restrictions needed today. The sea breeze keeps dispersion strong. Construction zones around Porvorim may see brief dust spikes in the afternoon; keep windows on that side closed if you are sensitive.",
      groups: ["General public: normal activity", "Near construction zones: keep windows closed in afternoon"],
    },
    kok: {
      headline: "पणजेंत आयज हवा बरी आसा",
      body:
        "आयज खंयच बंधन ना. दर्याचे वारें हवा नितळ दवरता. पर्वरी वाठारांत बांदकाम चलता थंय दनपारां धुल्ल वाडूं येता, तेन्ना जनेलां धांपून दवरात.",
      groups: ["सर्वसामान्य: सदांचेपरी कार्य", "बांदकाम लागीं: दनपारां जनेलां धांपात"],
    },
  },
};
