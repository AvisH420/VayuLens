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
    
    How it works (Source-to-Receptor Contribution Matrix Normalization):
    1. Runs attribution to identify the share of pollution from each source in each cell.
    2. Computes the base emission rate for all cells and categories.
    3. Runs dispersion physics to build a raw contribution matrix from each source cell j to receptor cell i.
    4. Normalizes the incoming contributions for each receptor cell i so they sum exactly to cell i's
       active concentration (original PM2.5 minus background 'other' share).
    5. Calculates the emission reduction fraction for each cell based on the intervention scenario.
    6. Recomputes each cell's PM2.5 concentration by applying these reduction fractions to the normalized
       contributions, preventing double-counting and ensuring realistic policy deltas.
    """
    # 1. Run source attribution to find the source shares for all cells
    attribution_req = GridAttributionRequest(cells=cells)
    attribution_resp = attribute_sources(attribution_req)
    
    # Map cell_id to its attribution for fast lookup
    attributions: Dict[str, SourceAttributionOutput] = {
        attr.cell_id: attr for attr in attribution_resp.attributions
    }
    
    # Map cell_id to cell input object
    cell_map: Dict[str, GridCellInput] = {cell.cell_id: cell for cell in cells}
    
    # 2. Compute original and simulated emissions for all cells
    original_active_emissions: Dict[str, float] = {}
    simulated_active_emissions: Dict[str, float] = {}
    
    affected_cells_set = set(scenario.affected_cell_ids)
    
    for cell in cells:
        attr = attributions[cell.cell_id]
        
        # Flow rate: cross-section area (1000m wide * 10m height) * wind speed
        stack_height = 10.0
        ambient_wind = max(0.5, cell.wind_speed)
        em_factor = 1000.0 * stack_height * ambient_wind
        
        # Emissions per category (PM2.5 * category_share * flow_rate)
        # Note: 'other' is background and is treated as non-dispersive (static background)
        traffic_em = cell.pm25 * attr.sources.traffic * em_factor
        industrial_em = cell.pm25 * attr.sources.industry * em_factor
        biomass_em = cell.pm25 * attr.sources.biomass * em_factor
        dust_em = cell.pm25 * attr.sources.dust * em_factor
        construction_em = cell.pm25 * attr.sources.construction * em_factor
        
        orig_active = traffic_em + industrial_em + biomass_em + dust_em + construction_em
        original_active_emissions[cell.cell_id] = orig_active
        
        if cell.cell_id in affected_cells_set:
            # Apply reductions to target cells
            traffic_sim = traffic_em * (1.0 - scenario.traffic_reduction)
            industrial_sim = industrial_em * (1.0 - scenario.industrial_reduction)
            biomass_sim = 0.0 if scenario.biomass_burning_banned else biomass_em
            construction_sim = 0.0 if scenario.construction_halted else construction_em
            dust_sim = dust_em  # Dust is unreduced
            
            sim_active = traffic_sim + industrial_sim + biomass_sim + construction_sim + dust_sim
        else:
            sim_active = orig_active
            
        simulated_active_emissions[cell.cell_id] = sim_active

    # 3. Build the Source-to-Receptor Contribution Matrix
    # contrib_matrix[s_id][r_id] stores the PM2.5 contribution from source cell s_id to receptor r_id
    contrib_matrix: Dict[str, Dict[str, float]] = {c.cell_id: {} for c in cells}
    
    for s_cell in cells:
        orig_active_em = original_active_emissions[s_cell.cell_id]
        
        for r_cell in cells:
            # Calculate raw ground-level concentration at receptor from source emissions using dispersion physics
            raw_contribution = calculate_ground_concentration(
                source_lat=s_cell.lat,
                source_lon=s_cell.lon,
                receptor_lat=r_cell.lat,
                receptor_lon=r_cell.lon,
                emission_rate=orig_active_em,
                wind_speed=s_cell.wind_speed,
                wind_direction_deg=s_cell.wind_direction
            )
            
            # Divide by em_factor of receptor cell to rescale dispersion to concentration units (ug/m3)
            # Dilution factor is normalized by receptor cell parameters
            stack_height = 10.0
            r_ambient_wind = max(0.5, r_cell.wind_speed)
            r_em_factor = 1000.0 * stack_height * r_ambient_wind
            
            contrib_matrix[s_cell.cell_id][r_cell.cell_id] = raw_contribution / r_em_factor

    # 4. Normalize the Contribution Matrix
    # Ensures that the sum of dispersed active contributions to any cell i equals
    # exactly its active concentration: cell_i.pm25 * (1.0 - other_share_i)
    normalized_matrix: Dict[str, Dict[str, float]] = {c.cell_id: {} for c in cells}
    
    for r_cell in cells:
        attr = attributions[r_cell.cell_id]
        active_target_concentration = r_cell.pm25 * (1.0 - attr.sources.other)
        
        sum_incoming = sum(contrib_matrix[s_cell.cell_id][r_cell.cell_id] for s_cell in cells)
        
        if sum_incoming > 0.0:
            scale_factor = active_target_concentration / sum_incoming
            for s_cell in cells:
                normalized_matrix[s_cell.cell_id][r_cell.cell_id] = (
                    contrib_matrix[s_cell.cell_id][r_cell.cell_id] * scale_factor
                )
        else:
            # Fallback: if dispersion shows 0 contribution, assign 100% of active concentration to self-contribution
            for s_cell in cells:
                if s_cell.cell_id == r_cell.cell_id:
                    normalized_matrix[s_cell.cell_id][r_cell.cell_id] = active_target_concentration
                else:
                    normalized_matrix[s_cell.cell_id][r_cell.cell_id] = 0.0

    # 5. Run the Simulation Scenario using Normalized Matrix and Reduction Fractions
    results: List[SimulationCellResult] = []
    total_reduction_percent = 0.0
    
    for r_cell in cells:
        orig_pm = r_cell.pm25
        attr = attributions[r_cell.cell_id]
        
        # Start with static background ("other" share)
        background_pm = orig_pm * attr.sources.other
        
        # Calculate simulated active concentration by scaling normalized contributions
        # according to the active emission reduction fraction of each source cell
        simulated_active_pm = 0.0
        for s_cell in cells:
            orig_em = original_active_emissions[s_cell.cell_id]
            sim_em = simulated_active_emissions[s_cell.cell_id]
            
            # Find fraction of active emissions remaining in the source cell (1.0 = no change, 0.0 = complete cut)
            if orig_em > 0.0:
                fraction_remaining = sim_em / orig_em
            else:
                fraction_remaining = 1.0
                
            # Apply remaining fraction to normalized contribution
            simulated_active_pm += normalized_matrix[s_cell.cell_id][r_cell.cell_id] * fraction_remaining
            
        sim_pm = max(5.0, background_pm + simulated_active_pm)
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
