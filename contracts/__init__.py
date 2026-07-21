"""VayuLens shared data contracts.

Every role builds against these schemas. They are the single source of truth
for the data shapes that cross module boundaries (data -> attribution/forecast
-> rag/decision -> api/frontend).

CHANGING A SCHEMA IS A BREAKING CHANGE. See contracts/README.md — tell the
group before you edit anything in this package.
"""

from contracts.grid_cell import GridCell
from contracts.measurement import Measurement
from contracts.attribution import Attribution, SourceShares
from contracts.forecast import Forecast, ForecastPoint
from contracts.recommendation import Recommendation

__all__ = [
    "GridCell",
    "Measurement",
    "Attribution",
    "SourceShares",
    "Forecast",
    "ForecastPoint",
    "Recommendation",
]
