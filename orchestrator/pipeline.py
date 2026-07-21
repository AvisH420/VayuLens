"""End-to-end orchestration of the real pipeline: Role 1 -> Role 2 -> Role 3.

This is the assembly layer that ties the roles together on *real* (or mock)
data, independent of the demo engine that serves the public site:

  Role 1  data.pipeline.run_pipeline(city)   -> (grid, measurements)
  join    Measurement (dynamic) + GridCell (static) -> GridCellInput
  Role 2  attribute_sources / generate_forecast / simulate_intervention
  adapt   api.role2_adapter -> contracts.Attribution / contracts.Forecast
  Role 3  (optional) RAG advisory grounded in the regulation corpus

Whether Role 1 pulls real or mock data is controlled by ``ingestion.config``
(``USE_MOCK`` / the ``.env`` file) — this module does not care which; it wires
the shapes together. Run it with mock data today to prove the chain, then set
``USE_MOCK=false`` + credentials to run it on live data with no code change.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from attribution.engine import attribute_sources
from attribution.models import GridAttributionRequest, GridCellInput
from contracts.grid_cell import GridCell
from contracts.measurement import Measurement
from data import pipeline as role1
from forecasting.predictor import generate_forecast

from api.role2_adapter import to_contract_attribution, to_contract_forecast

log = logging.getLogger("vayulens.orchestrator")

# Required (non-Optional) GridCellInput fields. A cell missing any of these
# after gap-filling can't be attributed, so it's skipped rather than defaulted
# to a fabricated value.
_REQUIRED = (
    "lat", "lon", "pm25", "no2", "so2", "aod",
    "uv_aerosol_index", "wind_speed", "wind_direction",
)


def build_grid_inputs(
    grid: list[GridCell], measurements: list[Measurement]
) -> tuple[list[GridCellInput], int]:
    """Join per-cell Measurement (dynamic) + GridCell (static) into Role 2 input.

    Returns ``(inputs, skipped)`` — ``skipped`` counts cells dropped because a
    required field was still ``None`` after fusion + gap-filling.
    """
    static = {c.cell_id: c for c in grid}
    inputs: list[GridCellInput] = []
    skipped = 0

    for m in measurements:
        cell = static.get(m.cell_id)
        if cell is None:
            skipped += 1
            continue

        values = {
            "cell_id": m.cell_id,
            "lat": m.lat,
            "lon": m.lon,
            "pm25": m.pm25,
            "pm10": m.pm10,
            "no2": m.no2,
            "so2": m.so2,
            "co": None,  # not produced by Role 1 yet; Optional in Role 2
            "aod": m.aod,
            "uv_aerosol_index": m.uv_aerosol_index,
            "wind_speed": m.wind_speed,
            "wind_direction": m.wind_direction,
            "road_density": cell.road_density,
            "industrial_proximity": cell.industrial_proximity,
            "construction_density": cell.construction_density,
        }
        if any(values[f] is None for f in _REQUIRED):
            skipped += 1
            continue
        inputs.append(GridCellInput(**values))

    return inputs, skipped


@dataclass
class PipelineResult:
    city: str
    cells_total: int
    cells_used: int
    cells_skipped: int
    attributions: list = field(default_factory=list)   # contracts.Attribution
    forecasts: list = field(default_factory=list)       # contracts.Forecast
    advisory: Any | None = None                          # rag GroundedAnswer | None


def run_full_pipeline(
    city: str = "delhi",
    *,
    forecast_hours: int = 24,
    with_advisory: bool = False,
) -> PipelineResult:
    """Run Role 1 -> 2 (-> 3) end to end and return contract-shaped results."""
    log.info("=== orchestrator: %s ===", city)

    # 1. Role 1 — ingestion + fusion (mock or real per ingestion.config)
    grid, measurements = role1.run_pipeline(city)
    log.info("Role 1: %d grid cells, %d measurements", len(grid), len(measurements))

    # 2. Assemble Role 2 inputs
    inputs, skipped = build_grid_inputs(grid, measurements)
    log.info("Assembled %d GridCellInputs (%d skipped for missing fields)",
             len(inputs), skipped)

    result = PipelineResult(
        city=city, cells_total=len(measurements),
        cells_used=len(inputs), cells_skipped=skipped,
    )
    if not inputs:
        log.warning("No usable cells — nothing to attribute or forecast.")
        return result

    # 3. Role 2 — attribution + forecast, mapped to platform contracts
    attr_resp = attribute_sources(GridAttributionRequest(cells=inputs))
    result.attributions = [to_contract_attribution(a) for a in attr_resp.attributions]

    fc_resp = generate_forecast(inputs, forecast_hours)
    result.forecasts = [to_contract_forecast(f) for f in fc_resp.forecasts]

    # 4. Role 3 — optional grounded advisory for the worst cell
    if with_advisory:
        result.advisory = _advisory_for_worst(inputs, result.attributions)

    return result


def _advisory_for_worst(inputs, attributions):
    """Ground a citizen advisory for the highest-PM2.5 cell, if the corpus exists."""
    try:
        from rag.pipeline import get_pipeline
    except Exception as exc:  # noqa: BLE001 — RAG is optional to the chain
        log.warning("RAG unavailable (%s); skipping advisory.", exc)
        return None

    worst = max(inputs, key=lambda c: c.pm25)
    attr = next((a for a in attributions if a.cell_id == worst.cell_id), None)
    dominant = "pollution"
    if attr is not None:
        dominant = max(attr.sources.model_dump().items(), key=lambda kv: kv[1])[0]

    situation = (
        f"PM2.5 is {worst.pm25:.0f} ug/m3 in this area, driven mainly by "
        f"{dominant}. What mitigation actions and health advice apply?"
    )
    try:
        return get_pipeline().recommend(situation)
    except Exception as exc:  # noqa: BLE001 — needs an indexed corpus
        log.warning("Advisory generation failed (%s); skipping.", exc)
        return None
