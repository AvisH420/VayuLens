"""Deterministic demo engine behind the gateway.

A faithful Python port of ``frontend/src/lib/mock.js`` (same mulberry32 RNG,
same field math), so the gateway serves the exact data the frontend mocks
generate. When the real modules (data, attribution, forecasting, rag,
decision) land, their outputs replace these functions route by route and
nothing downstream changes shape.
"""

from __future__ import annotations

import math
import re
from typing import Any

# ---- city configuration (mirror of frontend/src/lib/cities.js) ----

CITIES: dict[str, dict[str, Any]] = {
    "delhi": {
        "id": "delhi",
        "name": "Delhi",
        "center": [77.16, 28.61],
        "zoom": 9.9,
        "bbox": {"latMin": 28.42, "latMax": 28.82, "lonMin": 76.92, "lonMax": 77.38},
        "latStep": 0.011,
        "lonStep": 0.0125,
        "baseAqi": 210,
        "wind": {"speed": 2.3, "dir": 300},
        "stations": 40,
        "wards": [
            {"name": "Anand Vihar", "lat": 28.647, "lon": 77.316, "kind": "traffic", "amp": 150},
            {"name": "Wazirpur", "lat": 28.7, "lon": 77.165, "kind": "industry", "amp": 120},
            {"name": "Okhla", "lat": 28.535, "lon": 77.28, "kind": "industry", "amp": 110},
            {"name": "Dwarka", "lat": 28.58, "lon": 77.045, "kind": "construction", "amp": 95},
            {"name": "Rohini", "lat": 28.74, "lon": 77.09, "kind": "construction", "amp": 80},
            {"name": "Narela", "lat": 28.8, "lon": 77.09, "kind": "burning", "amp": 105},
            {"name": "Mundka", "lat": 28.68, "lon": 77.03, "kind": "industry", "amp": 100},
            {"name": "Jahangirpuri", "lat": 28.73, "lon": 77.17, "kind": "burning", "amp": 90},
            {"name": "Punjabi Bagh", "lat": 28.67, "lon": 77.13, "kind": "traffic", "amp": 85},
            {"name": "Chandni Chowk", "lat": 28.656, "lon": 77.23, "kind": "traffic", "amp": 75},
            {"name": "RK Puram", "lat": 28.565, "lon": 77.175, "kind": "traffic", "amp": 60},
            {"name": "Patparganj", "lat": 28.62, "lon": 77.29, "kind": "construction", "amp": 70},
            {"name": "Najafgarh", "lat": 28.61, "lon": 76.98, "kind": "dust", "amp": 80},
            {"name": "Shahdara", "lat": 28.69, "lon": 77.29, "kind": "traffic", "amp": 78},
        ],
    },
    "panaji": {
        "id": "panaji",
        "name": "Panaji",
        "center": [73.83, 15.49],
        "zoom": 11.8,
        "bbox": {"latMin": 15.42, "latMax": 15.56, "lonMin": 73.76, "lonMax": 73.9},
        "latStep": 0.011,
        "lonStep": 0.0117,
        "baseAqi": 52,
        "wind": {"speed": 4.1, "dir": 250},
        "stations": 3,
        "wards": [
            {"name": "Panaji Centre", "lat": 15.496, "lon": 73.828, "kind": "traffic", "amp": 26},
            {"name": "Ribandar", "lat": 15.5, "lon": 73.86, "kind": "dust", "amp": 14},
            {"name": "Taleigao", "lat": 15.464, "lon": 73.822, "kind": "construction", "amp": 20},
            {"name": "Dona Paula", "lat": 15.457, "lon": 73.803, "kind": "traffic", "amp": 10},
            {"name": "Miramar", "lat": 15.48, "lon": 73.81, "kind": "traffic", "amp": 12},
            {"name": "St. Cruz", "lat": 15.49, "lon": 73.86, "kind": "burning", "amp": 16},
            {"name": "Bambolim", "lat": 15.46, "lon": 73.86, "kind": "construction", "amp": 14},
            {"name": "Porvorim", "lat": 15.53, "lon": 73.82, "kind": "construction", "amp": 18},
        ],
    },
}

SOURCE_KEYS = ["traffic", "construction", "industry", "burning", "dust"]

