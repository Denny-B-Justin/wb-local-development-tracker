"""The PIL metric catalog: pillars, their score components and indicator metadata."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache

import constants

PILLARS = ("prosperity", "infrastructure", "livability")

PILLAR_COMPONENTS: dict[str, tuple[str, ...]] = {
    "prosperity": (
        "Luminosity per Capita Score",
        "Luminosity per Area Score",
        "Built Area Development Score",
        "Tourism Score",
        "Agricultural Land Score",
    ),
    "infrastructure": (
        "Broadband Internet Score",
        "Mobile Internet Score",
        "Key Structure Internet Access Score",
        "Accessibility to Hospitals Score",
        "Accessibility to Schools Score",
    ),
    "livability": (
        "Emissions Score",
        "Air Quality Score",
        "Deforestation Score",
        "Emissions per Area Score",
        "Railway Heatwave Score",
        "Road Heatwave Score",
        "Road Flood Score",
        "Railway Flood Score",
    ),
}

# Raw score-table column -> canonical label, where they differ.
SCORE_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "Emissions per Area Score": ("Emissions Normalized Score", "emissions_normalized_score"),
}
PILLAR_COLUMNS = {pillar: f"{pillar.capitalize()} Score" for pillar in PILLARS}
COMPOSITE_COLUMNS = ("PIL Aggregate", "PIL Score", "Composite Score", "pil_aggregate", "composite_score")

CONTEXT_COLUMNS: dict[str, tuple[str, ...]] = {
    "population": ("Population", "population", "total_population"),
    "area": ("Total Land Area (km2)", "land_area_km2", "total_land_area_km2", "area_km2"),
}

COMPONENT_INDICATOR = {
    "broadband_internet_score": "average-broadband-download-speed",
    "mobile_internet_score": "average-cellular-download-speed",
    "key_structure_internet_access_score": "key-structures-without-internet-access",
    "accessibility_to_hospitals_score": "accessibility-to-health-services",
    "accessibility_to_schools_score": "accessibility-to-school-services",
    "railway_heatwave_score": "railway-heatwave-risk",
    "road_heatwave_score": "road-heatwave-risk",
    "road_flood_score": "road-flood-risk",
    "railway_flood_score": "railway-flood-risk",
    "emissions_score": "co2-equivalent-emissions-tonnes",
    "air_quality_score": "pm-2-5-concentration",
    "deforestation_score": "change-in-forest-area",
    "emissions_per_area_score": "co2-equivalent-emissions-per-area",
    "luminosity_per_capita_score": "luminosity-per-capita",
    "luminosity_per_area_score": "luminosity-per-area",
    "built_area_development_score": "change-in-build-area",
    "tourism_score": "number-of-tourism-pois",
    "agricultural_land_score": "total-land-area-for-agricultural-use-km2",
}


def metric_id(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


@dataclass(frozen=True)
class Component:
    id: str
    label: str
    canonical: str
    pillar: str


COMPONENTS: tuple[Component, ...] = tuple(
    Component(metric_id(label), re.sub(r"\s+Score$", "", label), label, pillar)
    for pillar in PILLARS
    for label in PILLAR_COMPONENTS[pillar]
)
COMPONENT_IDS = tuple(c.id for c in COMPONENTS)
COMPONENT_INDEX = {c.id: i for i, c in enumerate(COMPONENTS)}
COMPONENT_BY_ID = {c.id: c for c in COMPONENTS}
SCORE_LABELS = {f"{p}_score": f"{p.capitalize()} Score" for p in PILLARS}


def is_pillar(value: str | None) -> bool:
    return value in PILLARS


def is_metric(value: str | None) -> bool:
    return value == "composite" or is_pillar(value) or value in COMPONENT_INDEX


def components_of(pillar: str) -> list[Component]:
    return [c for c in COMPONENTS if c.pillar == pillar]


@lru_cache(maxsize=1)
def indicator_definitions() -> list[dict]:
    with (constants.REFERENCE_DIR / "indicator_definitions.json").open(encoding="utf-8") as handle:
        return json.load(handle)["indicatorDefinitions"]


def indicator_name(label: str) -> str:
    return re.sub(r"\s*\(unit:.*$", "", label).strip()


@lru_cache(maxsize=1)
def data_sources() -> list[dict]:
    order = {p: i for i, p in enumerate(PILLARS)}
    rows = []
    for definition in sorted(indicator_definitions(), key=lambda d: (order.get(d.get("pillar"), 9), d.get("sortOrder", 0))):
        for source in definition.get("sources", []):
            url = str(source.get("url", ""))
            if url.startswith(("https://", "http://")):
                rows.append({
                    "indicator": indicator_name(definition["label"]),
                    "pillar": definition.get("pillar"),
                    "label": source.get("label", url),
                    "url": url,
                })
    return rows


def description_of(component_id: str) -> str | None:
    indicator = COMPONENT_INDICATOR.get(component_id)
    for definition in indicator_definitions():
        if definition["id"] == indicator:
            return definition.get("description")
    return None
