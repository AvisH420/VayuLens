# ingestion/

Reliable ingest of raw data from every upstream source. This layer knows nothing about the grid or
fusion — it fetches source-native records and hands them to [`data/`](../data/) to calibrate and fuse.

## Connectors

Six source connectors behind a common `BaseConnector` interface, each with a live-API mode and a
deterministic mock mode (selected by `USE_MOCK`), plus retry/backoff and rate-limit throttling:

- **`waqi`** — real-time PM2.5 / PM10 / NO₂ from ground stations (bounds query → per-station pollutant fetch).
- **`gee_satellite`** — Google Earth Engine: Sentinel-5P (NO₂, SO₂, UV-aerosol index) and MODIS aerosol
  optical depth, reduced to the area of interest. Supports headless service-account auth.
- **`open_meteo`** — wind speed/direction, temperature and gridded pollutant reanalysis, fetched in one
  bulk multi-point request.
- **`osm`** — OpenStreetMap land use, road density, industrial and construction footprints via Overpass.
- **`openaq`**, **`cpcb`** — additional ground-station connectors.

## Layout

- `base_connector.py` — retry, throttle, and the mock/real routing every connector inherits.
- `connectors/` — one module per source.
- `config.py` — endpoints, city bounding boxes, credentials (from `.env`), source rate limits.
- `scheduler.py`, `raw_store.py` — scheduled pulls and the raw-record store.

**Output:** raw, source-native records ready for `data/`.
