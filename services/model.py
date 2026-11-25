"""Pure analytics over a country bundle: tree, scores, baselines, drivers, ranks, peers, trust."""

from __future__ import annotations

import math
import threading
from collections import OrderedDict
from functools import cached_property
from typing import Any

from countries import Country

from . import catalog, store
from .text import fold, plan_key, slugify

N_COMPONENTS = len(catalog.COMPONENTS)
POP, AREA = 4 + N_COMPONENTS, 5 + N_COMPONENTS
_EMPTY_PLANS: dict[str, Any] = {"local": {}, "national": []}


def _avg(values: list[float | None]) -> float | None:
    finite = [v for v in values if v is not None]
    return sum(finite) / len(finite) if finite else None


def _round2(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


class CountryModel:
    def __init__(self, country: Country, bundle: dict[str, Any]):
        self.country = country
        self.bundle = bundle
        self.version = bundle.get("builtAt", "")
        self._cache: dict[tuple, Any] = {}
        self._lock = threading.Lock()

    def _memo(self, key: tuple, build):
        with self._lock:
            if key in self._cache:
                return self._cache[key]
        value = build()
        with self._lock:
            self._cache[key] = value
        return value

    @cached_property
    def years(self) -> list[int]:
        return [int(y) for y in self.bundle.get("years", [])] or list(self.country.release.years)

    @cached_property
    def default_year(self) -> int:
        preferred = self.country.release.default_year
        return preferred if preferred in self.years else max(self.years)

    @cached_property
    def mapped(self) -> set[str]:
        return set(self.bundle.get("mapped", []))

    @cached_property
    def units(self) -> list[dict[str, Any]]:
        out = []
        for unit in self.bundle.get("units", []):
            names = unit["names"]
            areas = {level.key: {"slug": slugify(names[level.column]), "name": names[level.column]} for level in self.country.filter_levels}
            out.append({"id": unit["id"], "key": unit["key"], "name": names[self.country.local_level.column], "names": names, "areas": areas})
        return sorted(out, key=lambda u: fold(u["name"]))

    @cached_property
    def unit_index(self) -> dict[str, dict[str, Any]]:
        return {u["id"]: u for u in self.units}

    @cached_property
    def tree(self) -> list[dict[str, Any]]:
        levels = []
        filter_levels = self.country.filter_levels
        for index, level in enumerate(filter_levels):
            parent = filter_levels[index - 1] if index else None
            nodes: dict[str, dict[str, Any]] = {}
            for unit in self.units:
                area = unit["areas"][level.key]
                parent_slug = unit["areas"][parent.key]["slug"] if parent else None
                key = f"{parent_slug or ''}/{area['slug']}"
                if key in nodes:
                    nodes[key]["unitCount"] += 1
                else:
                    nodes[key] = {"slug": area["slug"], "name": area["name"], "parentSlug": parent_slug, "unitCount": 1}
            levels.append({"level": level, "nodes": sorted(nodes.values(), key=lambda n: fold(n["name"]))})
        return levels

    def scores(self, year: int) -> dict[str, list[float | None]]:
        return self.bundle.get("scores", {}).get(str(year), {})

    def unit_scores(self, year: int) -> list[dict[str, Any]]:
        def build():
            table = self.scores(year)
            rows = []
            for unit in self.units:
                values = table.get(unit["id"])
                row = {**unit, "composite": None, "prosperity": None, "infrastructure": None, "livability": None,
                       "components": [None] * N_COMPONENTS, "population": None, "areaKm2": None, "scored": False}
                if values:
                    row.update(composite=values[0], prosperity=values[1], infrastructure=values[2], livability=values[3],
                               components=list(values[4:4 + N_COMPONENTS]), population=values[POP], areaKm2=values[AREA])
                    row["scored"] = any(v is not None for v in values[:4])
                rows.append(row)
            return rows
        return self._memo(("unit_scores", year), build)

    @property
    def plan_sources(self) -> dict[str, Any]:
        return store.plan_sources().get(self.country.iso3) or _EMPTY_PLANS

    def rows(self, year: int) -> list[dict[str, Any]]:
        plan_sources = self.plan_sources

        def build():
            rows = self.unit_scores(year)
            ranks = rank_by_composite(rows)
            local = plan_sources.get("local", {})
            out = []
            for row in rows:
                docs = local.get(self.plan_key(row)) or []
                out.append({**row, "rank": ranks.get(row["id"]), "plan": {"title": docs[0]["title"], "link": docs[0]["link"]} if docs else None})
            return out
        return self._memo(("rows", year, id(plan_sources)), build)

    def row(self, year: int, unit_id: str) -> dict[str, Any] | None:
        return next((r for r in self.rows(year) if r["id"] == unit_id), None)

    def plan_key(self, unit: dict[str, Any]) -> str:
        if self.country.plan_source_level == "top":
            return plan_key(unit["areas"][self.country.filter_levels[0].key]["name"])
        return plan_key(unit["name"])

    def baseline(self, year: int, filters: dict[str, str | None], area: dict[str, Any] | None) -> dict[str, Any]:
        key = ("baseline", year, tuple(sorted((k, v) for k, v in filters.items() if v)) if area else ())

        def build():
            rows = [r for r in self.unit_scores(year) if r["scored"] and (not area or in_context(r, filters))]
            return {
                "scope": self.country.filter_levels[area["levelIndex"]].key if area else "national",
                "areaName": area["name"] if area else None,
                "unitCount": len(rows),
                "scores": {
                    "composite": _avg([r["composite"] for r in rows]),
                    **{p: _avg([r[p] for r in rows]) for p in catalog.PILLARS},
                    "components": {c.id: _avg([r["components"][i] for r in rows]) for i, c in enumerate(catalog.COMPONENTS)},
                },
            }
        return self._memo(key, build)

    def summary(self, unit_id: str, year: int, filters: dict[str, str | None], area: dict[str, Any] | None) -> dict[str, Any] | None:
        row = next((r for r in self.unit_scores(year) if r["id"] == unit_id), None)
        if not row or not row["scored"]:
            return None
        baseline = self.baseline(year, filters, area)
        drivers = []
        for i, component in enumerate(catalog.COMPONENTS):
            score = row["components"][i]
            base = baseline["scores"]["components"].get(component.id)
            drivers.append({"id": component.id, "label": component.label, "pillar": component.pillar, "score": score,
                            "driver": None if score is None or base is None else round((score - base) * 10) / 10})
        areas = [{"name": row["areas"][level.key]["name"], "levelKey": level.key} for level in reversed(self.country.filter_levels)]
        return {"id": row["id"], "name": row["name"], "areas": areas, "year": year, "releaseKey": self.country.release_key(year),
                "scores": score_set(row), "baseline": baseline, "drivers": drivers}

    def context_summary(self, year: int, filters: dict[str, str | None]) -> dict[str, Any]:
        rows = [r for r in self.unit_scores(year) if r["scored"] and in_context(r, filters)]
        pops = [r["population"] for r in rows if r["population"] is not None]
        areas = [r["areaKm2"] for r in rows if r["areaKm2"] is not None]
        return {"unitCount": len(rows), "population": sum(pops) if pops else None, "landAreaKm2": sum(areas) if areas else None,
                "meanComposite": _round2(_avg([r["composite"] for r in rows]))}

    def coverage(self) -> list[dict[str, Any]]:
        return [{"year": y, "releaseKey": self.country.release_key(y), "units": sum(1 for r in self.unit_scores(y) if r["scored"])} for y in self.years]

    def boundary_gaps(self, year: int) -> dict[str, Any]:
        unmapped = [r for r in self.unit_scores(year) if r["scored"] and r["id"] not in self.mapped]
        return {
            "unmapped": [{"id": r["id"], "name": r["name"], "areaNames": [r["areas"][l.key]["name"] for l in self.country.filter_levels][::-1]} for r in unmapped],
            "boundaryOnly": int(self.bundle.get("boundaryOnly") or 0),
        }

    def trust(self, year: int) -> dict[str, Any]:
        plan_sources = self.plan_sources
        scored = [r for r in self.unit_scores(year) if r["scored"]]
        mapped = sum(1 for r in scored if r["id"] in self.mapped)
        analytics_only = len(scored) - mapped
        boundary_only = int(self.bundle.get("boundaryOnly") or 0)
        sourced_names = set(plan_sources.get("local", {}).keys())
        if self.country.plan_source_level == "top":
            top = self.country.filter_levels[0].key
            names = list(dict.fromkeys(r["areas"][top]["name"] for r in scored))
        else:
            names = [r["name"] for r in scored]
        total = len(names)
        sourced = sum(1 for n in names if plan_key(n) in sourced_names)
        plan_status = "blocked" if not total or not sourced else ("ready" if sourced == total else "partial")
        boundary_status = "ready" if analytics_only == 0 and boundary_only == 0 else ("partial" if mapped else "blocked")
        ai_status = plan_status if self.country.features.ai and plan_status != "blocked" else "blocked"
        gaps = analytics_only + boundary_only
        return {
            "releaseKey": self.country.release_key(year),
            "pilVersion": self.country.release.pil_version,
            "boundaryGapCount": gaps,
            "items": [
                {"key": "coverage", "status": "ready" if scored else "blocked", "facts": {"units": len(scored), "year": year, "releaseKey": self.country.release_key(year)}},
                {"key": "boundaries", "status": boundary_status, "facts": {"gaps": gaps, "mapped": mapped}},
                {"key": "planSources", "status": plan_status, "facts": {"sourced": sourced, "total": total, "percent": round(sourced / total * 100) if total else 0, "planLevel": self.country.plan_source_level}},
                {"key": "aiReadiness", "status": ai_status, "facts": {}},
            ],
        }

    def trend(self, unit_id: str, filters: dict[str, str | None], area: dict[str, Any] | None) -> list[dict[str, Any]]:
        out = []
        for year in self.years:
            row = next((r for r in self.unit_scores(year) if r["id"] == unit_id and r["scored"]), None)
            out.append({
                "year": year,
                "unit": score_set(row) if row else None,
                "area": self.baseline(year, filters, area)["scores"] if area else None,
                "national": self.baseline(year, {}, None)["scores"],
            })
        return out

    def peers(self, year: int, unit_id: str, count: int = 5) -> list[dict[str, Any]]:
        rows = self.rows(year)
        me = next((r for r in rows if r["id"] == unit_id), None)
        if not me or not complete(me):
            return []
        scored = [
            {"unit": r, "distance": math.dist([r[p] for p in catalog.PILLARS], [me[p] for p in catalog.PILLARS])}
            for r in rows if r["id"] != unit_id and complete(r)
        ]
        return sorted(scored, key=lambda p: (p["distance"], p["unit"]["id"]))[:count]


def complete(row: dict[str, Any]) -> bool:
    return all(row[p] is not None for p in catalog.PILLARS)


def score_set(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "composite": row["composite"],
        **{p: row[p] for p in catalog.PILLARS},
        "components": {c.id: row["components"][i] for i, c in enumerate(catalog.COMPONENTS)},
    }


def in_context(unit: dict[str, Any], filters: dict[str, str | None]) -> bool:
    return all(not slug or unit["areas"].get(key, {}).get("slug") == slug for key, slug in filters.items())


def rank_by_composite(rows: list[dict[str, Any]]) -> dict[str, int]:
    scored = sorted(((r["id"], round(r["composite"] * 100)) for r in rows if r["composite"] is not None), key=lambda x: -x[1])
    ranks: dict[str, int] = {}
    for index, (uid, value) in enumerate(scored):
        if index and scored[index - 1][1] == value:
            ranks[uid] = ranks[scored[index - 1][0]]
        else:
            ranks[uid] = index + 1
    return ranks


def metric_value(row: dict[str, Any], metric: str) -> float | None:
    if metric == "composite" or metric in catalog.PILLARS:
        return row.get(metric)
    index = catalog.COMPONENT_INDEX.get(metric)
    return None if index is None else row["components"][index]


def score_set_value(scores: dict[str, Any] | None, metric: str) -> float | None:
    if not scores:
        return None
    if metric == "composite" or metric in catalog.PILLARS:
        return scores.get(metric)
    return scores.get("components", {}).get(metric)


_models: OrderedDict[str, CountryModel] = OrderedDict()
_models_lock = threading.Lock()


def get(country: Country) -> CountryModel | None:
    bundle = store.bundle(country.iso3)
    if not bundle:
        return None
    key = f"{country.iso3}:{bundle.get('builtAt')}:{id(bundle)}"
    with _models_lock:
        model = _models.get(key)
        if model is None:
            for stale in [k for k in _models if k.startswith(f"{country.iso3}:")]:
                _models.pop(stale)
            model = _models[key] = CountryModel(country, bundle)
        return model


def clear() -> None:
    with _models_lock:
        _models.clear()


store.on_refresh(clear)
