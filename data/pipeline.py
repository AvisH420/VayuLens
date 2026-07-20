"""Role 1 — data layer pipeline.

Builds the ~1km analysis grid, connects to ground/satellite/meteorology
sources, and calibrates + fuses everything into ``Measurement`` records.

This replaces the original stubs with a real orchestrator that chains:
    grid_builder → ingestion connectors → alignment → calibration → fusion → gap_filling
"""

from __future__ import annotations

import logging
from datetime import datetime

from contracts.grid_cell import GridCell
from contracts.measurement import Measurement

from data import grid_builder, alignment, calibration, fusion, gap_filling
from ingestion.connectors import CONNECTORS

logger = logging.getLogger("vayulens.data")


def build_grid(
    bbox: tuple[float, float, float, float],
    cell_km: float = 1.0,
) -> list[GridCell]:
    """Build the ~1km analysis grid covering a bounding box.

    Args:
        bbox: (min_lon, min_lat, max_lon, max_lat) of the area of interest.
        cell_km: Target cell edge length in kilometres.

    Returns:
        One ``GridCell`` per cell, with ward / land-use / road-density /
        industrial attributes joined in.
    """
    # Step 1: Tessellate
    raw_cells = grid_builder.tessellate(bbox, cell_km)
    logger.info("Tessellated %d raw cells for bbox %s", len(raw_cells), bbox)

    # Step 2: Pull OSM context data
    osm_connector = CONNECTORS["osm"]()
    osm_records = osm_connector.pull(bbox, datetime.utcnow(), datetime.utcnow())
    logger.info("Fetched %d OSM context records", len(osm_records))

    # Step 3: Attach context
    grid = grid_builder.attach_context(raw_cells, osm_records, bbox)
    logger.info("Built grid with %d cells (with context)", len(grid))

    return grid


def fetch_source(
    source_name: str,
    since: datetime,
    until: datetime,
    bbox: tuple[float, float, float, float] | None = None,
) -> list[dict]:
    """Pull raw records from a single connected source.

    Args:
        source_name: Connector key, e.g. 'openaq', 'cpcb', 'gee_sentinel5p'.
        since: Inclusive start of the window (UTC).
        until: Exclusive end of the window (UTC).
        bbox: Bounding box; uses Delhi default if not specified.

    Returns:
        Raw, source-native records (not yet calibrated or gridded).
    """
    from ingestion import config as cfg

    if bbox is None:
        bbox = cfg.CITY_BBOX.get("delhi", (76.84, 28.40, 77.35, 28.88))

    connector_cls = CONNECTORS.get(source_name)
    if connector_cls is None:
        raise ValueError(f"Unknown source: {source_name}")

    connector = connector_cls()
    records = connector.pull(bbox, since, until)
    logger.info("[%s] Fetched %d raw records", source_name, len(records))
    return records


def calibrate(raw_records: list[dict], source_name: str) -> list[dict]:
    """Apply per-source calibration (bias correction, unit harmonisation).

    Args:
        raw_records: Output of ``fetch_source``.
        source_name: Connector key the records came from.

    Returns:
        Calibrated records in a common intermediate representation.
    """
    calibrated: list[dict] = []
    for rec in raw_records:
        cal = calibration.harmonise_units(rec, source_name)
        calibrated.append(cal)
    return calibrated