KIND_TO_SHARE_BIAS = {
    "traffic": {"traffic": 0.5, "dust": 0.12},
    "industry": {"industry": 0.55, "traffic": 0.1},
    "construction": {"construction": 0.5, "dust": 0.2},
    "burning": {"burning": 0.55, "dust": 0.1},
    "dust": {"dust": 0.5, "construction": 0.15},
}

# Forecast horizon: 13 steps of 6 h = now .. +72 h.
FC_STEPS = 13
FC_STEP_HOURS = 6


# ---- seeded RNG: mulberry32 with JS int32 semantics ----

def _u32(x: int) -> int:
    return x & 0xFFFFFFFF


def _i32(x: int) -> int:
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x & 0x80000000 else x


def _imul(a: int, b: int) -> int:
    return _i32(_u32(a) * _u32(b))


def _hash_seed(s: str) -> int:
    h = 1779033703
    for ch in s:
        h = _imul(h ^ ord(ch), 3432918353)
        h = _i32((_u32(h) << 13) | (_u32(h) >> 19))
    return _u32(h)


def _rng(seed_str: str):
    a = _hash_seed(seed_str)

    def rand() -> float:
        nonlocal a
        a = _i32(a + 0x6D2B79F5)
        t = _imul(a ^ (_u32(a) >> 15), _i32(1 | a))
        t = _i32(_i32(t + _imul(t ^ (_u32(t) >> 7), _i32(61 | t))) ^ t)
        return _u32(t ^ (_u32(t) >> 14)) / 4294967296

    return rand


# ---- spatial + temporal helpers ----

KM_PER_DEG_LAT = 111


def _dist_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dy = (lat2 - lat1) * KM_PER_DEG_LAT
    dx = (lon2 - lon1) * KM_PER_DEG_LAT * math.cos(lat1 * math.pi / 180)
    return math.sqrt(dx * dx + dy * dy)


def _diurnal(hour_of_day: float) -> float:
    """Traffic peaks ~8-10 and ~19-22, cleaner mid-afternoon."""
    morning = math.exp(-((hour_of_day - 9) ** 2) / 18)
    evening = math.exp(-((hour_of_day - 20.5) ** 2) / 14)
    return 0.88 + 0.22 * morning + 0.3 * evening


def _js_round(x: float) -> int:
    """Math.round: half always rounds up (Python's round is half-to-even)."""
    return math.floor(x + 0.5)


def _dominant_key(shares: dict[str, float]) -> str:
    return max(shares.items(), key=lambda kv: kv[1])[0]


# ---- city build (memoized) ----

_city_cache: dict[str, dict[str, Any]] = {}


