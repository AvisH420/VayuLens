"""Role 1: processed data persistence.

Stores/loads GridCell lists and Measurement batches as Parquet under::

    data_store/processed/grid/{city_id}.parquet
    data_store/processed/measurements/{city_id}/{date}.parquet
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from ingestion import config as cfg
from contracts.grid_cell import GridCell
from contracts.measurement import Measurement


# ── Grid persistence ──────────────────────────────────────────────────

def _grid_dir() -> Path:
    d = cfg.PROCESSED_STORE_DIR / "grid"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_grid(city_id: str, grid: list[GridCell]) -> Path:
    path = _grid_dir() / f"{city_id}.parquet"
    df = pd.DataFrame([g.model_dump() for g in grid])
    df.to_parquet(path, index=False)
    return path


def load_grid(city_id: str) -> list[GridCell]:
    path = _grid_dir() / f"{city_id}.parquet"
    if not path.is_file():
        return []
    df = pd.read_parquet(path)
    return [GridCell(**row) for row in df.to_dict("records")]


# ── Measurement persistence ──────────────────────────────────────────

def _meas_dir(city_id: str) -> Path:
    d = cfg.PROCESSED_STORE_DIR / "measurements" / city_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_measurements(city_id: str, measurements: list[Measurement], ts: datetime) -> Path:
    path = _meas_dir(city_id) / f"{ts:%Y%m%d_%H}.parquet"
    df = pd.DataFrame([m.model_dump() for m in measurements])
    # Convert datetime columns to string for Parquet compatibility
    if "timestamp" in df.columns:
        df["timestamp"] = df["timestamp"].astype(str)
    df.to_parquet(path, index=False)
    return path


def load_measurements(city_id: str, since: datetime, until: datetime) -> list[Measurement]:
    d = _meas_dir(city_id)
    frames: list[pd.DataFrame] = []
    for p in sorted(d.glob("*.parquet")):
        try:
            parts = p.stem.split("_")
            file_ts = datetime.strptime(parts[0] + parts[1], "%Y%m%d%H")
        except (ValueError, IndexError):
            continue
        if since <= file_ts < until:
            frames.append(pd.read_parquet(p))
    if not frames:
        return []

    df = pd.concat(frames, ignore_index=True)
    measurements = []
    for row in df.to_dict("records"):
        # Parse timestamp back if stored as string
        if isinstance(row.get("timestamp"), str):
            row["timestamp"] = datetime.fromisoformat(row["timestamp"])
        measurements.append(Measurement(**row))
    return measurements
