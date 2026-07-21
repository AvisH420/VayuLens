# VayuLens — Architecture Notes

> Placeholder. Expand as the design solidifies.

## Data flow

```
ingestion ─▶ data ─▶ attribution ─┐
                  ─▶ forecasting ─┼─▶ decision ◀─ rag
                                  ▼
                                 api ─▶ frontend
```

- **ingestion → data**: raw pulls (incl. GEE satellite) → calibrated, fused
  `Measurement`s on the ~1km grid.
- **data → attribution / forecasting**: measurements drive apportionment and
  24-72h forecasts.
- **attribution / forecasting + rag → decision**: grounded, regulation-cited
  recommendations.
- **api → frontend**: gateway aggregates modules; React app renders map,
  forecast slider, what-if panel, chat.

## Module boundaries & ownership

See the ownership table in the [root README](../README.md). Four roles, four
non-overlapping areas; everything integrates through [`contracts/`](../contracts/README.md).

## Shared contracts

`grid_cell`, `measurement`, `attribution`, `forecast`, `recommendation`.
Changing any of these is a breaking change — **tell the group first.**

## Open questions (to fill in)

- [ ] Grid CRS / exact cell sizing.
- [ ] Source list and calibration references.
- [ ] Dispersion model choice.
- [ ] Vector store + embedding model.
- [ ] Auth / deployment topology.
