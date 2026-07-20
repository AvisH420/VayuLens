"""Role 1 — ingestion scheduler.

Schedules and performs raw pulls from upstream sources, including the Google
Earth Engine (GEE) satellite pipeline. Hands raw records to ``data/`` for
calibration and fusion.

Replaces the original stubs with a real APScheduler-backed implementation.
"""

from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from ingestion import config as cfg
from ingestion import raw_store
from ingestion.connectors import CONNECTORS

logger = logging.getLogger("vayulens.ingestion")

# Module-level scheduler instance
_scheduler: BackgroundScheduler | None = None


def _get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
    return _scheduler


def _run_pull_job(source_name: str, bbox: tuple[float, float, float, float]) -> None:
    """Callback executed by APScheduler for each recurring job."""
    connector_cls = CONNECTORS.get(source_name)
    if connector_cls is None:
        logger.error("Unknown source: %s", source_name)
        return

    connector = connector_cls()
    now = datetime.utcnow()
    # Pull the last hour of data
    from datetime import timedelta
    since = now - timedelta(hours=1)

    try:
        records = connector.pull(bbox, since, now)
        if records:
            raw_store.save_raw(source_name, records, now)
            logger.info("[%s] Scheduled pull saved %d records", source_name, len(records))
        else:
            logger.info("[%s] Scheduled pull returned 0 records", source_name)
    except Exception as exc:
        logger.error("[%s] Scheduled pull failed: %s", source_name, exc)


def schedule_pull(
    source_name: str,
    cron: str,
    bbox: tuple[float, float, float, float] | None = None,
) -> str:
    """Register a recurring raw pull for a source.

    Args:
        source_name: Connector key, e.g. 'openaq', 'cpcb', 'gee_sentinel5p'.
        cron: Cron expression describing the pull cadence (e.g. '0 * * * *').
        bbox: Bounding box; defaults to Delhi if not specified.

    Returns:
        A job id for the registered schedule.
    """
    if bbox is None:
        bbox = cfg.CITY_BBOX.get("delhi", (76.84, 28.40, 77.35, 28.88))

    scheduler = _get_scheduler()
    trigger = CronTrigger.from_crontab(cron)
    job = scheduler.add_job(
        _run_pull_job,
        trigger=trigger,
        args=[source_name, bbox],
        id=f"pull_{source_name}",
        replace_existing=True,
    )
    logger.info("Scheduled %s with cron '%s' → job %s", source_name, cron, job.id)
    return job.id


def pull_raw(
    source_name: str,
    since: datetime,
    until: datetime,
    bbox: tuple[float, float, float, float] | None = None,
) -> list[dict]:
    """Perform a one-off raw pull for a source over a time window.

    Args:
        source_name: Connector key.
        since: Inclusive start (UTC).
        until: Exclusive end (UTC).
        bbox: Bounding box; defaults to Delhi.

    Returns:
        Raw, source-native records persisted to the raw store.
    """
    if bbox is None:
        bbox = cfg.CITY_BBOX.get("delhi", (76.84, 28.40, 77.35, 28.88))

    connector_cls = CONNECTORS.get(source_name)
    if connector_cls is None:
        raise ValueError(f"Unknown source: {source_name}")

    connector = connector_cls()
    records = connector.pull(bbox, since, until)

    if records:
        raw_store.save_raw(source_name, records, datetime.utcnow())

    return records


def pull_gee_satellite(
    product: str,
    bbox: tuple[float, float, float, float],
    since: datetime,
    until: datetime,
) -> list[dict]:
    """Pull a satellite product via the Google Earth Engine pipeline.

    Args:
        product: GEE product key (e.g. 'gee_sentinel5p', 'gee_modis').
        bbox: (min_lon, min_lat, max_lon, max_lat) area of interest.
        since: Inclusive start (UTC).
        until: Exclusive end (UTC).

    Returns:
        Raw raster/tabular records (AOD, aerosol index, NO2, ...) for ``data/``.
    """
    return pull_raw(product, since, until, bbox=bbox)


def start_scheduler() -> None:
    """Start the background scheduler with default jobs."""
    scheduler = _get_scheduler()
    if scheduler.running:
        return

    delhi_bbox = cfg.CITY_BBOX["delhi"]

    # Default schedules
    schedule_pull("openaq",        "0 * * * *",   delhi_bbox)   # every hour
    schedule_pull("cpcb",          "0 * * * *",   delhi_bbox)   # every hour
    schedule_pull("waqi",          "0 * * * *",   delhi_bbox)   # every hour
    schedule_pull("open_meteo",    "0 */3 * * *", delhi_bbox)   # every 3 hours
    schedule_pull("gee_sentinel5p","0 6 * * *",   delhi_bbox)   # daily at 6 AM UTC
    schedule_pull("osm",           "0 0 * * 0",   delhi_bbox)   # weekly (Sunday)

    scheduler.start()
    logger.info("Ingestion scheduler started with %d jobs", len(scheduler.get_jobs()))


def stop_scheduler() -> None:
    """Shut down the background scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()
        logger.info("Ingestion scheduler stopped")
    _scheduler = None
