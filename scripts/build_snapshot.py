#!/usr/bin/env python
"""Precompute a real-data snapshot the API can serve instantly.

The real Role 1->2 pipeline takes minutes (satellite calls), which is far too
slow for a web request. This script runs it offline and writes a JSON snapshot
in the *exact* shape ``demo_engine.build_city`` returns, so the gateway can
serve real data with zero frontend changes and no per-request latency.

    python scripts/build_snapshot.py [--city delhi] [--out data/snapshots]

Data source is decided by ingestion/config.py (USE_MOCK / .env). With
USE_MOCK=false and credentials present, the snapshot is real.

Calibration note: satellite AOD -> PM2.5 regression tends to overestimate
surface PM2.5 (it sees the whole air column). We trust the ground stations
(WAQI) for the absolute level and the satellite grid for the spatial pattern:
every cell's PM2.5 is rescaled so the grid median matches the ground-station
median. Shares and geometry are unaffected.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import statistics as st
from datetime import datetime, timedelta
from pathlib import Path

from api import demo_engine as demo
from attribution.engine import attribute_sources
from attribution.models import GridAttributionRequest
from data import pipeline as role1
from forecasting.predictor import generate_forecast
from ingestion import config as cfg
from ingestion.connectors.waqi import WAQIConnector
from orchestrator.pipeline import build_grid_inputs

log = logging.getLogger("vayulens.snapshot")

_BP = [(0, 30, 0, 50), (30, 60, 51, 100), (60, 90, 101, 200),
       (90, 120, 201, 300), (120, 250, 301, 400), (250, 500, 401, 500)]
_FC_STEP = 6          # hours between forecast points (matches demo_engine)
_FC_POINTS = 13       # 0..72h inclusive


def pm25_to_aqi(pm: float) -> int:
    for lo, hi, alo, ahi in _BP:
        if lo <= pm <= hi:
            return round(alo + (ahi - alo) * (pm - lo) / (hi - lo))
    return 500


def _ground_median_pm25(bbox, until) -> float | None:
    """Median PM2.5 across live WAQI ground stations — the calibration anchor."""
    try:
        recs = WAQIConnector().pull(bbox, until - timedelta(hours=1), until, use_mock=cfg.USE_MOCK)
    except Exception as exc:  # noqa: BLE001
        log.warning("WAQI anchor pull failed (%s); skipping recalibration.", exc)
        return None
    vals = [r["pm25"] for r in recs if r.get("pm25") is not None
            and not r.get("pm25_derived_from_aqi")]
    return st.median(vals) if vals else None


def build_city_snapshot(city: str) -> dict:
    """Run the real pipeline for one city and shape it like build_city()."""
    bbox = cfg.CITY_BBOX.get(city, cfg.CITY_BBOX["delhi"])
    until = role1.cfg.utc_now().replace(minute=0, second=0, microsecond=0)
    since = until - timedelta(hours=24)

    grid, measurements = role1.run_pipeline(city, sources=role1.WORKING_SOURCES)
    inputs, skipped = build_grid_inputs(grid, measurements)
    log.info("%s: %d cells, %d usable for attribution (%d skipped)",
             city, len(measurements), len(inputs), skipped)
    if not inputs:
        raise RuntimeError(f"No usable cells for {city}; cannot build a real snapshot.")

    # --- ground-anchored PM2.5 recalibration (satellite bias fix) ---
    grid_med = st.median([c.pm25 for c in inputs])
    ground_med = _ground_median_pm25(bbox, until)
    k = 1.0
    if ground_med and grid_med:
        k = ground_med / grid_med
        log.info("%s: recalibrating PM2.5 x%.3f (grid median %.1f -> ground %.1f)",
                 city, k, grid_med, ground_med)
        for c in inputs:
            c.pm25 = max(1.0, c.pm25 * k)

    # --- Role 2: attribution + forecast on calibrated inputs ---
    attr = {a.cell_id: a for a in
            attribute_sources(GridAttributionRequest(cells=inputs)).attributions}
    fc = {f.cell_id: f for f in generate_forecast(inputs, _FC_STEP * (_FC_POINTS - 1)).forecasts}

    # real per-cell records (only fully-attributed cells)
    real_cells = []
    for c in inputs:
        a = attr.get(c.cell_id)
        f = fc.get(c.cell_id)
        if a is None or f is None:
            continue
        s = a.sources
        forecast = [pm25_to_aqi(c.pm25)] + [
            int(f.horizon[h - 1].aqi) for h in range(_FC_STEP, _FC_STEP * (_FC_POINTS - 1) + 1, _FC_STEP)
            if h - 1 < len(f.horizon)
        ]
        real_cells.append({
            "lat": c.lat, "lon": c.lon, "pm25": round(c.pm25, 1),
            "pm10": round(c.pm10, 1) if c.pm10 else round(c.pm25 * 1.6, 1),
            "no2": round(c.no2, 1), "aod": round(c.aod, 3),
            "aqi": pm25_to_aqi(c.pm25),
            "shares": {
                "traffic": round(s.traffic, 3), "construction": round(s.construction, 3),
                "industry": round(s.industry, 3), "burning": round(s.biomass, 3),
                "dust": round(s.dust, 3),
            },
            "confidence": round(a.confidence_score, 2),
            "forecast": forecast[:_FC_POINTS],
        })

    # --- map real values onto demo's grid geometry (nearest cell) ---
    canvas = demo.build_city(city)
    _paint(canvas, real_cells)
    canvas["source"] = "real"
    canvas["generated_at"] = until.isoformat() + "Z"
    return canvas


def _paint(canvas: dict, real_cells: list[dict]) -> None:
    """Overwrite each demo cell's data layers with the nearest real cell."""
    try:
        import numpy as np
        rc = np.array([[c["lat"], c["lon"]] for c in real_cells])

        def nearest(lat, lon):
            d = (rc[:, 0] - lat) ** 2 + (rc[:, 1] - lon) ** 2
            return real_cells[int(d.argmin())]
    except Exception:  # numpy absent — pure-python fallback
        def nearest(lat, lon):
            return min(real_cells,
                       key=lambda c: (c["lat"] - lat) ** 2 + (c["lon"] - lon) ** 2)

    aqis, shares_acc = [], {k: [] for k in ("traffic", "construction", "industry", "burning", "dust")}
    for cell in canvas["cells"]:
        r = nearest(cell["lat"], cell["lon"])
        cell.update({
            "aqi": r["aqi"], "pm25": r["pm25"], "pm10": r["pm10"], "no2": r["no2"],
            "aod": r["aod"], "shares": r["shares"], "confidence": r["confidence"],
            "forecast": r["forecast"],
        })
        aqis.append(r["aqi"])
        for k in shares_acc:
            shares_acc[k].append(r["shares"][k])
    canvas["avgAqi"] = round(st.mean(aqis))
    canvas["avgShares"] = {k: round(st.mean(v), 3) for k, v in shares_acc.items()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", action="append", help="repeatable; default delhi+panaji")
    ap.add_argument("--out", default="data/snapshots")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(message)s")

    cities = args.city or ["delhi", "panaji"]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    print(f"data source: {'MOCK' if cfg.USE_MOCK else 'LIVE'}")
    for city in cities:
        t0 = datetime.now()
        snap = build_city_snapshot(city)
        (out / f"{city}.json").write_text(json.dumps(snap), encoding="utf-8")
        print(f"  {city}: avgAQI {snap['avgAqi']}  "
              f"({len(snap['cells'])} cells, {(datetime.now()-t0).seconds}s) "
              f"-> {out/f'{city}.json'}")


if __name__ == "__main__":
    main()
