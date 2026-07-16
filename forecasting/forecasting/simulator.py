from typing import List, Dict
from attribution.models import GridCellInput, SourceAttributionOutput
from attribution.engine import attribute_sources, GridAttributionRequest
from .models import SimulationScenario, SimulationResponse, SimulationCellResult
from .dispersion import calculate_ground_concentration

def simulate_intervention(
    cells: List[GridCellInput],
    scenario: SimulationScenario
) -> SimulationResponse:
    """
    Simulates the impact of environmental policy changes (interventions) on PM2.5 levels across the grid.
    
    How it works:
    1. Runs attribution to identify the share of pollution from each source in each cell.
    2. Estimates the original 'emission rate' (Q) for each cell's sources.
    3. Applies the intervention reductions (e.g. traffic reduction, construction ban) to those emissions.
    4. Re-disperses the new emissions using the Gaussian Plume model.
    5. Returns the pre-and-post PM2.5 values for each cell.
    """
    # 1. Run source attribution to find the source shares for all cells
    attribution_req = GridAttributionRequest(cells=cells)
    attribution_resp = attribute_sources(attribution_req)
    
    # Map cell_id to its attribution for fast lookup
    attributions: Dict[str, SourceAttributionOutput] = {
        attr.cell_id: attr for attr in attribution_resp.attributions
    }
    
    # 2. Estimate emission rates for each cell.
    # We treat each cell as an emitter. Its emission rate is proportional to its PM2.5
    # split by its source shares.
    original_emissions: Dict[str, Dict[str, float]] = {}
    for cell in cells:
        attr = attributions[cell.cell_id]
        
        # We define a scaling factor to turn concentration (ug/m3) into an emission rate (ug/s)
        # 1 ug/m3 in a 1km^3 volume requires roughly 10,000 ug/s of emissions assuming typical winds.
        # Dynamic em_factor: cross-section area (1000m * 10m height) * wind speed
        stack_height = 10.0
        ambient_wind = max(0.5, cell.wind_speed)
        em_factor = 1000.0 * stack_height * ambient_wind
        base_emissions = cell.pm25 * em_factor
        
        original_emissions[cell.cell_id] = {
            "traffic": base_emissions * attr.traffic_share,
            "industrial": base_emissions * attr.industrial_share,
            "biomass": base_emissions * attr.biomass_share,
            "dust": base_emissions * attr.dust_share,
            "construction": base_emissions * attr.construction_share,
            "other": base_emissions * attr.other_share
        }
        
    # 3. Apply the scenario reductions to create simulated emissions
    simulated_emissions: Dict[str, Dict[str, float]] = {}
    affected_cells_set = set(scenario.affected_cell_ids)
    
    for cell_id, em in original_emissions.items():
        if cell_id in affected_cells_set:
            # Apply reductions to target cells
            sim_em = {
                "traffic": em["traffic"] * (1.0 - scenario.traffic_reduction),
                "industrial": em["industrial"] * (1.0 - scenario.industrial_reduction),
                "biomass": 0.0 if scenario.biomass_burning_banned else em["biomass"],
                "construction": 0.0 if scenario.construction_halted else em["construction"],
                "dust": em["dust"], # Dust remains unchanged unless swept
                "other": em["other"]
            }
        else:
            # Unchanged cells keep their original emissions
            sim_em = em.copy()
            
        simulated_emissions[cell_id] = sim_em
        
    # 4. Re-calculate grid concentrations using dispersion modeling of reductions.
    # For each receptor cell, its new concentration is:
    # original_concentration - sum_of_reductions_dispersed_from_all_sources
    results: List[SimulationCellResult] = []
    total_reduction_percent = 0.0
    
    for r_cell in cells:
        orig_pm = r_cell.pm25
        total_reduction = 0.0
        
        # Add up reductions dispersed from all source cells
        for s_cell in cells:
            s_orig = original_emissions[s_cell.cell_id]
            s_sim = simulated_emissions[s_cell.cell_id]
            
            # Calculate emission reduction rate in ug/s for this source cell
            reduction_rate = (
                (s_orig["traffic"] - s_sim["traffic"]) +
                (s_orig["industrial"] - s_sim["industrial"]) +
                (s_orig["biomass"] - s_sim["biomass"]) +
                (s_orig["construction"] - s_sim["construction"])
            )
            
            if reduction_rate > 0.0:
                # Calculate how much this emission reduction reduces concentration at the receptor cell
                reduction_concentration = calculate_ground_concentration(
                    source_lat=s_cell.lat,
                    source_lon=s_cell.lon,
                    receptor_lat=r_cell.lat,
                    receptor_lon=r_cell.lon,
                    emission_rate=reduction_rate,
                    wind_speed=s_cell.wind_speed,
                    wind_direction_deg=s_cell.wind_direction
                )
                total_reduction += reduction_concentration
                
        # Simulated PM2.5 is the original minus the total reduction, bounded at a baseline (e.g. 5 ug/m3)
        sim_pm = max(5.0, orig_pm - total_reduction)
        delta_pm = sim_pm - orig_pm
        delta_pct = (delta_pm / orig_pm) * 100.0 if orig_pm > 0 else 0.0
        
        results.append(SimulationCellResult(
            cell_id=r_cell.cell_id,
            original_pm25=round(orig_pm, 2),
            simulated_pm25=round(sim_pm, 2),
            delta_pm25=round(delta_pm, 2),
            delta_percent=round(delta_pct, 2)
        ))
        
        total_reduction_percent += delta_pct
        
    avg_reduction_percent = total_reduction_percent / len(cells) if cells else 0.0
    
    return SimulationResponse(
        scenario_name=scenario.name,
        results=results,
        average_reduction_percent=round(avg_reduction_percent, 2)
    )
