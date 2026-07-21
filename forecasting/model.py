"""Role 2 — forecasting stubs.

Runs a dispersion model to produce 24-72h AQI forecasts per cell, and supports
counterfactual `simulate(scenario)` runs for the what-if panel.

All functions are stubs that raise NotImplementedError.
"""

from __future__ import annotations

from typing import Any

from contracts.forecast import Forecast
from contracts.grid_cell import GridCell
from contracts.measurement import Measurement


def forecast_cell(
    cell: GridCell,
    history: list[Measurement],
    horizon_hours: int = 72,
) -> Forecast:
    """Produce a 24-72h AQI forecast for a single cell.

    Args:
        cell: The grid cell to forecast.
        history: Recent measurements for the cell (and neighbours, as needed).
        horizon_hours: Forecast horizon, typically 24-72.

    Returns:
        A `Forecast` with an ordered `horizon` of (t, aqi) points.
    """
    raise NotImplementedError


def forecast_grid(
    grid: list[GridCell],
    history: dict[str, list[Measurement]],
    horizon_hours: int = 72,
) -> list[Forecast]:
    """Run the dispersion model across the whole grid.

    Args:
        grid: All grid cells.
        history: Recent measurements keyed by `cell_id`.
        horizon_hours: Forecast horizon, typically 24-72.

    Returns:
        One `Forecast` per cell.
    """
    raise NotImplementedError


def simulate(scenario: dict[str, Any], grid: list[GridCell]) -> list[Forecast]:
    """Run a counterfactual ("what-if") forecast under an intervention scenario.

    Args:
        scenario: Intervention description, e.g.
            {"halt_construction": ["cell_123"], "traffic_reduction": 0.3}.
        grid: All grid cells the scenario applies to.

    Returns:
        Forecasts under the scenario, comparable to the baseline `forecast_grid`.
    """
    raise NotImplementedError