def build_city(city_id: str) -> dict[str, Any]:
    if city_id in _city_cache:
        return _city_cache[city_id]
    cfg = CITIES[city_id]
    rand = _rng(city_id)
    cells: list[dict[str, Any]] = []
    now_hour = 11  # demo clock: late morning IST

    lat = cfg["bbox"]["latMin"]
    while lat < cfg["bbox"]["latMax"]:
        lon = cfg["bbox"]["lonMin"]
        while lon < cfg["bbox"]["lonMax"]:
            c_lat = lat + cfg["latStep"] / 2
            c_lon = lon + cfg["lonStep"] / 2

            # nearest ward seed -> ward assignment
            ward = cfg["wards"][0]
            ward_d = math.inf
            for w in cfg["wards"]:
                d = _dist_km(c_lat, c_lon, w["lat"], w["lon"])
                if d < ward_d:
                    ward_d = d
                    ward = w

            # pollution field: city base with edge falloff + hotspot gaussians
            d_center = _dist_km(c_lat, c_lon, cfg["center"][1], cfg["center"][0])
            aqi = cfg["baseAqi"] * max(0.45, 1 - d_center / 55)
            share_w = {"traffic": 0.2, "construction": 0.12, "industry": 0.08, "burning": 0.08, "dust": 0.18}
            for w in cfg["wards"]:
                d = _dist_km(c_lat, c_lon, w["lat"], w["lon"])
                g = w["amp"] * math.exp(-(d * d) / (2 * 3.2**2))
                aqi += g
                for k, v in KIND_TO_SHARE_BIAS[w["kind"]].items():
                    share_w[k] += (v * g) / (w["amp"] + 1)
            aqi = _js_round(min(485, max(18, aqi * (0.9 + rand() * 0.2))))

            total = sum(share_w.values())
            shares = {k: round(share_w[k] / total, 3) for k in SOURCE_KEYS}

            road_density = round(2 + share_w["traffic"] * 14 + rand() * 3, 1)
            industrial_flag = share_w["industry"] > 0.28
            if industrial_flag:
                land_use = "industrial"
            elif share_w["construction"] > 0.3:
                land_use = "mixed"
            elif road_density > 7:
                land_use = "commercial"
            elif rand() > 0.75:
                land_use = "green"
            else:
                land_use = "residential"

            # quality: better near hotspot seeds (stations cluster there)
            quality = round(min(0.95, max(0.55, 0.95 - ward_d * 0.03 - rand() * 0.1)), 2)

            # 72 h forecast at 6 h steps: diurnal cycle + city trend + noise
            trend_peak = 1.14 if city_id == "delhi" else 1.03
            forecast = []
            for i in range(FC_STEPS):
                h = i * FC_STEP_HOURS
                hod = (now_hour + h) % 24
                trend = 1 + (trend_peak - 1) * math.sin(min(math.pi, (h / 72) * math.pi))
                v = aqi * _diurnal(hod) * trend * (0.97 + rand() * 0.06)
                forecast.append(_js_round(min(500, max(12, v))))

            pm25 = round(aqi * 0.55 * (0.9 + rand() * 0.2), 1)
            dominant = _dominant_key(shares)
            cells.append(
                {
                    "cell_id": f"grid_{c_lat:.3f}_{c_lon:.3f}",
                    "lat": round(c_lat, 4),
                    "lon": round(c_lon, 4),
                    "bounds": [lon, lat, lon + cfg["lonStep"], lat + cfg["latStep"]],
                    "ward": ward["name"],
                    "land_use_class": land_use,
                    "road_density": road_density,
                    "industrial_flag": industrial_flag,
                    "aqi": aqi,
                    "shares": shares,
                    "confidence": round(0.55 + quality * 0.4 - (0.12 if shares[dominant] < 0.35 else 0), 2),
                    "quality_score": quality,
                    "uncertainty": round(pm25 * (1 - quality) * 0.9, 1),
                    "pm25": pm25,
                    "pm10": round(pm25 * 1.7, 1),
                    "no2": round(12 + shares["traffic"] * 90 * (aqi / 200), 1),
                    "aod": round(pm25 / 65, 2),
                    "forecast": forecast,
                }
            )
            lon += cfg["lonStep"]
        lat += cfg["latStep"]

    avg_aqi = _js_round(sum(c["aqi"] for c in cells) / len(cells))
    avg_shares = {
        k: round(sum(c["shares"][k] for c in cells) / len(cells), 3) for k in SOURCE_KEYS
    }
    built = {"cfg": cfg, "cells": cells, "avgAqi": avg_aqi, "avgShares": avg_shares, "nowHour": now_hour}
    _city_cache[city_id] = built
    return built


_cell_index: dict[str, tuple[str, dict[str, Any]]] = {}


def find_cell(cell_id: str) -> tuple[str, dict[str, Any]] | None:
    """Locate a cell (and its city) by id across all cities."""
    if not _cell_index:
        for city_id in CITIES:
            for cell in build_city(city_id)["cells"]:
                _cell_index[cell["cell_id"]] = (city_id, cell)
    return _cell_index.get(cell_id)


# ---- what-if simulator ----

