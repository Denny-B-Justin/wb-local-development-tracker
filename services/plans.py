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


def load_from_databricks() -> dict[str, Any]:
    frame = databricks.read_optional(constants.UC_SHARED_TABLES["plan_sources"])
    shaped = shape(frame)
    log.info("Plan sources: %s", {k: len(v["local"]) for k, v in shaped.items()})
    return shaped
