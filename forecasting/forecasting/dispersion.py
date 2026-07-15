import math
from typing import Tuple

def calculate_dispersion_coefficients(downwind_x: float, stability_class: str = 'D') -> Tuple[float, float]:
    """
    Calculates the dispersion coefficients sigma_y and sigma_z in meters,
    which determine how wide and tall the pollution plume spreads over distance downwind_x.
    Uses standard Pasquill-Gifford parameterization for Neutral stability class 'D'.
    """
    # Prevent division by zero or negative values for cells extremely close to the source
    x = max(1.0, downwind_x)
    
    # Class D (Neutral atmosphere - typical default) parameters
    # sigma_y = a * x^b
    # sigma_z = c * x^d
    # (Values approximated for range of 100m to 10km)
    sigma_y = 0.08 * x * (1.0 + 0.0001 * x) ** (-0.5)
    sigma_z = 0.06 * x * (1.0 + 0.0015 * x) ** (-0.5)
    
    return sigma_y, sigma_z

def calculate_ground_concentration(
    source_lat: float,
    source_lon: float,
    receptor_lat: float,
    receptor_lon: float,
    emission_rate: float,
    wind_speed: float,
    wind_direction_deg: float,
    stack_height: float = 10.0
) -> float:
    """
    Calculates the PM2.5 ground concentration (ug/m3) at a receptor location 
    caused by a source location using the Gaussian Plume Equation.
    
    Physics parameters:
    - emission_rate (Q): Emissions in ug/s (micrograms per second)
    - wind_speed (u): Wind speed in m/s (must be > 0)
    - wind_direction_deg: Wind direction (0 = North, 90 = East, etc.)
    - stack_height (H): Release height in meters (default 10m)
    """
    # 1. Convert latitude/longitude distances to meters (approximate)
    # 1 degree lat is approx 111,000 meters. 1 degree lon varies, let's use approx 96,000m for Delhi latitude
    dy = (receptor_lat - source_lat) * 111000.0
    dx = (receptor_lon - source_lon) * 96000.0
    
    # 2. Check if source and receptor are the same cell
    distance = math.sqrt(dx**2 + dy**2)
    if distance < 10.0:  # Same cell (within 10 meters)
        # Simplify: assume immediate dilution in a 1km wide cross-section
        # Volume flow rate = width (1000m) * height (stack_height) * wind_speed
        cross_section_area = 1000.0 * stack_height
        ambient_wind = max(0.5, wind_speed)
        return emission_rate / (cross_section_area * ambient_wind)
        
    # 3. Calculate wind vector. 
    # Meteorological angle is "direction wind comes FROM". 
    # Wind direction vector (where it goes TO) is opposite.
    wind_to_rad = math.radians((wind_direction_deg + 180) % 360)
    wind_x = math.sin(wind_to_rad)
    wind_y = math.cos(wind_to_rad)
    
    # 4. Project coordinates to get Downwind (x) and Crosswind (y) distances in meters
    # Downwind distance is the dot product of distance vector and wind direction vector
    downwind_x = dx * wind_x + dy * wind_y
    
    # If the receptor is UPWIND of the source, they receive 0 concentration contribution
    if downwind_x <= 0:
        return 0.0
        
    # Crosswind distance is the perpendicular (cross product) distance
    crosswind_y = abs(-dx * wind_y + dy * wind_x)
    
    # 5. Get dispersion coefficients
    sigma_y, sigma_z = calculate_dispersion_coefficients(downwind_x, 'D')
    
    # 6. Apply the Gaussian Plume Ground Concentration Formula:
    # C = [Q / (pi * u * sigma_y * sigma_z)] * exp[-y^2 / (2 * sigma_y^2)] * exp[-H^2 / (2 * sigma_z^2)]
    u = max(0.5, wind_speed)  # Avoid division by zero
    
    pi_term = math.pi * u * sigma_y * sigma_z
    horizontal_spread = math.exp(- (crosswind_y ** 2) / (2 * (sigma_y ** 2)))
    vertical_spread = math.exp(- (stack_height ** 2) / (2 * (sigma_z ** 2)))
    
    concentration = (emission_rate / pi_term) * horizontal_spread * vertical_spread
    
    return concentration