def fuse(
    grid: list[GridCell],
    calibrated_by_source: dict[str, list[dict]],
    timestamp: datetime,
) -> list[Measurement]:
    """Fuse multi-source calibrated data onto the grid for one timestamp.

    Args:
        grid: The analysis grid from ``build_grid``.
        calibrated_by_source: Calibrated records keyed by source name.
        timestamp: The observation time to produce measurements for (UTC).

    Returns:
        One ``Measurement`` per grid cell, with ``quality_score`` and
        ``uncertainty`` reflecting the fusion.
    """
    # Step 0: Pre-process GEE satellite records — expand product/value pairs
    #         into direct field names (e.g. product="aod", value=0.5 → aod=0.5)
    for source_name, records in calibrated_by_source.items():
        for rec in records:
            rec["source"] = source_name
            if rec.get("source") in ("gee_sentinel5p", "gee") and "product" in rec:
                product = rec["product"]
                value = rec.get("value")
                if product and value is not None:
                    rec[product] = value

    # Step 1: Snap all records to grid
    all_snapped: list[dict] = []
    for source_name, records in calibrated_by_source.items():
        snapped = alignment.snap_to_grid(records, grid)
        all_snapped.extend(snapped)

    logger.info("Snapped %d total records to grid", len(all_snapped))

    # Step 2: Resample to hourly buckets
    hourly = alignment.resample_hourly(all_snapped)

    # Step 3: For each cell, aggregate by source — use ANY available hour
    #         (prefer the target hour, fall back to closest available)
    hour_key = timestamp.strftime("%Y-%m-%dT%H:00")
    aligned_data: dict[str, dict[str, dict[str, float | None]]] = {}

    for cell_id, hour_buckets in hourly.items():
        records_this_hour = hour_buckets.get(hour_key, [])

        # If exact hour has no data, use the closest available hour
        if not records_this_hour and hour_buckets:
            # Pick the hour with the most records
            best_key = max(hour_buckets, key=lambda k: len(hour_buckets[k]))
            records_this_hour = hour_buckets[best_key]

        if records_this_hour:
            by_source = alignment.aggregate_by_source(records_this_hour)
            # Step 4: Calibrate (bias correct across sources)
            calibrated_sources = calibration.calibrate_all_sources(by_source)
            aligned_data[cell_id] = calibrated_sources

    logger.info("Cells with aligned data: %d / %d", len(aligned_data), len(grid))

    # Step 5: Fuse
    measurements = fusion.fuse_grid(grid, aligned_data, timestamp)
    fused_with_data = sum(1 for m in measurements if m.pm25 is not None)
    logger.info("Fused %d measurements (%d with PM2.5 data)", len(measurements), fused_with_data)

    # Step 6: Gap-fill
    measurements = gap_filling.fill_gaps(measurements)
    filled_count = sum(1 for m in measurements if m.pm25 is not None) - fused_with_data
    logger.info("Gap-filled %d additional cells", max(0, filled_count))

    return measurements


def run_pipeline(
    city_id: str = "delhi",
    since: datetime | None = None,
    until: datetime | None = None,
) -> tuple[list[GridCell], list[Measurement]]:
    """End-to-end pipeline: build grid → pull all sources → fuse.

    Convenience function that chains all steps for a single city and
    time window.

    Returns:
        (grid, measurements)
    """
    from ingestion import config as cfg
    from datetime import timedelta

    bbox = cfg.CITY_BBOX.get(city_id, cfg.CITY_BBOX["delhi"])

    if until is None:
        until = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    if since is None:
        since = until - timedelta(hours=24)

    logger.info("=== VayuLens pipeline: %s  %s → %s ===", city_id, since, until)

    # 1. Build grid
    grid = build_grid(bbox)

    # 2. Pull from all sources
    sources = ["openaq", "cpcb", "waqi", "open_meteo", "gee_sentinel5p"]
    calibrated_by_source: dict[str, list[dict]] = {}
    for src in sources:
        try:
            raw = fetch_source(src, since, until, bbox)
            cal = calibrate(raw, src)
            calibrated_by_source[src] = cal
        except Exception as exc:
            logger.warning("Source %s failed: %s — skipping", src, exc)

    # 3. Fuse for the most recent hour
    measurements = fuse(grid, calibrated_by_source, until)

    logger.info(
        "=== Pipeline complete: %d cells, %d measurements ===",
        len(grid), len(measurements),
    )
    return grid, measurements
