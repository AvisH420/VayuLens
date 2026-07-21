"""Adapter: Role 2 (attribution + forecasting) output -> platform contracts.

Role 2's internal Pydantic models (``attribution.models``,
``forecasting.models``) are close to ``contracts/`` but not identical, and
they can't simply be renamed because the modules depend on their own shapes:
the simulator uses the ``other`` background share and the ``biomass`` key in
its physics. So the translation lives here, at the boundary, instead.

Differences reconciled:

  attribution
    sources.biomass        -> sources.burning     (contract name)
    sources.other          -> folded out; the 5 contract shares are
                              renormalised to sum to ~1.0
    confidence_score       -> confidence
    timestamp: str (ISO Z) -> timestamp: datetime (UTC, tz-aware)

  forecast
    horizon[].t: str       -> t: datetime
    horizon[].aqi: int     -> aqi: float

Nothing here is wired into the live gateway: the demo routes still serve
``demo_engine`` so the presented numbers stay fixed. To serve a route from
the real modules instead, call the module, pass its result through the
matching function here, and return that. See ``docs`` at the bottom.
"""

from __future__ import annotations

from datetime import datetime, timezone

from contracts.attribution import Attribution, SourceShares
from contracts.forecast import Forecast, ForecastPoint

# Role 2 models — imported lazily inside functions would also work, but the
# package is a hard dependency of anything that calls this adapter.
from attribution.models import SourceAttributionOutput
from forecasting.models import ForecastCell


def _parse_ts(value: str) -> datetime:
    """Parse a Role 2 ISO-8601 timestamp (``...Z``) into an aware UTC datetime."""
    # Role 2 emits '%Y-%m-%dT%H:%M:%SZ'. fromisoformat handles the offset form;
    # normalise the trailing 'Z' it doesn't accept on older Pythons.
    text = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def to_contract_attribution(src: SourceAttributionOutput) -> Attribution:
    """Convert one Role 2 ``SourceAttributionOutput`` to a contract ``Attribution``.

    The contract has five source classes and no ``other`` bucket, so the five
    kept shares are renormalised to sum to ~1.0. When every kept share is zero
    (only background present) the mass is placed on ``dust`` as the neutral
    natural-background class, keeping the contract's "sum ~1.0" invariant.
    """
    s = src.sources
    kept = {
        "traffic": s.traffic,
        "construction": s.construction,
        "industry": s.industry,
        "burning": s.biomass,      # contract name for biomass/waste burning
        "dust": s.dust,
    }
    total = sum(kept.values())
    if total > 0:
        shares = {k: v / total for k, v in kept.items()}
    else:
        shares = {k: (1.0 if k == "dust" else 0.0) for k in kept}

    return Attribution(
        cell_id=src.cell_id,
        timestamp=_parse_ts(src.timestamp),
        sources=SourceShares(**{k: round(v, 4) for k, v in shares.items()}),
        confidence=src.confidence_score,
    )


def to_contract_forecast(cell: ForecastCell) -> Forecast:
    """Convert one Role 2 ``ForecastCell`` to a contract ``Forecast``."""
    return Forecast(
        cell_id=cell.cell_id,
        horizon=[
            ForecastPoint(t=_parse_ts(p.t), aqi=float(p.aqi))
            for p in cell.horizon
        ],
    )


# ── Self-test / conformance proof ─────────────────────────────────────
# Run directly:  PYTHONPATH=. python api/role2_adapter.py
# Building the contract models validates the shapes; this fails loudly if the
# Role 2 output ever drifts away from what the contracts require.
if __name__ == "__main__":
    from attribution.engine import attribute_sources
    from attribution.models import GridAttributionRequest, GridCellInput
    from forecasting.predictor import generate_forecast

    cell = GridCellInput(
        cell_id="grid_28.61_77.20", lat=28.61, lon=77.20, pm25=142.0,
        no2=48.0, so2=13.0, aod=0.9, uv_aerosol_index=1.6,
        wind_speed=2.3, wind_direction=300.0, road_density=0.7,
        industrial_proximity=750.0, construction_density=0.4,
    )

    attr = attribute_sources(GridAttributionRequest(cells=[cell])).attributions[0]
    contract_attr = to_contract_attribution(attr)
    ssum = sum(contract_attr.sources.model_dump().values())
    print("attribution ->", contract_attr.model_dump())
    print("  source shares sum:", round(ssum, 4), "(contract wants ~1.0)")
    assert 0.98 <= ssum <= 1.02, "renormalised shares must sum to ~1.0"
    assert isinstance(contract_attr.timestamp, datetime)

    fc = generate_forecast([cell], horizon_hours=24).forecasts[0]
    contract_fc = to_contract_forecast(fc)
    print("forecast    -> cell", contract_fc.cell_id,
          "| points", len(contract_fc.horizon),
          "| first", contract_fc.horizon[0].model_dump())
    assert isinstance(contract_fc.horizon[0].t, datetime)
    assert isinstance(contract_fc.horizon[0].aqi, float)

    print("\nOK — Role 2 output conforms to contracts via this adapter.")