ACTIONS: dict[str, dict[str, Any]] = {
    "halt_construction": {
        "label": "Halt construction",
        "detail": "Stop all C&D activity and truck movement at registered sites",
        "source": "construction",
        "efficacy": 0.8,
        "spill": 0.3,
        "citation": "GRAP Stage III · CAQM order s.11(1)",
    },
    "odd_even": {
        "label": "Odd-even traffic scheme",
        "detail": "Restrict private vehicles by plate parity, 7am-8pm",
        "source": "traffic",
        "efficacy": 0.45,
        "spill": 0.45,
        "citation": "GRAP Stage IV · Motor Vehicles Act s.115",
    },
    "industry_curbs": {
        "label": "Industrial fuel curbs",
        "detail": "Suspend non-PNG industrial units in the zone",
        "source": "industry",
        "efficacy": 0.7,
        "spill": 0.35,
        "citation": "Air Act 1981 s.31A · GRAP Stage III",
    },
    "burning_ban": {
        "label": "Open-burning enforcement",
        "detail": "Patrol and fine open waste and biomass burning",
        "source": "burning",
        "efficacy": 0.65,
        "spill": 0.25,
        "citation": "SWM Rules 2016 r.15 · NGT order 2016",
    },
}


def run_scenario(city_id: str, action: str, ward: str, days: int) -> dict[str, Any]:
    cells = build_city(city_id)["cells"]
    act = ACTIONS[action]
    horizon_h = min(72, days * 24)
    results: dict[str, dict[str, list[int]]] = {}
    zone_cells = 0
    sum_delta_48 = 0
    peak = 0

    for cell in cells:
        in_zone = ward == "all" or cell["ward"] == ward
        strength = 1 if in_zone else act["spill"] * 0.4
        share = cell["shares"][act["source"]]
        scenario = []
        for i, v in enumerate(cell["forecast"]):
            h = i * FC_STEP_HOURS
            # effect ramps in over ~12 h (dispersion lag), out after the window
            ramp = (
                0
                if h <= 0
                else min(1, h / 12) * (1 if h <= horizon_h else max(0, 1 - (h - horizon_h) / 18))
            )
            scenario.append(_js_round(v * (1 - share * act["efficacy"] * strength * ramp)))
        delta = [s - f for s, f in zip(scenario, cell["forecast"])]
        results[cell["cell_id"]] = {"scenario": scenario, "delta": delta}
        if in_zone:
            zone_cells += 1
            sum_delta_48 += delta[8]  # +48 h
            peak = min(peak, min(delta))

    return {
        "action": act,
        "ward": ward,
        "days": days,
        "results": results,
        "summary": {
            "zoneCells": zone_cells,
            "avgDelta48": _js_round(sum_delta_48 / zone_cells) if zone_cells else 0,
            "peakDelta": peak,
            "onsetHours": 12,
        },
    }


# ---- recommendations ----

def _rec_traffic(c: dict[str, Any]) -> dict[str, str]:
    return {
        "action": f"Divert heavy vehicles off the {c['ward']} corridor and run PUC checks at entry points",
        "justification": (
            f"Traffic contributes {_js_round(c['shares']['traffic'] * 100)}% of the load in this cell; "
            f"NO2 at {c['no2']} µg/m³ confirms a combustion signature."
        ),
        "regulation_citation": "GRAP Stage II s.6 · CMVR r.115(7)",
    }


def _rec_construction(c: dict[str, Any]) -> dict[str, str]:
    return {
        "action": f"Inspect active construction sites in {c['ward']} for dust-control compliance; halt non-compliant sites",
        "justification": (
            f"Construction accounts for {_js_round(c['shares']['construction'] * 100)}% here, "
            "consistent with high AOD against a moderate NO2 column."
        ),
        "regulation_citation": "C&D Waste Rules 2016 r.4 · GRAP Stage III",
    }


def _rec_industry(c: dict[str, Any]) -> dict[str, str]:
    return {
        "action": f"Audit fuel use at registered units near {c['ward']}; enforce PNG switchover or suspend operations",
        "justification": (
            f"Industrial share is {_js_round(c['shares']['industry'] * 100)}% with a registered source inside the cell."
        ),
        "regulation_citation": "Air Act 1981 s.31A · CAQM direction 2023",
    }


def _rec_burning(c: dict[str, Any]) -> dict[str, str]:
    return {
        "action": f"Deploy night patrols against open waste burning in {c['ward']}; issue on-the-spot fines",
        "justification": (
            f"Burning contributes {_js_round(c['shares']['burning'] * 100)}%; "
            "elevated UV aerosol index flags fresh smoke."
        ),
        "regulation_citation": "SWM Rules 2016 r.15 · NGT order of 22.12.2016",
    }


