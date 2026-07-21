"""Schema: grid_cell — one cell of the ~1km analysis grid."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GridCell(BaseModel):
    """A single ~1km grid cell, the spatial unit of the whole platform."""

    cell_id: str = Field(..., description="Stable unique id for the cell, e.g. 'grid_28.61_77.20'.")
    lat: float = Field(..., description="Latitude of the cell centroid (WGS84).")
    lon: float = Field(..., description="Longitude of the cell centroid (WGS84).")
    ward: str = Field(..., description="Administrative ward / zone the cell falls in.")
    land_use_class: str = Field(..., description="Dominant land use: residential | commercial | industrial | green | mixed.")
    road_density: float = Field(..., description="Road length per unit area (km/km^2).")
    industrial_flag: bool = Field(..., description="True if the cell contains a registered industrial source.")
    industrial_proximity: float = Field(..., description="Approximate distance (in meters) to nearest industrial source.")
    construction_density: float = Field(..., description="Density of construction sites in the cell.")
