"""Connector registry — one import brings every source connector."""

from ingestion.connectors.openaq import OpenAQConnector
from ingestion.connectors.cpcb import CPCBConnector
from ingestion.connectors.waqi import WAQIConnector
from ingestion.connectors.open_meteo import OpenMeteoConnector
from ingestion.connectors.osm import OSMConnector
from ingestion.connectors.gee_satellite import GEESatelliteConnector

CONNECTORS: dict[str, type] = {
    "openaq": OpenAQConnector,
    "cpcb": CPCBConnector,
    "waqi": WAQIConnector,
    "open_meteo": OpenMeteoConnector,
    "osm": OSMConnector,
    "gee_sentinel5p": GEESatelliteConnector,
    "gee_modis": GEESatelliteConnector,
}

__all__ = [
    "OpenAQConnector",
    "CPCBConnector",
    "WAQIConnector",
    "OpenMeteoConnector",
    "OSMConnector",
    "GEESatelliteConnector",
    "CONNECTORS",
]
