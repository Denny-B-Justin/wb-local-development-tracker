"""Plan document sources (national and local/SNG plans) per country."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

import constants

from . import databricks
from .text import clean, plan_key

log = logging.getLogger(__name__)


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


def load_from_databricks(areas: dict[str, list[str]] | None = None) -> dict[str, Any]:
    """``areas`` maps ISO3 to the area names a local plan is matched against, for the coverage report."""
    table = constants.UC_SHARED_TABLES["plan_sources"]
    if not databricks.table_exists(table):
        log.error("Plan sources: %s does not exist, so every area shows \"No plan\" and planning briefs cannot run alignment, SWOT "
                  "or recommendations. Create it with scripts/uc_tables.sql (or set LDT_PLAN_SOURCES_TABLE) and add plan rows.",
                  databricks.table_name(table))
        frame = pd.DataFrame()
    else:
        frame = databricks.read_table(table)
    shaped = shape(frame)
    if frame.empty:
        log.warning("Plan sources: none loaded (%s is missing or empty)", table)
    else:
        log.info("Plan sources: %d rows, %d kept (active, with an http(s) link) -> %s", len(frame),
                 sum(len(v["national"]) + sum(len(d) for d in v["local"].values()) for v in shaped.values()),
                 {k: {"national": len(v["national"]), "local areas": len(v["local"])} for k, v in shaped.items()})
    report(shaped, areas or {})
    return shaped
