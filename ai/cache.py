"""AI stage cache: local disk first, Unity Catalog table (if present) for sharing across instances."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

import constants
from services import databricks

log = logging.getLogger(__name__)
_lock = threading.Lock()
AI_DIR = constants.CACHE_DIR / "ai"


def cache_key(scope: dict[str, Any], stage: str) -> str:
    material = {**{k: scope[k] for k in ("countryCode", "releaseKey", "unitKey", "scoreId")}, "stage": stage,
                "promptVersion": constants.AI_PROMPT_VERSION, "invalidationVersion": constants.AI_INVALIDATION_VERSION}
    return hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _path(key: str):
    return AI_DIR / f"{key}.json"


def load_local(scope: dict[str, Any], stage: str) -> dict[str, Any] | None:
    path = _path(cache_key(scope, stage))
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save(scope: dict[str, Any], stage: str, payload: dict[str, Any]) -> None:
    key = cache_key(scope, stage)
    try:
        AI_DIR.mkdir(parents=True, exist_ok=True)
        tmp = AI_DIR / f".{key}.{os.getpid()}.tmp"
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, _path(key))
    except OSError as exc:
        log.error("AI cache: cannot write %s stage result to %s (%s); the brief page will not show it", stage, AI_DIR, exc)
    table = constants.UC_SHARED_TABLES["ai_stage_cache"]
    if not databricks.configured() or not databricks.table_exists(table):
        return
    try:
        databricks.execute(
            "MERGE INTO IDENTIFIER(:table) AS t USING (SELECT :cache_key AS cache_key) AS s ON t.cache_key = s.cache_key "
            "WHEN MATCHED THEN UPDATE SET payload = :payload, updated_at = current_timestamp() "
            "WHEN NOT MATCHED THEN INSERT (cache_key, country_code, release_key, municipality_key, score_id, stage, prompt_version, payload, updated_at) "
            "VALUES (:cache_key, :country, :release, :unit, :score, :stage, :prompt, :payload, current_timestamp())",
            {"table": databricks.table_name(table), "cache_key": key, "payload": json.dumps(payload, ensure_ascii=False),
             "country": scope["countryCode"], "release": scope["releaseKey"], "unit": scope["unitKey"], "score": scope["scoreId"],
             "stage": stage, "prompt": constants.AI_PROMPT_VERSION},
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("AI cache write to Unity Catalog failed: %s", exc)


def pull_remote(scope: dict[str, Any], stages: list[str]) -> int:
    """Copy stage rows from the UC cache table into the local cache. Returns how many arrived."""
    table = constants.UC_SHARED_TABLES["ai_stage_cache"]
    if not databricks.configured() or not databricks.table_exists(table):
        return 0
    wanted = {cache_key(scope, stage): stage for stage in stages if load_local(scope, stage) is None}
    if not wanted:
        return 0
    markers = ", ".join(f":k{i}" for i in range(len(wanted)))
    params = {"table": databricks.table_name(table), **{f"k{i}": key for i, key in enumerate(wanted)}}
    frame = databricks.query(f"SELECT cache_key, payload FROM IDENTIFIER(:table) WHERE cache_key IN ({markers})", params)
    count = 0
    for row in frame.to_dict("records"):
        try:
            payload = json.loads(row["payload"])
        except (TypeError, ValueError):
            continue
        AI_DIR.mkdir(parents=True, exist_ok=True)
        _path(row["cache_key"]).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        count += 1
    return count


def record_run(scope: dict[str, Any], stage: str, status: str) -> None:
    line = json.dumps({"at": time.time(), "stage": stage, "status": status, "country": scope["countryCode"]})
    try:
        AI_DIR.mkdir(parents=True, exist_ok=True)
        with _lock, (AI_DIR / f"runs-{datetime.now(timezone.utc):%Y%m%d}.log").open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError as exc:
        log.warning("AI cache: cannot record the run in %s (%s); the daily run limit is not enforced", AI_DIR, exc)


def runs_last_24h() -> int:
    cutoff = time.time() - 86400
    total = 0
    for path in AI_DIR.glob("runs-*.log") if AI_DIR.is_dir() else []:
        if path.stat().st_mtime < cutoff:
            continue
        with path.open(encoding="utf-8") as handle:
            total += sum(1 for line in handle if json.loads(line).get("at", 0) > cutoff)
    return total
