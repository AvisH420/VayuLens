"""Domain utilities: AQI banding and GRAP stage mapping (CPCB scale)."""
from __future__ import annotations

# CPCB National AQI bands
AQI_BANDS = [
    (0, 50, "Good"),
    (51, 100, "Satisfactory"),
    (101, 200, "Moderate"),
    (201, 300, "Poor"),
    (301, 400, "Very Poor"),
    (401, 500, "Severe"),
    (501, 10_000, "Severe+"),
]

# GRAP stages keyed to AQI thresholds (Delhi-NCR schedule)
GRAP_STAGES = [
    (201, 300, "Stage I", "Poor"),
    (301, 400, "Stage II", "Very Poor"),
    (401, 450, "Stage III", "Severe"),
    (451, 10_000, "Stage IV", "Severe+"),
]


def aqi_band(aqi: float) -> str:
    for lo, hi, label in AQI_BANDS:
        if lo <= aqi <= hi:
            return label
    return "Unknown"


def grap_stage(aqi: float) -> str | None:
    for lo, hi, stage, _ in GRAP_STAGES:
        if lo <= aqi <= hi:
            return stage
    return None


def grap_stage_number(aqi: float) -> int:
    stage = grap_stage(aqi)
    return {"Stage I": 1, "Stage II": 2, "Stage III": 3, "Stage IV": 4}.get(
        stage or "", 0
    )


def legal_urgency(aqi: float) -> str:
    """Qualitative legal urgency tied to enforceability under GRAP/Air Act."""
    n = grap_stage_number(aqi)
    return {0: "advisory", 1: "monitor", 2: "restrict", 3: "enforce",
            4: "emergency"}.get(n, "advisory")
