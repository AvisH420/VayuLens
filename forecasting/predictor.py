import math
from datetime import datetime, timedelta, timezone
from typing import List
from attribution.models import GridCellInput
from .models import ForecastResponse, ForecastCell, ForecastPoint

def pm25_to_aqi(pm25: float) -> int:
    """
    Converts PM2.5 concentration (ug/m3) to Indian Air Quality Index (AQI) 
    using the official Central Pollution Control Board (CPCB) piecewise linear breakpoints.
    """
    if pm25 <= 0:
        return 0
        
    # CPCB PM2.5 24hr breakpoints:
    # Conc range | AQI range
    # 0 - 30     | 0 - 50
    # 31 - 60    | 51 - 100
    # 61 - 90    | 101 - 200
    # 91 - 120   | 201 - 300
    # 121 - 250  | 301 - 400
    # 251 - 350  | 401 - 500
    # 350+       | Pinned at 500
    if pm25 <= 30.0:
        return round((50.0 / 30.0) * pm25)
    elif pm25 <= 60.0:
        return round(51.0 + (100.0 - 51.0) * (pm25 - 30.0) / (60.0 - 30.0))
    elif pm25 <= 90.0:
        return round(101.0 + (200.0 - 101.0) * (pm25 - 60.0) / (90.0 - 60.0))
    elif pm25 <= 120.0:
        return round(201.0 + (300.0 - 201.0) * (pm25 - 90.0) / (120.0 - 90.0))
    elif pm25 <= 250.0:
        return round(301.0 + (400.0 - 301.0) * (pm25 - 120.0) / (250.0 - 120.0))
    elif pm25 <= 350.0:
        return round(401.0 + (500.0 - 401.0) * (pm25 - 250.0) / (350.0 - 250.0))
    else:
        return 500

def generate_forecast(
    cells: List[GridCellInput],
    horizon_hours: int = 24
) -> ForecastResponse:
    """
    Generates hyperlocal forecasts for a list of cells over a horizon of hours.
    Returns timezone-aware UTC timestamps and predictions converted to CPCB AQI.
    """
    forecast_cells: List[ForecastCell] = []
    
    # Generate timezone-aware UTC starting time
    start_time = datetime.now(timezone.utc)
    
    for cell in cells:
        horizon_points: List[ForecastPoint] = []
        
        for hour in range(1, horizon_hours + 1):
            future_time = start_time + timedelta(hours=hour)
            # Standard UTC Z format
            timestamp_str = future_time.strftime('%Y-%m-%dT%H:%M:%SZ')
            
            # 1. Diurnal cycle model:
            # Peaks at 9:00 AM (hour 9) and 8:00 PM (hour 20) local-like cycle
            t = future_time.hour
            diurnal_factor = 1.0 + 0.3 * math.sin(2 * math.pi * (t - 6) / 24) + 0.1 * math.sin(4 * math.pi * (t - 15) / 24)
            
            # 2. Weather trend modeling (simplified):
            # Wind speed fluctuates, affecting dilution factor
            simulated_wind_speed = max(0.5, cell.wind_speed + 1.5 * math.sin(hour / 6.0))
            wind_factor = (cell.wind_speed + 1.0) / (simulated_wind_speed + 1.0)
            
            # 3. Combine base concentration, weather factors, and noise
            random_noise = 1.0 + (math.sin(hour * 1.5) * 0.05)
            predicted_pm = cell.pm25 * diurnal_factor * wind_factor * random_noise
            predicted_pm = max(5.0, min(999.0, predicted_pm))
            
            # 4. Convert PM2.5 prediction to CPCB AQI
            predicted_aqi = pm25_to_aqi(predicted_pm)
            
            horizon_points.append(ForecastPoint(
                t=timestamp_str,
                aqi=predicted_aqi
            ))
            
        forecast_cells.append(ForecastCell(
            cell_id=cell.cell_id,
            lat=cell.lat,
            lon=cell.lon,
            horizon=horizon_points
        ))
        
    return ForecastResponse(
        forecasts=forecast_cells,
        forecast_horizon_hours=horizon_hours,
    )
