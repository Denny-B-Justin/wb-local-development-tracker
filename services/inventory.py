"""Strategy inventory: records, readiness rules (incl. the Serbian exception) and filters."""

from __future__ import annotations

import logging
import os
import re
from typing import Any

import pandas as pd

import constants
import countries

from . import databricks
from .text import clean, fold, slugify, volume_slug

log = logging.getLogger(__name__)

READINESS = ("AI-ready", "Found / Not Parsed", "Needs Translation", "Needs Validation", "Missing")
READINESS_KEYS = {
    "AI-ready": "aiReady",
    "Found / Not Parsed": "notParsed",
    "Needs Translation": "needsTranslation",
    "Needs Validation": "needsValidation",
    "Missing": "missing",
}
DOCUMENT_TYPES = ("strategy", "plan", "budget", "other")
TRANSLATION_STATUSES = ("not_required", "translated", "needs_translation", "partial", "unknown")

_TEXT_FIELDS = ("country_code", "lsg_id", "lsg_name", "lsg_name_local", "region_name", "document_type", "document_title",
                "source_status", "language", "translation_status", "parsing_status", "notes", "last_updated")
_DOC_KEYWORDS = {
    "strategy": ("strategy", "strategij", "strateg", "development plan", "ldp", "plan of development"),
    "budget": ("budget", "budzet", "buxhet", "financ"),
    "plan": ("plan", "programme", "program"),
}
_LANGUAGES = {"en": {"en", "eng", "english"}, "sr": {"sr", "srp", "srb", "serbian", "srpski", "lat", "cyr"}, "ne": {"ne", "np", "npl", "nep", "nepali"}}


