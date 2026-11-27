"""Plan document sources (national and local/SNG plans) per country."""

from __future__ import annotations

import hashlib
import logging
import os
import re
from typing import Any

import pandas as pd

import constants
import countries

from . import databricks
from .inventory import NATIONAL_FOLDERS, TIMESTAMP_NAME
from .text import clean, plan_key, slugify, volume_slug

log = logging.getLogger(__name__)
READABLE_EXTENSIONS = {"pdf", "docx", "txt", "md", "html", "htm"}


def _safe_link(value: Any) -> str:
    link = clean(value, 2000)
    return link if link.lower().startswith(("https://", "http://")) else ""


def shape(frame: pd.DataFrame) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if frame.empty:
        return out
    frame = frame.copy()
    frame.columns = [str(c).lower() for c in frame.columns]
    if "is_active" in frame:
        frame = frame[frame["is_active"].astype(str).str.lower().isin({"true", "1", "t", "yes"})]
    if "priority" in frame:
        frame = frame.sort_values(["priority", "title"], na_position="last")
    for row in frame.astype(object).where(pd.notna(frame), None).to_dict("records"):
        iso3 = clean(row.get("country_code"), 3).upper()
        link = _safe_link(row.get("link"))
        if not iso3 or not link:
            continue
        doc = {
            "title": clean(row.get("title"), 300) or link,
            "link": link,
            "type": clean(row.get("document_type"), 80) or None,
            "level": "national" if clean(row.get("plan_level"), 40).lower() == "national" else "local",
            "area": clean(row.get("province"), 160) or None,
            "notes": clean(row.get("notes"), 500) or None,
            "scoreTheme": clean(row.get("score_theme"), 40) or None,
        }
        bucket = out.setdefault(iso3, {"local": {}, "national": []})
        if doc["level"] == "national":
            bucket["national"].append(doc)
        elif doc["area"]:
            bucket["local"].setdefault(plan_key(doc["area"]), []).append(doc)
    return out


def report(shaped: dict[str, Any], areas: dict[str, list[str]]) -> None:
    """Per country: which areas have a plan, which do not, and plan rows filed under a name no area has."""
    for iso3, names in areas.items():
        bucket = shaped.get(iso3) or {"local": {}, "national": []}
        keys = {plan_key(n): n for n in names}
        covered = sorted(n for k, n in keys.items() if k in bucket["local"])
        missing = sorted(n for k, n in keys.items() if k not in bucket["local"])
        stray = sorted(k for k in bucket["local"] if k not in keys)
        (log.info if not missing else log.warning)(
            "%s plan sources: %d national, %d of %d areas have a local plan%s", iso3, len(bucket["national"]), len(covered), len(keys),
            f"; without a plan: {missing[:12]}{' ...' if len(missing) > 12 else ''}" if missing else "")
        if stray:
            log.warning("%s plan sources: %d rows are filed under names no area has (check spelling): %s; area names are %s",
                        iso3, len(stray), stray[:12], sorted(keys)[:12])


def document_id(path: str) -> str:
    return hashlib.sha1(path.encode("utf-8")).hexdigest()[:20]


def _volume_title(stem: str, folder: str | None, area: str) -> str:
    if TIMESTAMP_NAME.match(stem):
        return f"{area} plan document ({stem[:4]}-{stem[4:6]}-{stem[6:8]})"
    if folder and stem.lower().startswith(folder.lower()):
        stem = area + stem[len(folder):]
    title = re.sub(r"[-_]+", " ", stem).strip()
    return title[:1].upper() + title[1:]


def _volume_rank(doc: dict[str, Any]) -> tuple:
    """The brief reads the first document of an area: readable formats first, then files named as plans."""
    name = doc["volumePath"].rsplit("/", 1)[-1].lower()
    return (name.rsplit(".", 1)[-1] not in READABLE_EXTENSIONS, "plan" not in name, name)


