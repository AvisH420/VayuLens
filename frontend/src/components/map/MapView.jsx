// Map + grid layers. MapLibre over a light Carto basemap. Both cities'
// ~1 km grids live in one GeoJSON source, so panning from Delhi to Goa
// shows Panaji's data without touching the city switcher; the switcher
// only flies the camera. When the viewport settles nearer the other city,
// onViewCity tells the shell so panels follow. Recolored per view (live
// AQI / dominant source / forecast hour / what-if delta) via paint
// expressions. Feeds the lens cursor through "lens:probe" events.

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { aqiStepExpression, SOURCES, dominantSource } from "../../lib/aqi.js";

const BASEMAP = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";

function cellsToGeoJSON(cities, scenario) {
  const features = [];
  for (const city of Object.values(cities)) {
    const { bbox, latStep, lonStep } = city.cfg;
    for (const c of city.cells) {
      const [w, s, e, n] = c.bounds;
      const dom = dominantSource(c.shares);
      // fade the grid out over its outer ~5 cells so the analysis extent
      // dissolves into the basemap instead of ending at a hard edge
      const edgeCells = Math.min(
        (c.lat - bbox.latMin) / latStep,
        (bbox.latMax - c.lat) / latStep,
        (c.lon - bbox.lonMin) / lonStep,
        (bbox.lonMax - c.lon) / lonStep
      );
      const t = Math.min(1, edgeCells / 5);
      const fade = +(0.08 + 0.92 * t * t * (3 - 2 * t)).toFixed(3);
      const props = {
        cell_id: c.cell_id,
        aqi: c.aqi,
        ward: c.ward,
        fade,
        dominant: dom.key,
        domShare: Math.round(c.shares[dom.key] * 100),
      };
      c.forecast.forEach((v, i) => (props[`f${i}`] = v));
      if (scenario) {
        const r = scenario.results.get(c.cell_id);
        if (r) r.delta.forEach((v, i) => (props[`d${i}`] = v));
      }
      features.push({
        type: "Feature",
        properties: props,
        geometry: {
          type: "Polygon",
          coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
        },
      });
    }
  }
  return { type: "FeatureCollection", features };
}

function fillColor(layer, hourIdx) {
  if (layer === "sources") {
    const m = ["match", ["get", "dominant"]];
    for (const s of SOURCES) m.push(s.key, s.color);
    m.push("#9aa8a0");
    return m;
  }
  if (layer === "forecast") return aqiStepExpression(`f${hourIdx}`);
  if (layer === "whatif")
    // diverging: improvement cool blue, unchanged neutral, worsening warm red
    return [
      "interpolate",
      ["linear"],
      ["coalesce", ["get", `d${hourIdx}`], 0],
      -70, "#104281",
      -30, "#3987e5",
      -6, "#9ec5f4",
      0, "#edece6",
      8, "#e8a08e",
      25, "#c74436",
    ];
  return aqiStepExpression("aqi");
}

export default function MapView({
  cities,
  cityId,
  flyNonce,
  onViewCity,
  layer,
  hourIdx,
  scenario,
  selectedId,
  onSelect,
}) {
  const mapRef = useRef(null);
  const containerRef = useRef(null);
  const readyRef = useRef(false);

  // current view lives in refs so map event handlers stay fresh
  const viewRef = useRef({ layer, hourIdx });
  viewRef.current = { layer, hourIdx };
  const cityIdRef = useRef(cityId);
  cityIdRef.current = cityId;
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const onViewCityRef = useRef(onViewCity);
  onViewCityRef.current = onViewCity;

  function applyView() {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    const { layer: l, hourIdx: h } = viewRef.current;
    map.setPaintProperty("cells-fill", "fill-color", fillColor(l, h));
    map.setPaintProperty("cells-fill", "fill-opacity", [
      "*",
      l === "whatif" ? 0.72 : 0.55,
      ["get", "fade"],
    ]);
    map.setFilter("cells-selected", ["==", ["get", "cell_id"], selectedId ?? ""]);
  }

  useEffect(() => {
    const start = cities[cityIdRef.current].cfg;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: BASEMAP,
      center: start.center,
      zoom: start.zoom,
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    if (import.meta.env.DEV) window.__vlMap = map; // dev/demo handle

    const layerValueFromProps = (p) => {
      const { layer: l, hourIdx: h } = viewRef.current;
      if (l === "forecast" || l === "whatif") return p[`f${h}`] ?? p.aqi;
      return p.aqi;
    };

    map.on("load", () => {
      map.addSource("cells", {
        type: "geojson",
        data: cellsToGeoJSON(cities, null),
      });
      map.addLayer({
        id: "cells-fill",
        type: "fill",
        source: "cells",
        paint: {
          "fill-color": fillColor("aqi", 0),
          "fill-opacity": ["*", 0.55, ["get", "fade"]],
          "fill-outline-color": [
            "rgba", 255, 255, 255,
            ["*", 0.55, ["get", "fade"]],
          ],
        },
      });
      map.addLayer({
        id: "cells-selected",
        type: "line",
        source: "cells",
        paint: { "line-color": "#182420", "line-width": 2 },
        filter: ["==", ["get", "cell_id"], ""],
      });

      map.on("mousemove", "cells-fill", (e) => {
        const p = e.features?.[0]?.properties;
        if (!p) return;
        const srcLabel = SOURCES.find((s) => s.key === p.dominant)?.label;
        window.dispatchEvent(
          new CustomEvent("lens:probe", {
            detail: {
              aqi: layerValueFromProps(p),
              ward: p.ward,
              sub: `${srcLabel} ${p.domShare}%`,
            },
          })
        );
      });
      map.on("mouseleave", "cells-fill", () =>
        window.dispatchEvent(new CustomEvent("lens:probe", { detail: null }))
      );
      map.on("click", (e) => {
        const hits = map.queryRenderedFeatures(e.point, { layers: ["cells-fill"] });
        onSelectRef.current(hits[0]?.properties?.cell_id ?? null);
      });

      // panels follow whichever city the viewport settles over
      map.on("moveend", () => {
        const c = map.getCenter();
        let best = null;
        let bestD = Infinity;
        for (const city of Object.values(cities)) {
          const [lon, lat] = city.cfg.center;
          const d = (c.lat - lat) ** 2 + (c.lng - lon) ** 2;
          if (d < bestD) {
            bestD = d;
            best = city.cfg.id;
          }
        }
        if (best && best !== cityIdRef.current) onViewCityRef.current(best);
      });

      readyRef.current = true;
      applyView();
    });

    return () => {
      window.dispatchEvent(new CustomEvent("lens:probe", { detail: null }));
      map.remove();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // explicit city switch (button) flies the camera
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !flyNonce) return;
    const cfg = cities[cityId].cfg;
    map.flyTo({ center: cfg.center, zoom: cfg.zoom, duration: 1600 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flyNonce]);

  // scenario changes rebuild the source data
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    map.getSource("cells").setData(cellsToGeoJSON(cities, scenario));
    // Re-run on `cities` too: the grid starts as the client-side build and is
    // swapped for the real API grid once it loads, so the source data must
    // refresh then — not only when a what-if scenario changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenario, cities]);

  // view changes repaint
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(applyView, [layer, hourIdx, selectedId, scenario]);

  return <div ref={containerRef} className="map-container" />;
}
