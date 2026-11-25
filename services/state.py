"""URL state: ?page=<name> routing, the workspace context and link building."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

import constants
import countries
from countries import Country

from . import model as model_module
from . import security
from .i18n import Translator, normalize_locale, translator

SITE_PAGES = ("home", "why-ldt", "methodology", "resources", "release-notes", "about")
WORKSPACE_PAGES = ("map", "compare", "municipalities", "profile", "brief", "data", "strategy-inventory")
PARAM_ORDER = ("page", "country", "unit", "year")


@dataclass
class Request:
    page: str
    params: dict[str, str]
    lang: str
    t: Translator
    country: Country | None = None
    model: Any = None
    year: int | None = None
    filters: dict[str, str | None] = field(default_factory=dict)
    area: dict[str, Any] | None = None
    compare: list[str] = field(default_factory=list)
    preview: str | None = None

    def href(self, page: str, keep_context: bool = True, **params: Any) -> str:
        query: dict[str, Any] = {"page": page}
        if self.country and page in WORKSPACE_PAGES:
            query["country"] = self.country.slug
            if keep_context:
                query.update(self.context_params(include_compare=True))
        query.update({k: v for k, v in params.items() if v not in (None, "", [], False)})
        if self.lang != constants.DEFAULT_LOCALE:
            query["lang"] = self.lang
        return build(query)

    def context_params(self, include_compare: bool = False) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.country and self.year is not None and self.model and self.year != self.model.default_year:
            out["year"] = self.year
        for key, value in self.filters.items():
            if value:
                out[key] = value
        if include_compare and self.compare:
            out["compare"] = ",".join(self.compare)
        return out

    def with_params(self, **changes: Any) -> str:
        """The current page's URL with some params changed (None removes one)."""
        query = {"page": self.page, **self.params}
        query.pop("lang", None)
        for key, value in changes.items():
            if value in (None, "", []):
                query.pop(key, None)
            else:
                query[key] = value
        if self.lang != constants.DEFAULT_LOCALE:
            query["lang"] = self.lang
        return build(query)

    def site_href(self, page: str) -> str:
        return build({"page": page, **({"lang": self.lang} if self.lang != constants.DEFAULT_LOCALE else {})})

    def lang_href(self, lang: str) -> str:
        query = {"page": self.page, **self.params}
        query["lang"] = lang
        if lang == constants.DEFAULT_LOCALE:
            query.pop("lang")
        return build(query)

    def toggle_compare(self, unit_id: str) -> str:
        ids = [i for i in self.compare if i != unit_id] if unit_id in self.compare else [*self.compare, unit_id][: constants.COMPARE_MAX]
        return self.with_params(compare=",".join(ids) or None)


def build(query: dict[str, Any]) -> str:
    ordered = {k: query[k] for k in PARAM_ORDER if k in query}
    ordered.update({k: v for k, v in query.items() if k not in ordered})
    return "?" + urlencode({k: str(v) for k, v in ordered.items()}, safe=",")


def parse(search: str | None) -> Request:
    level_keys = tuple({level.key for c in countries.REGISTRY for level in c.levels})
    params = security.parse_query(search, level_keys)
    lang = normalize_locale(params.get("lang"))
    page = params.pop("page", "")
    params.pop("lang", None)
    preview = _preview_cookie()
    country = countries.find(security.slug(params.get("country")))
    if country and not countries.is_visible(country, preview):
        country = None
    if not page:
        page = "map" if country else "home"
    if page == "overview":
        page = "map"
    req = Request(page=page, params=params, lang=lang, t=translator(lang), preview=preview)
    if page in WORKSPACE_PAGES:
        if not country:
            req.page = "not-found"
            return req
        req.country = country
        req.model = model_module.get(country)
        apply_context(req)
    elif page not in SITE_PAGES:
        req.page = "not-found"
    return req


def _preview_cookie() -> str | None:
    from flask import has_request_context, request

    return request.cookies.get(PREVIEW_COOKIE) if has_request_context() else None


PREVIEW_COOKIE = "ldt_preview"


def apply_context(req: Request) -> None:
    country, model = req.country, req.model
    years = model.years if model else list(country.release.years)
    default = model.default_year if model else country.release.default_year
    try:
        year = int(req.params.get("year", ""))
    except ValueError:
        year = default
    req.year = year if year in years else default
    req.filters = {level.key: None for level in country.filter_levels}
    req.compare = security.compare_ids(req.params.get("compare"))
    if not model:
        return
    parent = None
    for index, level in enumerate(country.filter_levels):
        value = security.slug(req.params.get(level.key))
        if not value:
            break
        node = next((n for n in model.tree[index]["nodes"] if n["slug"] == value and (index == 0 or n["parentSlug"] == parent)), None)
        if not node:
            break
        req.filters[level.key] = value
        req.area = {"levelIndex": index, "name": node["name"], "slug": value, "unitCount": node["unitCount"]}
        parent = value
    if req.compare:
        known = model.unit_index
        req.compare = [i for i in req.compare if i in known]


def localized_country(country: Country, t: Translator) -> dict[str, Any]:
    levels = []
    for level in country.levels:
        key = f"data.levels.{level.singular.lower()}"
        levels.append({"key": level.key, "column": level.column,
                       "singular": t.t_or(f"{key}.one", level.singular), "plural": t.t_or(f"{key}.other", level.plural)})
    return {
        "name": t.t_or(f"data.countries.{country.iso3}", country.name),
        "levels": levels,
        "local": levels[-1],
        "filters": levels[:-1],
        "ai_message": t.t_or(f"data.aiMessage.{country.iso3}", country.ai_message),
        "landing_meta": t.t_or(f"data.landingMeta.{country.iso3}", country.landing_meta),
    }


def units_label(req: Request, count: int) -> str:
    local = localized_country(req.country, req.t)["local"]
    return req.t.tp("units.count", count, one=local["singular"].lower(), other=local["plural"].lower())


def area_label(req: Request) -> str:
    names = localized_country(req.country, req.t)
    if not req.area:
        return names["name"]
    level = names["filters"][req.area["levelIndex"]]
    return req.t.t("labels.area", name=req.area["name"], level=level["singular"])


def context_line(req: Request, unit_count: int) -> str:
    return f"{area_label(req)} · {units_label(req, unit_count)} · {req.year}"


def baseline_label(t: Translator, baseline: dict[str, Any]) -> str:
    return t.t("baseline.area", area=baseline["areaName"]) if baseline.get("areaName") else t.t("baseline.national")


def area_line(req: Request, areas: dict[str, Any]) -> str:
    levels = localized_country(req.country, req.t)["filters"]
    parts = [req.t.t("labels.area", name=areas[l["key"]]["name"], level=l["singular"]) for l in reversed(levels) if areas.get(l["key"])]
    return " · ".join(parts)