def from_volume(country, areas: list[str]) -> dict[str, Any]:
    """Plans stored in the documents volume under <Country>/<level>/<area>/.../<file>; files under national/ are national plans.
    Area folders are matched to ``areas`` (the names a local plan is filed under)."""
    root = f"{constants.UC_DOCUMENTS_VOLUME.rstrip('/')}/{country.source.documents_subdir or country.name}"
    lookup: dict[str, str] = {}
    for name in areas:
        lookup.setdefault(slugify(name), name)
        lookup.setdefault(volume_slug(name), name)
    bucket: dict[str, Any] = {"local": {}, "national": []}
    unmatched: set[str] = set()
    for item in databricks.list_volume(root):
        if item["name"].startswith("."):
            continue
        folders = item.get("folders") or []
        stem = os.path.splitext(item["name"])[0]
        doc = {"id": document_id(item["path"]), "volumePath": item["path"], "type": folders[2] if len(folders) > 2 else None,
               "notes": None, "scoreTheme": None}
        if not folders or folders[0].lower() in NATIONAL_FOLDERS or len(folders) < 2:
            bucket["national"].append({**doc, "title": _volume_title(stem, None, country.name), "level": "national", "area": None})
            continue
        area = lookup.get(folders[1].lower())
        if not area:
            unmatched.add(folders[1])
            continue
        bucket["local"].setdefault(plan_key(area), []).append({**doc, "title": _volume_title(stem, folders[1], area), "level": "local", "area": area})
    bucket["national"].sort(key=_volume_rank)
    for docs in bucket["local"].values():
        docs.sort(key=_volume_rank)
    for doc in [*bucket["national"], *(d for docs in bucket["local"].values() for d in docs)]:
        doc["link"] = f"api/document/{doc['id']}"
    log.info("%s plan sources from volume %s: %d national documents, %d areas with local documents (%d documents)", country.iso3, root,
             len(bucket["national"]), len(bucket["local"]), sum(len(d) for d in bucket["local"].values()))
    if unmatched:
        log.warning("%s plan sources from volume: %d area folders match no %s name and were skipped: %s", country.iso3, len(unmatched),
                    country.plan_source_level, sorted(unmatched)[:15])
    return bucket


def _merge(shaped: dict[str, Any], iso3: str, extra: dict[str, Any]) -> None:
    """Table rows first (they are curated), then volume documents."""
    bucket = shaped.setdefault(iso3, {"local": {}, "national": []})
    bucket["national"] += extra["national"]
    for key, docs in extra["local"].items():
        bucket["local"].setdefault(key, []).extend(docs)


def load_from_databricks(areas: dict[str, list[str]] | None = None) -> dict[str, Any]:
    """``areas`` maps ISO3 to the area names a local plan is matched against, for the coverage report."""
    table = constants.UC_SHARED_TABLES["plan_sources"]
    if not databricks.table_exists(table):
        log.warning("Plan sources: table %s does not exist; using the documents volume only (%s)", databricks.table_name(table),
                    constants.UC_DOCUMENTS_VOLUME)
        frame = pd.DataFrame()
    else:
        frame = databricks.read_table(table)
    shaped = shape(frame)
    if frame.empty:
        log.info("Plan sources: no rows from %s", table)
    else:
        log.info("Plan sources: %d rows, %d kept (active, with an http(s) link) -> %s", len(frame),
                 sum(len(v["national"]) + sum(len(d) for d in v["local"].values()) for v in shaped.values()),
                 {k: {"national": len(v["national"]), "local areas": len(v["local"])} for k, v in shaped.items()})
    for country in countries.REGISTRY:
        if not country.features.plan_sources or country.iso3 not in (areas or {}):
            continue
        try:
            _merge(shaped, country.iso3, from_volume(country, areas[country.iso3]))
        except Exception as exc:  # noqa: BLE001
            log.warning("%s plan sources: volume listing FAILED (%s: %s)", country.iso3, type(exc).__name__, exc)
    report(shaped, areas or {})
    return shaped