def _rec_dust(c: dict[str, Any]) -> dict[str, str]:
    ratio = c["pm10"] / c["pm25"]
    return {
        "action": f"Schedule mechanized sweeping and water sprinkling on arterial roads in {c['ward']}",
        "justification": (
            f"Road and soil dust make up {_js_round(c['shares']['dust'] * 100)}% of the coarse fraction "
            f"(PM10/PM2.5 ratio {ratio:.1f})."
        ),
        "regulation_citation": "GRAP Stage I s.9 · NCAP city action plan",
    }


REC_TEMPLATES = {
    "traffic": _rec_traffic,
    "construction": _rec_construction,
    "industry": _rec_industry,
    "burning": _rec_burning,
    "dust": _rec_dust,
}


def recommendations_for(cell: dict[str, Any]) -> list[dict[str, Any]]:
    ranked = sorted(cell["shares"].items(), key=lambda kv: kv[1], reverse=True)[:3]
    return [
        {
            "cell_id": cell["cell_id"],
            **REC_TEMPLATES[key](cell),
            "priority_score": round(min(1, share * (cell["aqi"] / 320)), 2),
        }
        for key, share in ranked
    ]


# ---- grounded chat ----

CHAT_ANSWERS: list[dict[str, Any]] = [
    {
        "match": re.compile(r"grap|severe|stage|mandat|protocol", re.I),
        "text": (
            "Anand Vihar is in the Severe band (AQI 412) mainly because of traffic (41%) and "
            "construction (22%) under stagnant north-westerly winds. At this level GRAP Stage III "
            "is in force: it mandates a halt on non-exempt construction and demolition, intensified "
            "mechanized road sweeping, and a ban on BS-III petrol / BS-IV diesel cars in the NCT. "
            "Stage IV triggers if AQI holds above 450 for 24 h."
        ),
        "citations": [
            {"doc": "GRAP (CAQM, rev. 2024)", "ref": "Stage III, s.1-4"},
            {"doc": "CAQM direction no. 72", "ref": "para 3"},
        ],
        "confidence": 0.89,
        "retrieved": 4,
    },
    {
        "match": re.compile(r"construction|dust|c&d|site", re.I),
        "text": (
            "Construction dust is regulated by the C&D Waste Management Rules 2016: sites over "
            "20,000 m² need dust screens, covered storage, and wheel-washing. Under GRAP Stage III "
            "all non-exempt C&D activity must stop. VayuLens flags 3 cells in Dwarka where the "
            "construction share exceeds 35% while AQI is Poor or worse; those sites are the "
            "highest-priority inspections today."
        ),
        "citations": [
            {"doc": "C&D Waste Rules 2016", "ref": "r.4(1), r.4(3)"},
            {"doc": "GRAP (CAQM, rev. 2024)", "ref": "Stage III, s.1"},
        ],
        "confidence": 0.84,
        "retrieved": 5,
    },
    {
        "match": re.compile(r"school|child|advisory|health|outdoor|elderly", re.I),
        "text": (
            "For today's Very Poor band in most of central Delhi, the standard health advisory "
            "applies: schools should suspend outdoor assembly and sports (CBSE circular under GRAP "
            "Stage III makes this binding when invoked), outdoor workers should get N95 masks and "
            "staggered shifts, and people with cardiac or respiratory conditions should avoid "
            "morning hours, when the surface inversion holds pollutants low. Ward-level advisories "
            "in Hindi are available in the Advisory tab."
        ),
        "citations": [
            {"doc": "MoHFW health advisory on air pollution, 2023", "ref": "s.2"},
            {"doc": "GRAP (CAQM, rev. 2024)", "ref": "Stage III, s.8"},
        ],
        "confidence": 0.81,
        "retrieved": 3,
    },
    {
        "match": re.compile(r"panaji|goa|clean|contrast", re.I),
        "text": (
            "Panaji sits in the Satisfactory band today (city mean AQI 78); the sea breeze at "
            "4 m/s keeps dispersion strong. The main local signal is construction around Porvorim "
            "and Taleigao, at roughly a quarter of the local load. No GRAP-equivalent action is "
            "warranted; the NCAP city plan for Panaji focuses on road-dust control and "
            "construction-site norms."
        ),
        "citations": [
            {"doc": "NCAP city action plan, Panaji", "ref": "s.3.2"},
            {"doc": "GSPCB ambient bulletin", "ref": "Jul 2026"},
        ],
        "confidence": 0.77,
        "retrieved": 3,
    },
    {
        "match": re.compile(r"inspect|enforce|priorit|fine|penal", re.I),
        "text": (
            "Today's enforcement queue ranks Wazirpur first: the industrial share there is 48% "
            "with AQI 388, and Air Act s.31A lets the board order closure or fuel restrictions "
            "directly. Second is the Anand Vihar corridor for PUC and heavy-vehicle checks, third "
            "the Narela periphery for open-burning patrols, where the UV aerosol index has been "
            "elevated for 36 h. Each entry in the queue carries the exact clause that authorizes "
            "the action."
        ),
        "citations": [
            {"doc": "Air (Prevention & Control) Act 1981", "ref": "s.31A"},
            {"doc": "CAQM enforcement SOP", "ref": "s.5"},
        ],
        "confidence": 0.86,
        "retrieved": 5,
    },
]

