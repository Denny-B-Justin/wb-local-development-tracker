"""Country registry: one module per country. Order is display order."""

from __future__ import annotations

import hmac

import constants

from . import gin, npl, srb, vnm, zmb
from .schema import Country, Level

REGISTRY: tuple[Country, ...] = tuple(module.COUNTRY.validate() for module in (npl, srb, zmb, vnm, gin))

_slugs = [c.slug for c in REGISTRY]
_codes = [c.iso3 for c in REGISTRY]
if len(set(_slugs)) != len(_slugs) or len(set(_codes)) != len(_codes):
    raise ValueError("Country registry has duplicate slugs or ISO3 codes")

BY_SLUG = {c.slug: c for c in REGISTRY}
BY_ISO3 = {c.iso3: c for c in REGISTRY}


def preview_ok(token: str | None) -> bool:
    expected = constants.PREVIEW_TOKEN
    return bool(expected and token and hmac.compare_digest(expected, token))


def is_visible(country: Country, preview_token: str | None = None) -> bool:
    if country.status == "published":
        return True
    if country.status == "draft":
        return False
    return preview_ok(preview_token)


def visible(preview_token: str | None = None) -> list[Country]:
    return [c for c in REGISTRY if is_visible(c, preview_token)]


def published() -> list[Country]:
    return [c for c in REGISTRY if c.status == "published"]


def find(slug: str | None) -> Country | None:
    return BY_SLUG.get((slug or "").strip().lower())


__all__ = ["Country", "Level", "REGISTRY", "BY_SLUG", "BY_ISO3", "find", "visible", "published", "is_visible", "preview_ok"]
