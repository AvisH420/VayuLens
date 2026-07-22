# forecasting/

Answers *"where is this pollution going?"* and *"what if we intervened?"*.

## Components

- **`dispersion.py`** — a Gaussian-plume dispersion model with Pasquill-Gifford coefficients that
  projects how emissions from one cell travel downwind to another.
- **`predictor.py`** — produces the per-cell 72-hour AQI trajectory from a diurnal + wind-driven model,
  converting PM2.5 to the CPCB AQI (`pm25_to_aqi`).
- **`simulator.py`** — the policy what-if engine. It builds a source-to-receptor contribution matrix and
  **normalises it so contributions reconstruct each cell's real concentration** (avoiding
  double-counting), then applies an intervention's emission cuts and re-disperses — yielding realistic,
  defensible AQI deltas.
- **`models.py`** — forecast and simulation schemas.

**Input:** `Measurement` history + grid. **Output:** [`Forecast`](../contracts/forecast.py) horizons and
per-cell simulation results.
