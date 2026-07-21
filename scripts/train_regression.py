"""Train city-specific AOD -> PM2.5 regression models using 1 year of historical data."""

import json
import math
import numpy as np

# Load data
with open("data_store/delhi_historical.json") as f:
    delhi = json.load(f)
with open("data_store/panaji_historical.json") as f:
    panaji = json.load(f)


def build_dataset(data):
    """Merge AQ + weather into paired arrays."""
    aq = data["aq"]
    wx = data["wx"]
    
    times = aq["time"]
    aod = aq["aerosol_optical_depth"]
    pm25 = aq["pm2_5"]
    humidity = wx.get("relative_humidity_2m", [None] * len(times))
    wind = wx.get("wind_speed_10m", [None] * len(times))
    temp = wx.get("temperature_2m", [None] * len(times))
    
    # Build feature matrix: only rows where ALL values are present
    X = []  # [AOD, humidity, wind_speed, temperature, hour_sin, hour_cos, month_sin, month_cos]
    y = []  # PM2.5
    
    for i in range(len(times)):
        if any(v is None for v in [aod[i], pm25[i], humidity[i], wind[i], temp[i]]):
            continue
        
        # Parse hour and month for cyclical features
        time_str = times[i]
        hour = int(time_str[11:13])
        month = int(time_str[5:7])
        
        hour_sin = math.sin(2 * math.pi * hour / 24)
        hour_cos = math.cos(2 * math.pi * hour / 24)
        month_sin = math.sin(2 * math.pi * month / 12)
        month_cos = math.cos(2 * math.pi * month / 12)
        
        X.append([aod[i], humidity[i], wind[i], temp[i], hour_sin, hour_cos, month_sin, month_cos])
        y.append(pm25[i])
    
    return np.array(X), np.array(y)


def train_regression(X, y, city_name):
    """Train multivariate linear regression and report results."""
    from numpy.linalg import lstsq
    
    n = len(y)
    print(f"\n{'='*60}")
    print(f"  {city_name}: {n} valid data pairs")
    print(f"{'='*60}")
    
    # Split 80/20
    split = int(0.8 * n)
    indices = np.arange(n)
    np.random.seed(42)
    np.random.shuffle(indices)
    
    train_idx = indices[:split]
    test_idx = indices[split:]
    
    X_train, y_train = X[train_idx], y[train_idx]
    X_test, y_test = X[test_idx], y[test_idx]
    
    # Add intercept column
    X_train_b = np.column_stack([np.ones(len(X_train)), X_train])
    X_test_b = np.column_stack([np.ones(len(X_test)), X_test])
    
    # Ordinary Least Squares
    coeffs, residuals, rank, sv = lstsq(X_train_b, y_train, rcond=None)
    
    intercept = coeffs[0]
    feature_names = ["AOD", "Humidity", "Wind", "Temp", "HourSin", "HourCos", "MonthSin", "MonthCos"]
    
    print(f"\n  Intercept: {intercept:.4f}")
    for name, coeff in zip(feature_names, coeffs[1:]):
        print(f"  {name:>10s}: {coeff:+.4f}")
    
    # Evaluate on test set
    y_pred = X_test_b @ coeffs
    
    errors = y_test - y_pred
    mae = np.mean(np.abs(errors))
    rmse = np.sqrt(np.mean(errors**2))
    
    # R-squared
    ss_res = np.sum(errors**2)
    ss_tot = np.sum((y_test - np.mean(y_test))**2)
    r2 = 1 - ss_res / ss_tot
    
    # Mean Absolute Percentage Error
    mask = y_test > 5  # avoid division by near-zero
    mape = np.mean(np.abs(errors[mask] / y_test[mask])) * 100
    
    print(f"\n  Test Set Results ({len(y_test)} samples):")
    print(f"    R-squared:  {r2:.4f}")
    print(f"    MAE:        {mae:.2f} ug/m3")
    print(f"    RMSE:       {rmse:.2f} ug/m3")
    print(f"    MAPE:       {mape:.1f}%")
    
    # Compare with generic formula
    generic_pred = 70 * X_test[:, 0] + 5  # PM2.5 = 70*AOD + 5
    generic_errors = y_test - generic_pred
    generic_mae = np.mean(np.abs(generic_errors))
    generic_rmse = np.sqrt(np.mean(generic_errors**2))
    generic_r2 = 1 - np.sum(generic_errors**2) / ss_tot
    generic_mape = np.mean(np.abs(generic_errors[mask] / y_test[mask])) * 100
    
    print(f"\n  Generic Formula (PM2.5 = 70*AOD + 5) Comparison:")
    print(f"    R-squared:  {generic_r2:.4f}")
    print(f"    MAE:        {generic_mae:.2f} ug/m3")
    print(f"    RMSE:       {generic_rmse:.2f} ug/m3")
    print(f"    MAPE:       {generic_mape:.1f}%")
    
    improvement_mae = (1 - mae / generic_mae) * 100
    improvement_mape = generic_mape - mape
    print(f"\n  >>> Improvement: MAE reduced by {improvement_mae:.1f}%, MAPE reduced by {improvement_mape:.1f} percentage points")
    
    return {
        "intercept": round(float(intercept), 4),
        "aod_slope": round(float(coeffs[1]), 4),
        "humidity_coeff": round(float(coeffs[2]), 4),
        "wind_coeff": round(float(coeffs[3]), 4),
        "temp_coeff": round(float(coeffs[4]), 4),
        "hour_sin_coeff": round(float(coeffs[5]), 4),
        "hour_cos_coeff": round(float(coeffs[6]), 4),
        "month_sin_coeff": round(float(coeffs[7]), 4),
        "month_cos_coeff": round(float(coeffs[8]), 4),
        "r2": round(float(r2), 4),
        "mae": round(float(mae), 2),
        "rmse": round(float(rmse), 2),
        "mape": round(float(mape), 1),
    }


# Build datasets
print("Building datasets...")
X_delhi, y_delhi = build_dataset(delhi)
X_panaji, y_panaji = build_dataset(panaji)

# Train
delhi_model = train_regression(X_delhi, y_delhi, "DELHI")
panaji_model = train_regression(X_panaji, y_panaji, "PANAJI")

# Save models
models = {"delhi": delhi_model, "panaji": panaji_model}
with open("data_store/regression_models.json", "w") as f:
    json.dump(models, f, indent=2)

print(f"\n\nModels saved to data_store/regression_models.json")
print("\nDELHI coefficients:", json.dumps(delhi_model, indent=2))
print("\nPANAJI coefficients:", json.dumps(panaji_model, indent=2))
