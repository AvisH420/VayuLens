#!/usr/bin/env python
"""Run the real cross-role pipeline (Role 1 -> 2 -> 3) and print a summary.

    python scripts/run_realtime.py --city delhi [--advisory] [--hours 24]

Data source is decided by ingestion/config.py: mock by default, or live data
when USE_MOCK=false and credentials are present in .env (WAQI_TOKEN, etc.).
The public demo site is unaffected — this is a standalone validation run.
"""
from __future__ import annotations

import argparse
import logging
import statistics as st

from orchestrator.pipeline import run_full_pipeline
from ingestion import config as cfg


# CPCB PM2.5 -> AQI, for a human-readable headline
_BP = [(0, 30, 0, 50), (30, 60, 51, 100), (60, 90, 101, 200),
       (90, 120, 201, 300), (120, 250, 301, 400), (250, 1000, 401, 500)]


def _aqi(pm: float) -> float:
    for lo, hi, alo, ahi in _BP:
        if lo <= pm <= hi:
            return alo + (ahi - alo) * (pm - lo) / (hi - lo)
    return 500.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", default="delhi")
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--advisory", action="store_true", help="also run Role 3 RAG advisory")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(message)s",
    )

    print(f"data source: {'MOCK' if cfg.USE_MOCK else 'LIVE (real APIs)'}")
    res = run_full_pipeline(args.city, forecast_hours=args.hours, with_advisory=args.advisory)

    print(f"\n=== {res.city.upper()} ===")
    print(f"cells: {res.cells_used} used / {res.cells_total} total "
          f"({res.cells_skipped} skipped)")

    if res.attributions:
        # mean source split across the grid
        keys = ("traffic", "construction", "industry", "burning", "dust")
        means = {k: st.mean(getattr(a.sources, k) for a in res.attributions) for k in keys}
        print("mean source split: " +
              " | ".join(f"{k} {means[k]*100:.0f}%" for k in keys))
        conf = [a.confidence for a in res.attributions]
        print(f"attribution confidence: {min(conf):.2f}-{max(conf):.2f}")

    if res.forecasts:
        # headline AQI now (first forecast step) across the grid
        now = [f.horizon[0].aqi for f in res.forecasts if f.horizon]
        if now:
            print(f"forecast AQI (t+1): mean {st.mean(now):.0f}  max {max(now):.0f}")
        # trajectory for the single worst cell
        worst = max(res.forecasts, key=lambda f: f.horizon[0].aqi if f.horizon else 0)
        traj = [round(p.aqi) for p in worst.horizon[:6]]
        print(f"worst cell {worst.cell_id}: {traj} ... ({len(worst.horizon)}h)")

    if res.advisory is not None:
        a = res.advisory
        print(f"\nadvisory (grounded={a.grounded}, confidence={a.confidence}):")
        print("  " + a.answer[:400])
        print("  sources:", a.retrieved_sources)


if __name__ == "__main__":
    main()
