"""Role 1: raw-record persistence.

Saves/loads raw pulled dicts as Parquet files partitioned by source and date.
Directory layout::

    data_store/raw/{source_name}/YYYYMMDD_HHMMSS.parquet
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from ingestion import config as cfg


def _dir_for(source: str) -> Path:
    d = cfg.RAW_STORE_DIR / source
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_raw(source: str, records: list[dict], ts: datetime) -> Path | None:
    """Persist *records* to a Parquet file. Returns the written path."""
    if not records:
        return None
    path = _dir_for(source) / f"{ts:%Y%m%d_%H%M%S}.parquet"
    df = pd.DataFrame(records)
    if "ingested_at" not in df.columns:
        df["ingested_at"] = ts.isoformat()
    df.to_parquet(path, index=False)
    return path


def load_raw(source: str, since: datetime, until: datetime) -> list[dict]:
    """Load all raw Parquet files for *source* whose timestamp ∈ [since, until)."""
    d = _dir_for(source)
    frames: list[pd.DataFrame] = []
    for p in sorted(d.glob("*.parquet")):
        try:
            file_ts = datetime.strptime(p.stem, "%Y%m%d_%H%M%S")
        except ValueError:
            continue
        if since <= file_ts < until:
            frames.append(pd.read_parquet(p))
    if not frames:
        return []
    return pd.concat(frames, ignore_index=True).to_dict("records")
