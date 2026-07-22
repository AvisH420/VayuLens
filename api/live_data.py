"""Live-data layer: serve precomputed real snapshots when available.

The real Role 1->2 pipeline is far too slow to run per request, so it is run
offline (``scripts/build_snapshot.py``) and written to ``data/snapshots/{city}.json``
in the exact shape ``demo_engine.build_city`` returns. This module loads those
snapshots and exposes ``build_city`` / ``find_cell`` with the same signatures the
gateway already uses, so switching the grid/attribution/forecast/measurement
routes to real data needs no other changes.

Activation: set env ``REAL_DATA=true`` *and* have snapshot files present. When
either is missing, ``enabled()`` is False and the gateway keeps serving
``demo_engine`` — the demo is always a safe fallback. Chat, advisories, and
what-if simulation are not in the snapshot and continue to come from the demo
engine regardless.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_SNAP_DIR = Path(
    os.getenv("SNAPSHOT_DIR", Path(__file__).resolve().parent.parent / "data" / "snapshots")
)
_CACHE: dict[str, dict] = {}


def _flag_on() -> bool:
    return os.getenv("REAL_DATA", "").lower() in {"1", "true", "yes", "on"}


def _load(city: str) -> dict | None:
    if city in _CACHE:
        return _CACHE[city]
    path = _SNAP_DIR / f"{city}.json"
    if not path.is_file():
        return None
    try:
        snap = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — a bad snapshot must not break the API
        return None
    _CACHE[city] = snap
    return snap


def enabled() -> bool:
    """True when real data should be served (flag on and at least one snapshot)."""
    if not _flag_on():
        return False
    return _SNAP_DIR.is_dir() and any(_SNAP_DIR.glob("*.json"))


def has_city(city: str) -> bool:
    return _flag_on() and _load(city) is not None


def build_city(city: str) -> dict | None:
    """Return the real snapshot for *city*, or None if unavailable."""
    if not _flag_on():
        return None
    return _load(city)


def find_cell(cell_id: str) -> tuple[str, dict[str, Any]] | None:
    """Locate a cell across all snapshots. Returns (city_id, cell) or None."""
    if not _flag_on() or not _SNAP_DIR.is_dir():
        return None
    for path in _SNAP_DIR.glob("*.json"):
        snap = _load(path.stem)
        if not snap:
            continue
        for cell in snap.get("cells", []):
            if cell.get("cell_id") == cell_id:
                return snap["cfg"]["id"], cell
    return None
