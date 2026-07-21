from typing import List
from datetime import datetime, timezone
from .models import (
    GridCellInput, 
    SourceAttributionDict, 
    SourceAttributionOutput, 
    GridAttributionRequest, 
    GridAttributionResponse
)

# Representative baseline scaling factors (typical values for Indian cities like Delhi)
# Normalizes input variables of completely different units to a comparable [0.0 - 2.0] scale
TYPICAL_NO2 = 40.0             # NO2 values usually range 10 - 100
TYPICAL_SO2 = 15.0             # SO2 values usually range 5 - 50
TYPICAL_UV_INDEX = 1.0         # UV Aerosol Index usually ranges 0 - 3 (representing carbon/dust smoke)
TYPICAL_AOD = 0.5              # Aerosol Optical Depth usually ranges 0.1 - 1.2
TYPICAL_INDUSTRIAL_PROXIMITY = 1000.0  # Industrial zone proximity benchmark in meters

def attribute_sources(request: GridAttributionRequest) -> GridAttributionResponse:
    """
    Computes source attribution percentages for a grid of cells.
    Uses unit-normalized proxies and static land-use weights to determine
    the contribution of each category (traffic, industrial, biomass, dust, construction).
    """
    results: List[SourceAttributionOutput] = []
    # All calculations are timestamped with the current execution time in UTC
    utc_now_str = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    for cell in request.cells:
        # 1. Scale inputs by typical values to align them to a common scale
        norm_no2 = cell.no2 / TYPICAL_NO2
        norm_so2 = cell.so2 / TYPICAL_SO2
        norm_uv = max(0.0, cell.uv_aerosol_index) / TYPICAL_UV_INDEX
        norm_aod = cell.aod / TYPICAL_AOD
        
        # 2. Compute category scores
        # Traffic score: driven by NO2 and localized road density
        traffic_score = norm_no2 * (0.5 + cell.road_density)
        
        # Industrial score: driven by SO2 and proximity to industrial zones (higher when closer)
        proximity_factor = 1.0 / (1.0 + max(0.0, cell.industrial_proximity / TYPICAL_INDUSTRIAL_PROXIMITY))
        industrial_score = norm_so2 * proximity_factor * 1.2
        
        # Biomass burning: driven by UV aerosol index (stubble burning emissions are rich in UV-absorbing aerosols)
        biomass_score = norm_uv * 0.8
        
        # Dust: driven by overall AOD and wind speed (wind picks up dust)
        dust_score = norm_aod * (0.6 + cell.wind_speed * 0.08)
        
        # Construction: driven by localized construction density and overall AOD
        construction_score = norm_aod * cell.construction_density * 1.0
        
        # Other/Background: stable regional baseline background pollution
        other_score = 0.15
        
        # 3. Normalize the scores to sum to 1.0 (100%)
        total_score = traffic_score + industrial_score + biomass_score + dust_score + construction_score + other_score
        
        traffic_share = traffic_score / total_score
        industrial_share = industrial_score / total_score
        biomass_share = biomass_score / total_score
        dust_share = dust_score / total_score
        construction_share = construction_score / total_score
        other_share = other_score / total_score
        
        # 4. Calculate attribution confidence based on proxy signal strengths
        raw_signal_strength = cell.no2 + cell.so2 + cell.aod
        confidence_score = min(0.95, 0.4 + (raw_signal_strength / 250.0))
        
        sources_dict = SourceAttributionDict(
            traffic=round(traffic_share, 3),
            construction=round(construction_share, 3),
            industry=round(industrial_share, 3),
            biomass=round(biomass_share, 3),
            dust=round(dust_share, 3),
            other=round(other_share, 3)
        )
        
        results.append(SourceAttributionOutput(
            cell_id=cell.cell_id,
            sources=sources_dict,
            confidence_score=round(confidence_score, 2),
            timestamp=utc_now_str
        ))
        
    return GridAttributionResponse(attributions=results)
