"""OpenStreetMap Overpass API connector.

Real mode : Overpass QL queries for landuse polygons, highway networks,
            and industrial areas within the bbox.
Mock mode : deterministic synthetic land-use and road-density records
            for the analysis grid cells.
"""

from __future__ import annotations

import hashlib
from datetime import datetime

import requests

from ingestion.base_connector import BaseConnector
from ingestion import config as cfg


class OSMConnector(BaseConnector):
    source_name = "osm"

    def _pull_real(
        self, bbox: tuple[float, float, float, float],
        since: datetime, until: datetime,
    ) -> list[dict]:
        min_lon, min_lat, max_lon, max_lat = bbox
        bbox_str = f"{min_lat},{min_lon},{max_lat},{max_lon}"

        records: list[dict] = []

        # Query 1: Land use polygons
        landuse_query = f"""
        [out:json][timeout:60];
        (
          way["landuse"]({bbox_str});
          relation["landuse"]({bbox_str});
        );
        out center;
        """
        self._throttle()
        try:
            resp = requests.post(cfg.OVERPASS_URL, data={"data": landuse_query}, timeout=90)
            resp.raise_for_status()
            for el in resp.json().get("elements", []):
                center = el.get("center", {})
                lat = center.get("lat") or el.get("lat")
                lon = center.get("lon") or el.get("lon")
                if lat is None or lon is None:
                    continue
                records.append({
                    "source": "osm",
                    "feature_type": "landuse",
                    "landuse": el.get("tags", {}).get("landuse", "unknown"),
                    "lat": lat,
                    "lon": lon,
                })
        except Exception:
            pass

        # Query 2: Roads (highway=*)
        road_query = f"""
        [out:json][timeout:60];
        way["highway"]({bbox_str});
        out geom;
        """
        self._throttle()
        try:
            resp = requests.post(cfg.OVERPASS_URL, data={"data": road_query}, timeout=90)
            resp.raise_for_status()
            for el in resp.json().get("elements", []):
                geom = el.get("geometry", [])
                if geom:
                    mid = geom[len(geom)//2]
                    records.append({
                        "source": "osm",
                        "feature_type": "road",
                        "highway": el.get("tags", {}).get("highway", "unclassified"),
                        "lat": mid.get("lat"),
                        "lon": mid.get("lon"),
                        "node_count": len(geom),
                    })
        except Exception:
            pass

        # Query 3: Industrial areas
        ind_query = f"""
        [out:json][timeout:60];
        (
          way["landuse"="industrial"]({bbox_str});
          relation["landuse"="industrial"]({bbox_str});
        );
        out center;
        """
        self._throttle()
        try:
            resp = requests.post(cfg.OVERPASS_URL, data={"data": ind_query}, timeout=90)
            resp.raise_for_status()
            for el in resp.json().get("elements", []):
                center = el.get("center", {})
                lat = center.get("lat") or el.get("lat")
                lon = center.get("lon") or el.get("lon")
                if lat is None:
                    continue
                records.append({
                    "source": "osm",
                    "feature_type": "industrial",
                    "lat": lat,
                    "lon": lon,
                    "name": el.get("tags", {}).get("name", ""),
                })
        except Exception:
            pass

        # Query 4: Construction areas
        const_query = f"""
        [out:json][timeout:60];
        (
          way["landuse"="construction"]({bbox_str});
          relation["landuse"="construction"]({bbox_str});
        );
        out center;
        """
        self._throttle()
        try:
            resp = requests.post(cfg.OVERPASS_URL, data={"data": const_query}, timeout=90)
            resp.raise_for_status()
            for el in resp.json().get("elements", []):
                center = el.get("center", {})
                lat = center.get("lat") or el.get("lat")
                lon = center.get("lon") or el.get("lon")
                if lat is None:
                    continue
                records.append({
                    "source": "osm",
                    "feature_type": "construction",
                    "lat": lat,
                    "lon": lon,
                })
        except Exception:
            pass

        return records

    def _pull_mock(
        self, bbox: tuple[float, float, float, float],
        since: datetime, until: datetime,
    ) -> list[dict]:
        """Generate deterministic land-use and road features for the grid."""
        min_lon, min_lat, max_lon, max_lat = bbox

        records: list[dict] = []
        step = 0.01  # ~1 km
        lat = min_lat
        while lat <= max_lat:
            lon = min_lon
            while lon <= max_lon:
                s = _seed(lat, lon)

                # Deterministic land-use class
                r = _rng(s)
                if r < 0.35:
                    landuse = "residential"
                elif r < 0.55:
                    landuse = "commercial"
                elif r < 0.70:
                    landuse = "industrial"
                elif r < 0.85:
                    landuse = "mixed"
                else:
                    landuse = "green"

                records.append({
                    "source": "osm",
                    "feature_type": "landuse",
                    "landuse": landuse,
                    "lat": round(lat, 4),
                    "lon": round(lon, 4),
                })

                # Road density proxy: number of road nodes per cell
                road_nodes = int(5 + 35 * _rng(s + 1))
                if landuse == "commercial":
                    road_nodes = int(road_nodes * 1.5)
                elif landuse == "green":
                    road_nodes = int(road_nodes * 0.3)

                records.append({
                    "source": "osm",
                    "feature_type": "road",
                    "highway": "mixed",
                    "lat": round(lat, 4),
                    "lon": round(lon, 4),
                    "node_count": road_nodes,
                })

                # Industrial flag
                if landuse == "industrial" or _rng(s + 2) < 0.08:
                    records.append({
                        "source": "osm",
                        "feature_type": "industrial",
                        "lat": round(lat, 4),
                        "lon": round(lon, 4),
                        "name": f"Industrial Zone {int(_rng(s+3)*100)}",
                    })

                # Construction density mock (0.0 to 1.0 proxy)
                const_density = 0.0
                if landuse == "commercial" and _rng(s + 4) < 0.2:
                    const_density = round(_rng(s + 5) * 0.4, 2)
                elif landuse == "residential" and _rng(s + 6) < 0.1:
                    const_density = round(_rng(s + 7) * 0.2, 2)

                if const_density > 0:
                    records.append({
                        "source": "osm",
                        "feature_type": "construction",
                        "lat": round(lat, 4),
                        "lon": round(lon, 4),
                        "density": const_density,
                    })

                lon += step
            lat += step

        return records


def _seed(lat: float, lon: float) -> int:
    return int(hashlib.md5(f"{lat:.4f},{lon:.4f}".encode()).hexdigest()[:8], 16)


def _rng(s: int) -> float:
    return ((s * 1103515245 + 12345) & 0x7FFF_FFFF) / 0x7FFF_FFFF
