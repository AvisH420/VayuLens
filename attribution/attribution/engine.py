import random
from typing import List
from .models import GridCellInput, SourceAttributionOutput, GridAttributionRequest, GridAttributionResponse

def attribute_sources(request: GridAttributionRequest) -> GridAttributionResponse:
    """
    Computes source attribution percentages for a grid of cells.
    Currently uses a heuristic/pseudo-model based on pollutant proxies and land use
    to generate realistic outputs.
    """
    results: List[SourceAttributionOutput] = []
    
    for cell in request.cells:
        # 1. Calculate raw heuristic scores for each category
        # Traffic score: driven by NO2 and road density
        traffic_score = max(0.1, cell.no2 * (1.0 + cell.road_density))
        
        # Industrial score: driven by SO2 and how close it is to industrial zones
        # Safe division for proximity
        proximity_factor = 1.0 / (1.0 + max(0.0, cell.industrial_proximity / 1000.0))
        industrial_score = max(0.1, cell.so2 * proximity_factor * 1.5)
        
        # Biomass burning: driven by UV aerosol index (values > 0 represent smoke/dust)
        # Stubble burning has a high UV aerosol index, especially during dry seasons
        biomass_score = max(0.05, cell.uv_aerosol_index * 1.2 if cell.uv_aerosol_index > 0 else 0.05)
        
        # Dust: driven by overall Aerosol Optical Depth (AOD) and wind speed (wind kicks up dust)
        dust_score = max(0.1, cell.aod * (1.0 + cell.wind_speed * 0.1))
        
        # Construction: driven by construction density and AOD
        construction_score = max(0.05, cell.construction_density * cell.aod * 1.3)
        
        # Other/Background: baseline background pollution
        other_score = 0.1
        
        # 2. Normalize the scores so they sum to 1.0 (100%)
        total_score = traffic_score + industrial_score + biomass_score + dust_score + construction_score + other_score
        
        traffic_share = traffic_score / total_score
        industrial_share = industrial_score / total_score
        biomass_share = biomass_score / total_score
        dust_share = dust_score / total_score
        construction_share = construction_score / total_score
        other_share = other_score / total_score
        
        # 3. Calculate a mock confidence score based on the inputs' magnitude
        # High raw inputs mean we have strong signals, hence higher confidence
        raw_signal_strength = cell.no2 + cell.so2 + cell.aod
        confidence_score = min(0.95, 0.5 + (raw_signal_strength / 200.0))
        
        results.append(SourceAttributionOutput(
            cell_id=cell.cell_id,
            traffic_share=round(traffic_share, 3),
            industrial_share=round(industrial_share, 3),
            biomass_share=round(biomass_share, 3),
            dust_share=round(dust_share, 3),
            construction_share=round(construction_share, 3),
            other_share=round(other_share, 3),
            confidence_score=round(confidence_score, 2)
        ))
        
    return GridAttributionResponse(attributions=results)
