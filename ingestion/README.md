# ingestion/ — Schedulers, raw pulls & GEE satellite pipeline

**Owner:** Role 1 (Data Engineer)
**Builds against:** raw source APIs; output consumed by [`data/`](../data/README.md)

## Purpose

Reliably get raw data *in*. This layer knows nothing about the grid or fusion —
it only schedules and executes pulls and lands raw records in the raw store.

- **Schedulers** — recurring pull jobs per source (cron-style).
- **Raw pulls** — one-off / backfill pulls over a time window.
- **GEE satellite pipeline** — Google Earth Engine extraction of satellite
  products (AOD, aerosol index, NO2).

## Inputs

- Upstream source APIs & credentials (ground stations, GEE, met reanalysis).
- Schedule / backfill requests (source, time window, bbox).

## Outputs

- Raw, source-native records in the raw store, ready for [`data/`](../data/README.md)
  to calibrate and fuse.

## Key module

- `scheduler.py` — `schedule_pull`, `pull_raw`, `pull_gee_satellite`.
