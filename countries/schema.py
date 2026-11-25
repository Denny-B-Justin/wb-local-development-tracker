from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

import constants

Status = Literal["draft", "preview", "published"]
Column = Literal["province", "district", "municipality"]

_SLUG = re.compile(r"^[a-z0-9-]+$")
_RESERVED_KEYS = {"year", "type", "compare", "selected", "view", "tab", "preview", "page", "country", "lang", "unit"}


@dataclass(frozen=True)
class Level:
    key: str
    column: Column
    singular: str
    plural: str


@dataclass(frozen=True)
class Plan:
    title: str
    url: str


@dataclass(frozen=True)
class Release:
    prefix: str
    version: str
    pil_version: str
    years: tuple[int, ...]
    default_year: int


@dataclass(frozen=True)
class Features:
    ai: bool = True
    plan_sources: bool = True
    province_plan_sources: bool = False
    strategy_inventory: bool = False
    translation_check: bool = False


@dataclass(frozen=True)
class Source:
    """How this country's Unity Catalog tables are shaped."""

    hierarchy: dict[str, str]
    boundary_candidates: dict[str, tuple[str, ...]]
    year_candidates: tuple[str, ...] = ("Year", "year", "release_year", "data_year")
    geometry_candidates: tuple[str, ...] = ("geometry_wkt", "geometry_wkb", "geometry", "geom", "wkt", "geojson", "shape")
    column_aliases: dict[str, tuple[str, ...]] = field(default_factory=dict)
    crs: str = "EPSG:4326"
    simplify_tolerance: float = 0.0008
    documents_subdir: str | None = None


@dataclass(frozen=True)
class Country:
    iso3: str
    slug: str
    name: str
    status: Status
    release: Release
    levels: tuple[Level, ...]
    plan_source_level: Literal["top", "local"]
    ai_message: str
    landing_meta: str
    features: Features
    source: Source
    national_plan: Plan | None = None
    public_totals: dict[str, float] = field(default_factory=dict)
    map_max_zoom: float = 11

    @property
    def tables(self) -> dict[str, str]:
        return constants.UC_COUNTRY_TABLES[self.iso3]

    @property
    def local_level(self) -> Level:
        return self.levels[-1]

    @property
    def filter_levels(self) -> tuple[Level, ...]:
        return self.levels[:-1]

    def release_key(self, year: int) -> str:
        return f"{self.release.prefix}-{year}-{self.release.version}"

    def validate(self) -> "Country":
        problems: list[str] = []
        if not re.fullmatch(r"[A-Z]{3}", self.iso3):
            problems.append("iso3 must be three capital letters")
        if not _SLUG.fullmatch(self.slug):
            problems.append("slug must be lowercase letters, digits and dashes")
        if self.status not in ("draft", "preview", "published"):
            problems.append("status must be draft, preview or published")
        if not 2 <= len(self.levels) <= 3:
            problems.append("a country has two or three admin levels")
        if self.levels and self.levels[-1].column != "municipality":
            problems.append("the last level (local unit) must use the municipality column")
        keys = [level.key for level in self.levels]
        if len(set(keys)) != len(keys):
            problems.append("level keys must be unique")
        for key in keys:
            if key in _RESERVED_KEYS or not _SLUG.fullmatch(key):
                problems.append(f'level key "{key}" is reserved or invalid')
        if self.release.default_year not in self.release.years:
            problems.append("release.default_year must be one of release.years")
        if self.iso3 not in constants.UC_COUNTRY_TABLES:
            problems.append("add the country's tables to constants.UC_COUNTRY_TABLES")
        for column in ("province", "district", "municipality"):
            if column not in self.source.hierarchy:
                problems.append(f'source.hierarchy needs a "{column}" column')
        if self.national_plan and not self.national_plan.url.startswith("https://") and not self.national_plan.url.startswith("http://"):
            problems.append("national_plan.url must be an http(s) URL")
        if problems:
            raise ValueError(f"Invalid country registry entry {self.iso3}: " + "; ".join(problems))
        return self
