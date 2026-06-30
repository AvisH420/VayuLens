"""Role 2 — source-attribution engine stubs.

Takes fused `Measurement` records (plus grid context) and apportions pollution
to source classes (traffic, construction, industry, burning, dust).

All functions are stubs that raise NotImplementedError.
"""

from __future__ import annotations

from contracts.attribution import Attribution
from contracts.grid_cell import GridCell
from contracts.measurement import Measurement


def attribute_cell(measurement: Measurement, cell: GridCell) -> Attribution:
    """Apportion a single cell's measured pollution to source classes.

    Args:
        measurement: The fused observation for the cell/timestamp.
        cell: Static context (land use, road density, industrial flag).

    Returns:
        An `Attribution` with per-source shares and a confidence score.
    """
    raise NotImplementedError


def attribute_batch(
    measurements: list[Measurement],
    grid: dict[str, GridCell],
) -> list[Attribution]:
    """Run attribution over many measurements.

    Args:
        measurements: Fused observations to attribute.
        grid: Grid cells keyed by `cell_id` for context lookup.

    Returns:
        One `Attribution` per input measurement.
    """
    raise NotImplementedError
