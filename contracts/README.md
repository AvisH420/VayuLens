# contracts/

The single source of truth for every data shape that crosses a module boundary. Every module reads and
writes these schemas, so the four areas of the platform integrate without surprises. They are defined as
[Pydantic](https://docs.pydantic.dev/) models, so they double as runtime validation and JSON-schema
export (`Model.model_json_schema()`).

## Schemas

| Schema | File | Produced by | Consumed by |
| --- | --- | --- | --- |
| `GridCell` | `grid_cell.py` | data (grid builder) | attribution, forecasting |
| `Measurement` | `measurement.py` | data (calibration/fusion) | attribution, forecasting |
| `Attribution` | `attribution.py` | attribution | decision, api, frontend |
| `Forecast` | `forecast.py` | forecasting | decision, api, frontend |
| `Recommendation` | `recommendation.py` | decision | api, frontend |

## Fields

- **GridCell** — `cell_id, lat, lon, ward, land_use_class, road_density, industrial_flag,
  industrial_proximity, construction_density`
- **Measurement** — `cell_id, lat, lon, timestamp, pm25, pm10, no2, so2, aod, uv_aerosol_index, temp,
  wind_speed, wind_direction, quality_score, uncertainty`
- **Attribution** — `cell_id, timestamp, sources{traffic, construction, industry, burning, dust}, confidence`
- **Forecast** — `cell_id, horizon[{t, aqi}]`
- **Recommendation** — `cell_id, action, justification, regulation_citation, priority_score`