def _record(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in _TEXT_FIELDS:
        value = clean(row.get(key), 400)
        if value:
            out[key] = value
    for key in ("publication_year", "valid_from_year", "valid_to_year"):
        try:
            out[key] = int(float(row[key])) if row.get(key) not in (None, "") else None
        except (TypeError, ValueError):
            out[key] = None
    url = clean(row.get("source_url"), 2000)
    out["source_url"] = url if url.lower().startswith(("https://", "http://")) else None
    out["ai_ready"] = str(row.get("ai_ready")).lower() in {"true", "1", "t", "yes"}
    out.setdefault("lsg_name", "")
    out.setdefault("lsg_id", slugify(out["lsg_name"]))
    out["last_updated"] = (out.get("last_updated") or "")[:10] or None
    return out


def _from_table() -> dict[str, list[dict[str, Any]]]:
    frame = databricks.read_optional(constants.UC_SHARED_TABLES["strategy_inventory"])
    if frame.empty:
        return {}
    frame.columns = [str(c).lower() for c in frame.columns]
    if "is_active" in frame:
        frame = frame[frame["is_active"].astype(str).str.lower().isin({"true", "1", "t", "yes"})]
    out: dict[str, list[dict[str, Any]]] = {}
    for row in frame.astype(object).where(pd.notna(frame), None).to_dict("records"):
        record = _record(row)
        out.setdefault(record.get("country_code", "").upper(), []).append(record)
    for records in out.values():
        records.sort(key=lambda r: (r.get("lsg_name", ""), r.get("document_type", "")))
    return out


def _classify(name: str) -> dict[str, Any]:
    lowered = name.lower()
    doc_type = next((k for k, words in _DOC_KEYWORDS.items() if any(w in lowered for w in words)), "other")
    years = [int(y) for y in re.findall(r"(?:19|20)\d{2}", name)]
    tokens = set(re.split(r"[^a-z0-9]+", lowered.rsplit(".", 1)[0]))
    language = next((lang for lang, marks in _LANGUAGES.items() if tokens & marks), "unknown")
    ext = lowered.rsplit(".", 1)[-1] if "." in lowered else ""
    parsed = ext in ("pdf", "docx", "doc", "txt", "md")
    return {"document_type": doc_type, "publication_year": max(years) if years else None, "language": language,
            "parsing_status": "parsed" if parsed else "needs_review", "ai_ready": parsed}


NATIONAL_FOLDERS = {"national", "country"}
TIMESTAMP_NAME = re.compile(r"^\d{8}-\d{6}$")


def _from_volume(country, units: list[dict[str, str]]) -> list[dict[str, Any]]:
    """One record per file under <volume>/<Country>/. The folders give the level, the area and the sector:
    <level>/<area>/[<sector>/<year>/]<file>, e.g. municipal/kraljevo/general/unknown/x.pdf, districts/kabwe/x.pdf;
    files under national/ (or directly under the country) are national documents."""
    subdir = country.source.documents_subdir or country.name
    files = databricks.list_volume(f"{constants.UC_DOCUMENTS_VOLUME.rstrip('/')}/{subdir}")
    lookup: dict[str, dict[str, str]] = {}
    for unit in units:
        for key in (slugify(unit["name"]), volume_slug(unit["name"])):
            lookup.setdefault(key, unit)
    records: list[dict[str, Any]] = []
    levels: dict[str, int] = {}
    unmatched: set[str] = set()
    for item in files:
        if item["name"].startswith("."):
            continue
        folders = item.get("folders") or []
        level = folders[0].lower() if folders else "national"
        levels[level] = levels.get(level, 0) + 1
        national = level in NATIONAL_FOLDERS or len(folders) < 2
        if national:
            lsg, region = country.name, None
        else:
            unit = lookup.get(folders[1].lower())
            if not unit:
                unmatched.add(folders[1])
            lsg, region = (unit["name"], unit["region"]) if unit else (folders[1].replace("-", " ").title(), None)
        stem = os.path.splitext(item["name"])[0]
        meta = _classify(item["name"])
        if TIMESTAMP_NAME.match(stem):
            meta["publication_year"] = None  # an upload timestamp, not the publication year
        year_folder = folders[3] if len(folders) > 3 else ""
        if meta["publication_year"] is None and re.fullmatch(r"(?:19|20)\d{2}", year_folder):
            meta["publication_year"] = int(year_folder)
        sector = folders[2] if len(folders) > 2 else None
        records.append({
            "country_code": country.iso3, "lsg_id": slugify(lsg), "lsg_name": clean(lsg, 160), "region_name": region,
            "document_title": clean(stem, 300), "source_url": None, "source_status": "found", "translation_status": "unknown",
            "notes": f"National document ({sector})" if national and sector else "National document" if national else None,
            "last_updated": None, "level": "national" if national else "local", "sector": sector, "volume_path": item["path"], **meta,
        })
    local = [r for r in records if r["level"] == "local"]
    log.info("%s strategy inventory: %d files (by folder: %s); %d national, %d local covering %d of %d %s",
             country.iso3, len(records), levels, len(records) - len(local), len(local), len({r["lsg_id"] for r in local}),
             len(units), "units" if units else "units (unit list unavailable; area names come from folder names)")
    if unmatched and units:
        log.warning("%s strategy inventory: %d area folders match no unit (shown under the folder name): %s",
                    country.iso3, len(unmatched), sorted(unmatched)[:15])
    return records


def load_all_from_databricks(units: dict[str, list[dict[str, str]]] | None = None) -> dict[str, list[dict[str, Any]]]:
    """``units``: per country, the local units as {"name", "region"}, used to name the areas found in the volume."""
    data = _from_table()
    for country in countries.REGISTRY:
        if country.features.strategy_inventory and not data.get(country.iso3):
            try:
                data[country.iso3] = _from_volume(country, (units or {}).get(country.iso3, []))
            except Exception as exc:  # noqa: BLE001
                log.warning("%s: strategy inventory volume listing FAILED (%s: %s)", country.iso3, type(exc).__name__, exc)
                data[country.iso3] = []
    log.info("Strategy inventory: %s", {k: len(v) for k, v in data.items()} or "no documents")
    return data


def _translation_block(r: dict[str, Any]) -> bool:
    return r.get("translation_status") in ("needs_translation", "partial")


def _serbian_exception(r: dict[str, Any]) -> bool:
    return r.get("country_code") == "SRB" and r.get("language") == "sr" and not _translation_block(r)


def _needs_translation(r: dict[str, Any]) -> bool:
    return False if _serbian_exception(r) else _translation_block(r)


def _needs_validation(r: dict[str, Any]) -> bool:
    return r.get("source_status") == "needs_validation" or r.get("parsing_status") in ("failed", "needs_review")


def _ai_ready(r: dict[str, Any]) -> bool:
    return (r.get("source_status") == "found" and r.get("parsing_status") == "parsed"
            and not _translation_block(r) and bool(r.get("ai_ready") or _serbian_exception(r)))


def readiness(r: dict[str, Any]) -> str:
    if r.get("source_status") in ("missing", "not_available"):
        return "Missing"
    if _needs_validation(r):
        return "Needs Validation"
    if _ai_ready(r):
        return "AI-ready"
    if _needs_translation(r):
        return "Needs Translation"
    return "Found / Not Parsed"


def _has_source(r: dict[str, Any]) -> bool:
    return r.get("source_status") in ("found", "needs_validation")


def _lsg_key(r: dict[str, Any]) -> str:
    return (r.get("lsg_id") or r.get("lsg_name") or "").strip().lower()


def summarize(records: list[dict[str, Any]], expected: int) -> dict[str, Any]:
    documents = [r for r in records if _has_source(r)]
    covered = {_lsg_key(r) for r in documents if r.get("level") != "national"}
    seen: set[str] = set()
    missing = []
    for r in records:
        if _has_source(r) or _lsg_key(r) in seen:
            continue
        seen.add(_lsg_key(r))
        missing.append({"lsg_id": r.get("lsg_id"), "lsg_name": r.get("lsg_name"), "region_name": r.get("region_name")})
    unlisted = max(0, expected - len(covered) - len(missing))
    years: dict[str, int] = {}
    for r in documents:
        key = str(r["publication_year"]) if r.get("publication_year") else "Unknown"
        years[key] = years.get(key, 0) + 1
    counts = {c: 0 for c in READINESS}
    for r in records:
        counts[readiness(r)] += 1
    counts["Missing"] = max(counts["Missing"], len(missing) + unlisted)
    dates = sorted(r["last_updated"] for r in records if r.get("last_updated"))
    return {
        "expected_lsgs": expected,
        "lsgs_with_any_document": len(covered),
        "coverage_rate": len(covered) / expected if expected else 0,
        "total_documents_found": len(documents),
        "ai_ready_documents": sum(1 for r in records if _ai_ready(r)),
        "needs_translation": sum(1 for r in records if _needs_translation(r)),
        "needs_validation": sum(1 for r in records if _needs_validation(r)),
        "missing_lsgs": missing,
        "unlisted_missing_lsg_count": unlisted,
        "publication_year_counts": sorted(({"year": y, "count": c} for y, c in years.items()), key=lambda e: (e["year"] == "Unknown", e["year"])),
        "unknown_year_count": years.get("Unknown", 0),
        "status_breakdown": [{"category": c, "count": counts[c]} for c in READINESS],
        "latest_last_updated": dates[-1] if dates else None,
    }


def filter_records(records: list[dict[str, Any]], query: str = "", year: str = "all", category: str = "all",
                   doc_type: str = "all", translation: str = "all") -> list[dict[str, Any]]:
    needle = fold(query)

    def matches(r: dict[str, Any]) -> bool:
        if needle and not any(needle in fold(r.get(k)) for k in ("lsg_name", "lsg_name_local", "region_name", "document_title", "notes")):
            return False
        record_year = str(r["publication_year"]) if r.get("publication_year") else "Unknown"
        return ((year == "all" or year == record_year)
                and (category == "all" or category == readiness(r))
                and (doc_type == "all" or doc_type == r.get("document_type"))
                and (translation == "all" or translation == r.get("translation_status")))

    return [r for r in records if matches(r)]
