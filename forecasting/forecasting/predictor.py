import datetime
import math
from typing import List
from attribution.models import GridCellInput
from .models import ForecastResponse, ForecastCell

def generate_forecast(
    cells: List[GridCellInput],
    horizon_hours: int = 24
) -> ForecastResponse:
    """
    Generates hyperlocal PM2.5 forecasts for a list of cells over a horizon of hours.
    
    How it works (Heuristic Time-Series):
    1. For each hour in the future, we calculate a diurnal (daily) variation curve.
       Typically, pollution peaks in the morning (8-10 AM) and evening (6-9 PM) due to traffic,
       and drops in the afternoon (1-4 PM) as atmospheric mixing increases.
    2. We apply weather forecasts (modeled here as fluctuations in wind speed/direction).
    3. We return the forecast arrays with ISO timestamps.
    """
    forecast_cells: List[ForecastCell] = []
    
    # We will generate forecasts starting from the current local time
    start_time = datetime.datetime.now()
    
    for cell in cells:
        predictions_pm25: List[float] = []
        timestamps: List[str] = []
        
        for hour in range(1, horizon_hours + 1):
            future_time = start_time + datetime.timedelta(hours=hour)
            timestamps.append(future_time.isoformat())
            
            # 1. Diurnal cycle model:
            # We want peaks at 9:00 AM (hour 9) and 8:00 PM (hour 20)
            t = future_time.hour
            # Diurnal factor ranges between 0.7 and 1.3
            diurnal_factor = 1.0 + 0.3 * math.sin(2 * math.pi * (t - 6) / 24) + 0.1 * math.sin(4 * math.pi * (t - 15) / 24)
            
            # 2. Weather trend modeling (simplified):
            # Assume wind speed changes slightly in the future
            # If wind speed increases, pollution dilutes. If it drops, pollution accumulates.
            simulated_wind_speed = max(0.5, cell.wind_speed + 1.5 * math.sin(hour / 6.0))
            wind_factor = (cell.wind_speed + 1.0) / (simulated_wind_speed + 1.0)
            
            # 3. Combine base concentration with factors and add tiny random variance
            random_noise = 1.0 + (math.sin(hour * 1.5) * 0.05) # Predictable noise for consistency
            predicted_pm = cell.pm25 * diurnal_factor * wind_factor * random_noise
            
            # Ensure PM2.5 values stay positive and within realistic limits (e.g. 5.0 to 999.0)
            predicted_pm = max(5.0, min(999.0, predicted_pm))
            predictions_pm25.append(round(predicted_pm, 2))
            
        forecast_cells.append(ForecastCell(
            cell_id=cell.cell_id,
            lat=cell.lat,
            lon=cell.lon,
            predictions_pm25=predictions_pm25,
            timestamps=timestamps
        ))
        
    return ForecastResponse(
        forecasts=forecast_cells,
        forecast_horizon_hours=horizon_hours
    )
