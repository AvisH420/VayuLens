# contracts/ — Shared data schemas

**Owner:** shared / all roles
**Purpose:** Single source of truth for every data shape that crosses a module
boundary. Each role builds *against* these schemas so the four areas integrate
without surprises.

## ⚠️ Changing a schema is a group decision

These files are a contract between four people. If you change a field, rename
one, or change a type, **you break someone else's code.**

> **Rule: tell the group first.**
> Before editing anything in `contracts/`, announce the proposed change to the
> team, agree on it, and only then edit. Treat every change here as a breaking
> change until proven otherwise.

## Schemas

| Schema           | File                  | Produced by            | Consumed by                  |
| ---------------- | --------------------- | ---------------------- | ---------------------------- |
| `grid_cell`      | `grid_cell.py`        | data (grid builder)    | everyone                     |
| `measurement`    | `measurement.py`      | data (calibration/fusion) | attribution, forecasting  |
| `attribution`    | `attribution.py`      | attribution            | decision, api, frontend      |
| `forecast`       | `forecast.py`         | forecasting            | decision, api, frontend      |
| `recommendation` | `recommendation.py`   | decision               | api, frontend                |

## Field reference

- **grid_cell**: `cell_id, lat, lon, ward, land_use_class, road_density, industrial_flag`
- **measurement**: `cell_id, timestamp, pm25, pm10, no2, aod, aerosol_index, temp, wind_speed, wind_dir, quality_score, uncertainty`
- **attribution**: `cell_id, timestamp, sources{traffic, construction, industry, burning, dust}, confidence`
- **forecast**: `cell_id, horizon[{t, aqi}]`
- **recommendation**: `cell_id, action, justification, regulation_citation, priority_score`

Schemas are defined as [pydantic](https://docs.pydantic.dev/) models so they
double as runtime validation and as JSON-schema export (`Model.model_json_schema()`).
