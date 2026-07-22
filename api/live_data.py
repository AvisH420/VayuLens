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
import time
import urllib.request
from pathlib import Path
from typing import Any

_SNAP_DIR = Path(
    os.getenv("SNAPSHOT_DIR", Path(__file__).resolve().parent.parent / "data" / "snapshots")
)
# When set, snapshots are fetched from this base URL (the public raw URL of the
# `snapshots` data branch the refresh Action publishes to), so the site picks up
# fresh data without a redeploy. Example:
#   https://raw.githubusercontent.com/AvisH420/VayuLens/snapshots/data/snapshots
_SNAP_URL = os.getenv("SNAPSHOT_URL", "").rstrip("/")
_TTL = int(os.getenv("SNAPSHOT_TTL", "600"))  # seconds before a re-fetch

_CACHE: dict[str, dict] = {}
_FETCHED_AT: dict[str, float] = {}


def _flag_on() -> bool:
    return os.getenv("REAL_DATA", "").lower() in {"1", "true", "yes", "on"}


def _fetch_url(city: str) -> dict | None:
    try:
        with urllib.request.urlopen(f"{_SNAP_URL}/{city}.json", timeout=8) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 — network/JSON error -> fall back to local
        return None


def _load_local(city: str) -> dict | None:
    path = _SNAP_DIR / f"{city}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — a bad snapshot must not break the API
        return None


def _load(city: str) -> dict | None:
    """Return the snapshot for *city*: fresh from the URL (TTL-cached), else local.

    A remote fetch is attempted at most once per TTL; on any failure the last
    good cached copy or the committed local file is used, so the API never
    depends on the network being up.
    """
    now = time.time()
    fresh = city in _CACHE and (now - _FETCHED_AT.get(city, 0)) < _TTL
    if fresh:
        return _CACHE[city]

    snap = _fetch_url(city) if _SNAP_URL else None
    if snap is None:
        snap = _CACHE.get(city) or _load_local(city)  # keep last good / committed
    if snap is not None:
        _CACHE[city] = snap
        _FETCHED_AT[city] = now
    return snap


def _known_cities() -> list[str]:
    """City ids we have snapshots for — from the committed local files, or a
    fixed list when serving purely from the URL."""
    if _SNAP_DIR.is_dir():
        names = sorted(p.stem for p in _SNAP_DIR.glob("*.json"))
        if names:
            return names
    return ["delhi", "panaji"]


def enabled() -> bool:
    """True when real data should be served (flag on and a source is present)."""
    if not _flag_on():
        return False
    return bool(_SNAP_URL) or (_SNAP_DIR.is_dir() and any(_SNAP_DIR.glob("*.json")))


def has_city(city: str) -> bool:
    return _flag_on() and _load(city) is not None


def build_city(city: str) -> dict | None:
    """Return the real snapshot for *city*, or None if unavailable."""
    if not _flag_on():
        return None
    return _load(city)


def find_cell(cell_id: str) -> tuple[str, dict[str, Any]] | None:
    """Locate a cell across all snapshots. Returns (city_id, cell) or None."""
    if not _flag_on():
        return None
    for city in _known_cities():
        snap = _load(city)
        if not snap:
            continue
        for cell in snap.get("cells", []):
            if cell.get("cell_id") == cell_id:
                return snap["cfg"]["id"], cell
    return None
