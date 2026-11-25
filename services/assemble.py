"""Turn Unity Catalog rows (or a legacy JSON bundle) into one canonical country bundle."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from countries import Country

from . import catalog, databricks
from .text import clean, fold

log = logging.getLogger(__name__)

NAME_COLUMNS = ("province", "district", "municipality")
COORD_DIGITS = 5


def unit_id(iso3: str, key: str) -> str:
    return hashlib.sha1(f"{iso3}|{key}".encode("utf-8")).hexdigest()[:12]


def match_key(names: dict[str, str]) -> str:
    return "::".join(fold(names[c]) for c in NAME_COLUMNS)


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", fold(str(name)))


def resolve(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    columns = list(columns)
    normalized = {_norm(c): c for c in columns}
    for candidate in candidates:
        if candidate in columns:
            return candidate
        hit = normalized.get(_norm(candidate))
        if hit is not None:
            return hit
    return None


def _number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).replace(",", "").strip()
        if not text:
            return None
        try:
            number = float(text)
        except ValueError:
            return None
    return number if math.isfinite(number) else None


def _round(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(value, digits)


def _mean(values: Iterable[float | None]) -> float | None:
    finite = [v for v in values if v is not None]
    return round(sum(finite) / len(finite), 2) if finite else None


def _names(row: dict[str, Any], columns: dict[str, str | None]) -> dict[str, str]:
    province = clean(row.get(columns["province"]) if columns["province"] else "", 160)
    district = clean(row.get(columns["district"]) if columns["district"] else "", 160) or province
    municipality = clean(row.get(columns["municipality"]) if columns["municipality"] else "", 160)
    return {"province": province, "district": district, "municipality": municipality}


def _hierarchy_columns(country: Country, columns: list[str]) -> dict[str, str | None]:
    return {role: resolve(columns, [name]) for role, name in country.source.hierarchy.items()}


def _score_columns(columns: list[str]) -> dict[str, str | None]:
    mapping: dict[str, str | None] = {}
    for component in catalog.COMPONENTS:
        mapping[component.id] = resolve(columns, [component.canonical, *catalog.SCORE_COLUMN_ALIASES.get(component.canonical, ())])
    for pillar, column in catalog.PILLAR_COLUMNS.items():
        mapping[pillar] = resolve(columns, [column])
    mapping["composite"] = resolve(columns, catalog.COMPOSITE_COLUMNS)
    return mapping


def _context_columns(country: Country, columns: list[str]) -> dict[str, str | None]:
    out = {}
    for key, candidates in catalog.CONTEXT_COLUMNS.items():
        extra = country.source.column_aliases.get(candidates[0], ())
        out[key] = resolve(columns, [*candidates, *extra])
    return out


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return frame.astype(object).where(pd.notna(frame), None).to_dict("records") if not frame.empty else []


def _row_values(row: dict[str, Any] | None, columns: dict[str, str | None]) -> list[float | None]:
    if row is None:
        return [None] * (4 + len(catalog.COMPONENTS))
    pillars = [_round(_number(row.get(columns[p]))) if columns[p] else None for p in catalog.PILLARS]
    components = [_round(_number(row.get(columns[c.id]))) if columns[c.id] else None for c in catalog.COMPONENTS]
    composite = _round(_number(row.get(columns["composite"]))) if columns["composite"] else None
    if composite is None:
        composite = _mean(pillars)
    return [composite, *pillars, *components]


class BundleBuilder:
    def __init__(self, country: Country, source: str):
        self.country = country
        self.source = source
        self.units: dict[str, dict[str, Any]] = {}
        self.scores: dict[int, dict[str, list[float | None]]] = {}

    def unit(self, names: dict[str, str]) -> str | None:
        if not names["municipality"] or not names["province"]:
            return None
        key = match_key(names)
        uid = unit_id(self.country.iso3, key)
        if uid not in self.units:
            self.units[uid] = {"id": uid, "key": key, "names": names}
        return uid

    def add(self, year: int, names: dict[str, str], values: list[float | None], population: float | None, area: float | None) -> None:
        uid = self.unit(names)
        if uid is None:
            return
        if area is not None and area > 100000:
            area = area / 1_000_000
        self.scores.setdefault(year, {})[uid] = [*values, _round(population, 0), _round(area, 2)]

    def finish(self, features: list[dict[str, Any]], boundary_only: int) -> tuple[dict[str, Any], dict[str, Any]]:
        mapped = sorted({f["properties"]["id"] for f in features})
        bundle = {
            "iso3": self.country.iso3,
            "source": self.source,
            "builtAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "components": list(catalog.COMPONENT_IDS),
            "years": sorted(self.scores),
            "units": sorted(self.units.values(), key=lambda u: (u["names"]["province"], u["names"]["district"], u["names"]["municipality"])),
            "scores": {str(year): rows for year, rows in sorted(self.scores.items())},
            "mapped": mapped,
            "boundaryOnly": boundary_only,
        }
        return bundle, {"type": "FeatureCollection", "features": features}


def _round_coords(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        if value and isinstance(value[0], (int, float)):
            return [round(float(v), COORD_DIGITS) for v in value[:2]]
        return [_round_coords(v) for v in value]
    return value


def _decode_geometry(value: Any):
    from shapely import wkb, wkt
    from shapely.geometry import shape

    if value is None:
        return None
    if isinstance(value, (bytes, bytearray, memoryview)):
        return wkb.loads(bytes(value))
    if isinstance(value, dict):
        return shape(value)
    text = str(value).strip()
    if not text:
        return None
    if text[0] in "{[":
        return shape(json.loads(text))
    if len(text) > 16 and len(text) % 2 == 0 and all(ch in "0123456789abcdefABCDEF" for ch in text):
        try:
            return wkb.loads(bytes.fromhex(text))
        except Exception:  # noqa: BLE001
            pass
    return wkt.loads(text)


def _to_wgs84(geom, crs: str):
    minx, miny, maxx, maxy = geom.bounds
    looks_projected = max(abs(minx), abs(maxx)) > 180 or max(abs(miny), abs(maxy)) > 90
    if crs.upper() in ("EPSG:4326", "4326") and not looks_projected:
        return geom
    from pyproj import Transformer
    from shapely.ops import transform

    source = crs if crs.upper() not in ("EPSG:4326", "4326") else "EPSG:6933"
    transformer = Transformer.from_crs(source, "EPSG:4326", always_xy=True)
    return transform(lambda x, y, z=None: transformer.transform(x, y), geom)


def _features(builder: BundleBuilder, rows: list[tuple[dict[str, str], Any]]) -> tuple[list[dict[str, Any]], int]:
    from shapely.geometry import mapping
    from shapely.ops import unary_union

    country = builder.country
    by_key = {u["key"]: u for u in builder.units.values()}
    grouped: dict[str, list] = {}
    unmatched: set[str] = set()
    failures = 0
    for names, raw in rows:
        key = match_key(names)
        if key not in by_key:
            unmatched.add(key)
            continue
        try:
            geom = _decode_geometry(raw)
        except Exception:  # noqa: BLE001
            failures += 1
            continue
        if geom is None or geom.is_empty:
            continue
        grouped.setdefault(key, []).append(_to_wgs84(geom, country.source.crs))
    if failures:
        log.warning("%s: %d boundary rows failed to decode", country.iso3, failures)
    features = []
    level = country.local_level.column
    for key, geoms in grouped.items():
        merged = geoms[0] if len(geoms) == 1 else unary_union(geoms)
        simplified = merged.simplify(country.source.simplify_tolerance, preserve_topology=True) if country.source.simplify_tolerance else merged
        if simplified.is_empty:
            simplified = merged
        unit = by_key[key]
        minx, miny, maxx, maxy = simplified.bounds
        features.append({
            "type": "Feature",
            "properties": {
                "id": unit["id"],
                "name": unit["names"][level],
                "bbox": [round(minx, 4), round(miny, 4), round(maxx, 4), round(maxy, 4)],
            },
            "geometry": {"type": mapping(simplified)["type"], "coordinates": _round_coords(mapping(simplified)["coordinates"])},
        })
    return features, len(unmatched)


def from_databricks(country: Country) -> tuple[dict[str, Any], dict[str, Any]]:
    tables = country.tables
    log.info("Assembling %s from %s (%s, %s, %s)", country.iso3, "Unity Catalog", tables["indicators"], tables["scores"], tables["boundaries"])
    admin = databricks.read_table(tables["indicators"])
    scores = databricks.read_table(tables["scores"])
    if scores.empty:
        raise RuntimeError(f"{tables['scores']} returned no rows")
    builder = BundleBuilder(country, "databricks")

    admin_cols, score_cols = list(admin.columns), list(scores.columns)
    admin_h = _hierarchy_columns(country, admin_cols)
    score_h = _hierarchy_columns(country, score_cols)
    admin_year = resolve(admin_cols, country.source.year_candidates)
    score_year = resolve(score_cols, country.source.year_candidates)
    if score_year is None:
        raise RuntimeError(f"{tables['scores']}: no year column among {country.source.year_candidates}")
    context_cols = _context_columns(country, admin_cols)
    score_map = _score_columns(score_cols)
    missing = [k for k, v in score_map.items() if v is None and k != "composite"]
    if missing:
        log.warning("%s: score columns not found: %s", tables["scores"], missing)

    context: dict[str, tuple[float | None, float | None]] = {}
    for row in _records(admin):
        year = _number(row.get(admin_year)) if admin_year else None
        names = _names(row, admin_h)
        context[f"{int(year) if year else ''}|{match_key(names)}"] = (
            _number(row.get(context_cols["population"])) if context_cols["population"] else None,
            _number(row.get(context_cols["area"])) if context_cols["area"] else None,
        )

    for row in _records(scores):
        year = _number(row.get(score_year))
        if year is None:
            continue
        names = _names(row, score_h)
        population, area = context.get(f"{int(year)}|{match_key(names)}", (None, None))
        builder.add(int(year), names, _row_values(row, score_map), population, area)

    boundaries = databricks.read_table(tables["boundaries"])
    rows: list[tuple[dict[str, str], Any]] = []
    if not boundaries.empty:
        cols = list(boundaries.columns)
        roles = {role: resolve(cols, candidates) for role, candidates in country.source.boundary_candidates.items()}
        roles["district"] = roles.get("district") or roles["province"]
        geom_col = resolve(cols, country.source.geometry_candidates)
        if not (roles["municipality"] and roles["province"] and geom_col):
            raise RuntimeError(f"{tables['boundaries']}: cannot resolve boundary columns from {cols}")
        for row in _records(boundaries):
            rows.append((_names(row, roles), row.get(geom_col)))
    features, boundary_only = _features(builder, rows)
    return builder.finish(features, boundary_only)


def from_legacy(country: Country, folder: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """The demo's bundled analytics-data.json + municipalities.geojson (offline fallback)."""
    with (folder / "analytics-data.json").open(encoding="utf-8") as handle:
        data = json.load(handle)
    builder = BundleBuilder(country, "legacy")
    for item in data["municipalities"]:
        if item.get("year") is None:
            continue
        names = {"province": clean(item["province"]), "district": clean(item["district"]) or clean(item["province"]), "municipality": clean(item["municipality"])}
        pillars = [_round(_number(item["scores"].get(f"{p}_score"))) for p in catalog.PILLARS]
        components = [_round(_number(item["scoreComponents"].get(c.id))) for c in catalog.COMPONENTS]
        context = item.get("context") or {}
        builder.add(int(item["year"]), names, [_mean(pillars), *pillars, *components], _number(context.get("population")), _number(context.get("totalLandAreaKm2")))
    with (folder / "municipalities.geojson").open(encoding="utf-8") as handle:
        geo = json.load(handle)
    rows = []
    for feature in geo["features"]:
        p = feature["properties"]
        rows.append(({"province": clean(p.get("Province")), "district": clean(p.get("District")) or clean(p.get("Province")), "municipality": clean(p.get("Municipality"))}, feature["geometry"]))
    features, boundary_only = _features(builder, rows)
    boundary_only = max(boundary_only, int(data.get("coverage", {}).get("boundaryOnlyCount") or 0))
    return builder.finish(features, boundary_only)
