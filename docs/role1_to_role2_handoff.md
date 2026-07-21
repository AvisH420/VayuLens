# Role 1 → Role 2 data handoff (integration gap)

**Status:** blocking the "real data" path. The live demo runs on `demo_engine`
and is unaffected. This only matters when we run the actual pipeline
end-to-end: Role 1 ingestion → Role 2 attribution/forecasting.

**Owner to fix:** Role 1 (data), with Role 2 review on field semantics.

---

## The problem in one line

Role 2's attribution/forecasting takes a **`GridCellInput`** with 13 fields.
Role 1 produces a **`Measurement`** (`contracts/measurement.py`). Only **5 of
the 13** line up. The rest are renamed, live on a different object, or are not
produced at all — so Role 2 cannot currently be fed from Role 1's output.

## Field-by-field

Role 2 input is `attribution/models.py :: GridCellInput`. Role 1 output is
`contracts/measurement.py :: Measurement` (plus static `GridCell` context).

| Role 2 needs (`GridCellInput`) | Role 1 provides | Status | Fix |
|---|---|---|---|
| `cell_id` | `Measurement.cell_id` | ✅ | agree on format (see note) |
| `pm25` | `Measurement.pm25` | ✅ | — |
| `no2` | `Measurement.no2` | ✅ | — |
| `aod` | `Measurement.aod` | ✅ | — |
| `wind_speed` | `Measurement.wind_speed` | ✅ | — |
| `lat`, `lon` | — (on `GridCell`, not `Measurement`) | ⚠️ missing | carry cell centroid lat/lon onto `Measurement`, or hand Role 2 the `GridCell` alongside |
| `wind_direction` | `Measurement.wind_dir` | ⚠️ rename | same value, different name — map `wind_dir → wind_direction` |
| `uv_aerosol_index` | `Measurement.aerosol_index` | ⚠️ rename | Role 1's `aerosol_index` **is** the S5P absorbing (UV) aerosol index — same quantity, confirm and map |
| `so2` | — (connectors fetch it, fusion drops it) | ❌ missing | carry SO₂ through `calibration → fusion → Measurement`; the raw connectors already return it |
| `road_density` | `GridCell.road_density` (static) | ⚠️ different object | join from `GridCell` when assembling the Role 2 input |
| `industrial_proximity` (metres) | `GridCell.industrial_flag` (bool only) | ❌ missing | derive a proximity/distance metric during grid build, or Role 2 adapts to consume the boolean flag |
| `construction_density` | — (produced nowhere) | ❌ missing | new field: derive from OSM construction landuse/POIs in grid build, or supply a default until available |

**5 aligned, 3 easy (rename/join), 3 genuinely missing** (`so2`,
`industrial_proximity`, `construction_density`).

## `cell_id` format — agree on one

- Role 1 emits `grid_28.61_77.20` (`grid_{lat}_{lon}`).
- Role 2's docstring examples say `cell_row_col`.

It is a passthrough string, so nothing crashes — but the two sides must use the
**same** ids or attribution results can't be joined back to the grid. Recommend
adopting Role 1's `grid_{lat}_{lon}` since it matches `contracts/grid_cell.py`
and the frontend.

## Recommended shape of the fix

1. **Role 1**: extend the fusion output so `Measurement` (or a thin wrapper)
   carries `lat`, `lon`, and `so2`. SO₂ is already fetched by the OpenAQ / CPCB
   / GEE connectors — it's only lost at the fusion step.
2. **Grid build**: add `industrial_proximity` (metres to nearest industrial
   source) and `construction_density` (from OSM) to `GridCell`. These are
   land-use products Role 1 already has the OSM data for.
3. **Assembly** (whoever wires the pipeline): build each `GridCellInput` by
   joining `Measurement` (dynamic) + `GridCell` (static), applying the two
   renames (`wind_dir → wind_direction`, `aerosol_index → uv_aerosol_index`).
4. **Output side is already handled**: Role 2 → `contracts/` conversion is done
   in `api/role2_adapter.py` (run `python api/role2_adapter.py` to verify).

## What this unblocks

With the above, the pipeline runs end-to-end on real data:

```
Role 1 (real APIs, needs WAQI token) → Measurement + GridCell
    → GridCellInput → Role 2 attribution/forecast/simulate
    → role2_adapter → contracts → gateway → frontend
```

Until then the gateway serves `demo_engine`, which is correct and intended for
the demo. This handoff is what makes "flip to real data" possible, not a bug in
anyone's module.
