"""Role 1: ingestion — schedulers, raw pulls, and the GEE satellite pipeline.

Public API::

    from ingestion import pull_raw, pull_gee_satellite, schedule_pull
    from ingestion import start_scheduler, stop_scheduler
"""

from ingestion.scheduler import (
    schedule_pull,
    pull_raw,
    pull_gee_satellite,
    start_scheduler,
    stop_scheduler,
)

__all__ = [
    "schedule_pull",
    "pull_raw",
    "pull_gee_satellite",
    "start_scheduler",
    "stop_scheduler",
]