ABSTAIN_ANSWER: dict[str, Any] = {
    "text": (
        "I can't ground an answer for that in the indexed corpus (retrieval confidence 0.31, "
        "below the 0.55 answer threshold), so I won't guess. I can answer reliably about GRAP "
        "stages and triggers, construction-dust rules, health advisories, enforcement "
        "priorities, and today's readings for Delhi and Panaji."
    ),
    "citations": [],
    "confidence": 0.31,
    "retrieved": 1,
    "abstained": True,
}


def chat_answer(query: str) -> dict[str, Any]:
    for a in CHAT_ANSWERS:
        if a["match"].search(query):
            return {k: v for k, v in a.items() if k != "match"} | {"abstained": False}
    return dict(ABSTAIN_ANSWER)


# ---- citizen advisories ----

ADVISORIES: dict[str, dict[str, dict[str, Any]]] = {
    "delhi": {
        "en": {
            "headline": "Very Poor air over most of Delhi today",
            "body": (
                "Keep children indoors during morning school hours; the inversion traps pollutants "
                "until about 11am. Outdoor workers should use N95 masks. Avoid burning waste; report "
                "it on 311. Conditions ease slightly after tomorrow evening's wind shift."
            ),
            "groups": [
                "Schools: move assembly and sports indoors",
                "Outdoor workers: N95, staggered shifts",
                "Elderly & cardiac patients: avoid 6-10am outdoors",
            ],
        },
        "hi": {
            "headline": "आज दिल्ली की हवा गंभीर रूप से खराब",
            "body": (
                "सुबह के स्कूल समय में बच्चों को घर के अंदर रखें; लगभग 11 बजे तक प्रदूषण नीचे टिका रहता है। "
                "बाहर काम करने वाले N95 मास्क पहनें। कूड़ा न जलाएं; 311 पर सूचना दें।"
            ),
            "groups": ["स्कूल: सभा और खेल अंदर करें", "बाहरी कामगार: N95 मास्क", "बुजुर्ग: सुबह 6-10 बजे बाहर न निकलें"],
        },
    },
    "panaji": {
        "en": {
            "headline": "Satisfactory air across Panaji",
            "body": (
                "No restrictions needed today. The sea breeze keeps dispersion strong. Construction "
                "zones around Porvorim may see brief dust spikes in the afternoon; keep windows on "
                "that side closed if you are sensitive."
            ),
            "groups": [
                "General public: normal activity",
                "Near construction zones: keep windows closed in afternoon",
            ],
        },
        "kok": {
            "headline": "पणजेंत आयज हवा बरी आसा",
            "body": (
                "आयज खंयच बंधन ना. दर्याचे वारें हवा नितळ दवरता. पर्वरी वाठारांत बांदकाम चलता थंय "
                "दनपारां धुल्ल वाडूं येता, तेन्ना जनेलां धांपून दवरात."
            ),
            "groups": ["सर्वसामान्य: सदांचेपरी कार्य", "बांदकाम लागीं: दनपारां जनेलां धांपात"],
        },
    },
}
