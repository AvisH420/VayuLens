import requests
import json
import os

os.makedirs("data_store", exist_ok=True)

# Pull 1 year of historical PM2.5 + weather for Delhi (city center)
print("=== Pulling Delhi historical data ===")
aq = requests.get("https://air-quality-api.open-meteo.com/v1/air-quality", params={
    "latitude": 28.62,
    "longitude": 77.22,
    "hourly": "pm2_5,pm10,nitrogen_dioxide,sulphur_dioxide,carbon_monoxide,ozone,aerosol_optical_depth",
    "start_date": "2025-07-01",
    "end_date": "2026-07-01",
}, timeout=60)
aq.raise_for_status()
aq_data = aq.json().get("hourly", {})
times = aq_data.get("time", [])
print(f"Delhi AQ records: {len(times)}")
print(f"Fields: {list(aq_data.keys())}")

aod_vals = [v for v in aq_data.get("aerosol_optical_depth", []) if v is not None]
pm25_vals = [v for v in aq_data.get("pm2_5", []) if v is not None]
print(f"Non-null AOD values: {len(aod_vals)}")
print(f"Non-null PM2.5 values: {len(pm25_vals)}")
if aod_vals:
    print(f"AOD range: {min(aod_vals):.3f} - {max(aod_vals):.3f}")
if pm25_vals:
    print(f"PM2.5 range: {min(pm25_vals):.1f} - {max(pm25_vals):.1f}")

wx = requests.get("https://archive-api.open-meteo.com/v1/archive", params={
    "latitude": 28.62,
    "longitude": 77.22,
    "hourly": "temperature_2m,wind_speed_10m,relative_humidity_2m",
    "start_date": "2025-07-01",
    "end_date": "2026-07-01",
}, timeout=60)
wx.raise_for_status()
wx_data = wx.json().get("hourly", {})
print(f"Delhi weather records: {len(wx_data.get('time', []))}")

with open("data_store/delhi_historical.json", "w") as f:
    json.dump({"aq": aq_data, "wx": wx_data}, f)
print("Saved delhi_historical.json")

# Pull Panaji
print("\n=== Pulling Panaji historical data ===")
aq2 = requests.get("https://air-quality-api.open-meteo.com/v1/air-quality", params={
    "latitude": 15.49,
    "longitude": 73.83,
    "hourly": "pm2_5,pm10,nitrogen_dioxide,sulphur_dioxide,carbon_monoxide,ozone,aerosol_optical_depth",
    "start_date": "2025-07-01",
    "end_date": "2026-07-01",
}, timeout=60)
aq2.raise_for_status()
aq2_data = aq2.json().get("hourly", {})
print(f"Panaji AQ records: {len(aq2_data.get('time', []))}")

aod2 = [v for v in aq2_data.get("aerosol_optical_depth", []) if v is not None]
pm25_2 = [v for v in aq2_data.get("pm2_5", []) if v is not None]
print(f"Non-null AOD: {len(aod2)}, PM2.5: {len(pm25_2)}")
if aod2:
    print(f"AOD range: {min(aod2):.3f} - {max(aod2):.3f}")
if pm25_2:
    print(f"PM2.5 range: {min(pm25_2):.1f} - {max(pm25_2):.1f}")

wx2 = requests.get("https://archive-api.open-meteo.com/v1/archive", params={
    "latitude": 15.49,
    "longitude": 73.83,
    "hourly": "temperature_2m,wind_speed_10m,relative_humidity_2m",
    "start_date": "2025-07-01",
    "end_date": "2026-07-01",
}, timeout=60)
wx2.raise_for_status()
wx2_data = wx2.json().get("hourly", {})
print(f"Panaji weather records: {len(wx2_data.get('time', []))}")

with open("data_store/panaji_historical.json", "w") as f:
    json.dump({"aq": aq2_data, "wx": wx2_data}, f)
print("Saved panaji_historical.json")

print("\n=== DATA COLLECTION COMPLETE ===")
