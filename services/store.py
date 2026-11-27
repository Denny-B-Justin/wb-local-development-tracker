"""Request-safe data artifacts.

Databricks is read only by ``warm()``, off the request path. Pages read gzipped
JSON artifacts from the writable cache, then the shipped snapshot. A stale or
missing artifact schedules a background warm; requests never wait on it.
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable

import constants
import countries

from . import assemble, databricks, inventory, plans

log = logging.getLogger(__name__)

_memo: dict[str, tuple[float, Any]] = {}
_memo_lock = threading.RLock()
_warm_lock = threading.Lock()
_hooks: list[Callable[[], None]] = []
_status: dict[str, Any] = {"lastWarm": None, "lastError": None, "failed": {}, "running": False}
_last_attempt = 0.0
_reported_missing: set[str] = set()


def on_refresh(hook: Callable[[], None]) -> None:
    _hooks.append(hook)


def _name(kind: str, iso3: str | None = None) -> str:
    return f"{kind}_{iso3}.json.gz" if iso3 else f"{kind}.json.gz"


def _candidates(name: str) -> list[Path]:
    return [constants.CACHE_DIR / name, constants.SNAPSHOT_DIR / name]


def _write(name: str, payload: Any, directory: Path | None = None) -> None:
    directory = directory or constants.CACHE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    data = gzip.compress(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"), compresslevel=6)
    tmp = directory / f".{name}.{os.getpid()}.{threading.get_ident()}.tmp"
    tmp.write_bytes(data)
    os.replace(tmp, directory / name)


def _read(name: str) -> tuple[Any, float] | None:
    for path in _candidates(name):
        if path.is_file():
            try:
                return json.loads(gzip.decompress(path.read_bytes())), path.stat().st_mtime
            except (OSError, ValueError) as exc:
                log.warning("Unreadable artifact %s: %s", path, exc)
    return None


def _raw(name: str) -> tuple[bytes, float] | None:
    for path in _candidates(name):
        if path.is_file():
            return path.read_bytes(), path.stat().st_mtime
    return None


def _cached(name: str) -> Any:
    with _memo_lock:
        hit = _memo.get(name)
    current = None
    for path in _candidates(name):
        if path.is_file():
            current = path.stat().st_mtime
            break
    # Exact match: a deleted cache file falls back to an older snapshot, which must not keep the stale memo.
    if hit and current is not None and hit[0] == current:
        return hit[1]
    loaded = _read(name)
    if loaded is None:
        if name not in _reported_missing:
            _reported_missing.add(name)
            log.warning("Artifact %s not found in %s or %s", name, constants.CACHE_DIR, constants.SNAPSHOT_DIR)
        schedule_warm(reason=f"{name} is missing")
        return None
    payload, mtime = loaded
    _reported_missing.discard(name)
    with _memo_lock:
        _memo[name] = (mtime, payload)
    age = time.time() - mtime
    origin = "cache" if (constants.CACHE_DIR / name).is_file() else "snapshot"
    log.info("Loaded %s from %s (built %.1fh ago)", name, origin, age / 3600)
    if age > constants.DATA_MAX_AGE_SECONDS:
        schedule_warm(reason=f"{name} is {age / 3600:.1f}h old (max {constants.DATA_MAX_AGE_SECONDS / 3600:.0f}h)")
    return payload


def bundle(iso3: str) -> dict[str, Any] | None:
    return _cached(_name("country", iso3))


def geometry_gz(iso3: str) -> tuple[bytes, float] | None:
    return _raw(_name("geometry", iso3))


def plan_sources() -> dict[str, Any]:
    return _cached(_name("plans")) or {}


def strategy_inventory(iso3: str) -> list[dict[str, Any]] | None:
    data = _cached(_name("inventory"))
    return None if data is None else data.get(iso3)


def write_country(iso3: str, payload: dict[str, Any], geometry: dict[str, Any], directory: Path | None = None) -> None:
    _write(_name("country", iso3), payload, directory)
    _write(_name("geometry", iso3), geometry, directory)
    log.info("%s: wrote %s and %s to %s (%d units, %d mapped)", iso3, _name("country", iso3), _name("geometry", iso3),
             directory or constants.CACHE_DIR, len(payload.get("units", [])), len(geometry.get("features", [])))


def _keep_boundaries(iso3: str, payload: dict[str, Any], geometry: dict[str, Any]) -> dict[str, Any]:
    """Never let a rebuild with fewer matched boundaries replace a better artifact.

    Unit ids are derived from names, so features from the previous artifact still join
    to the fresh scores; only those whose unit is still present are carried over.
    """
    ids = {u["id"] for u in payload["units"]}
    kept: list[dict[str, Any]] = []
    for path in _candidates(_name("geometry", iso3)):
        try:
            features = json.loads(gzip.decompress(path.read_bytes())).get("features", []) if path.is_file() else []
        except (OSError, ValueError) as exc:
            log.warning("Unreadable artifact %s: %s", path, exc)
            continue
        matching = [f for f in features if f["properties"]["id"] in ids]
        if len(matching) > len(kept):
            kept = matching
    if len(kept) <= len(geometry["features"]):
        return geometry
    log.warning("%s: rebuild matched %d boundaries; keeping %d from the previous artifact", iso3, len(geometry["features"]), len(kept))
    payload["mapped"] = sorted(f["properties"]["id"] for f in kept)
    return {"type": "FeatureCollection", "features": kept}


def write_shared(plan_payload: dict[str, Any], inventory_payload: dict[str, Any], directory: Path | None = None) -> None:
    _write(_name("plans"), plan_payload, directory)
    _write(_name("inventory"), inventory_payload, directory)


def warm(force: bool = False, directory: Path | None = None) -> dict[str, Any]:
    global _last_attempt
    if not databricks.configured():
        log.warning("Data refresh skipped: Databricks is not configured")
        return {"ok": False, "reason": "Databricks is not configured"}
    if not _warm_lock.acquire(blocking=False):
        log.info("Data refresh skipped: a refresh is already running")
        return {"ok": False, "reason": "A refresh is already running"}
    _status["running"] = True
    _last_attempt = time.time()
    built, failed = [], {}
    plan_areas: dict[str, list[str]] = {}
    inventory_units: dict[str, list[dict[str, str]]] = {}
    started = time.time()
    selected = [c for c in countries.REGISTRY if force or c.status != "draft"]
    log.info("Data refresh started (%s): %s -> %s", "forced" if force else "scheduled", [c.iso3 for c in selected], directory or constants.CACHE_DIR)
    try:
        for country in selected:
            country_started = time.time()
            try:
                payload, geometry = assemble.from_databricks(country)
                geometry = _keep_boundaries(country.iso3, payload, geometry)
                write_country(country.iso3, payload, geometry, directory)
                built.append(country.iso3)
                if country.features.plan_sources:
                    level = country.filter_levels[0] if country.plan_source_level == "top" else country.local_level
                    plan_areas[country.iso3] = sorted({u["names"][level.column] for u in payload["units"]})
                if country.features.strategy_inventory:
                    inventory_units[country.iso3] = [{"name": u["names"][country.local_level.column], "region": u["names"][country.filter_levels[0].column]}
                                                     for u in payload["units"]]
                log.info("%s: refresh OK in %.1fs", country.iso3, time.time() - country_started)
            except Exception as exc:  # noqa: BLE001
                log.exception("%s: refresh FAILED after %.1fs (%s: %s); the previous artifact keeps serving",
                              country.iso3, time.time() - country_started, type(exc).__name__, exc)
                failed[country.iso3] = str(exc)[:300]
        try:
            write_shared(plans.load_from_databricks(plan_areas), inventory.load_all_from_databricks(inventory_units), directory)
            log.info("Shared artifacts (plan sources, strategy inventory) written")
        except Exception as exc:  # noqa: BLE001
            log.exception("Shared tables refresh FAILED (%s: %s)", type(exc).__name__, exc)
            failed["shared"] = str(exc)[:300]
        _status.update(lastWarm=time.time(), failed=failed, lastError=None if built else "No country could be rebuilt")
        (log.warning if failed else log.info)("Data refresh finished in %.1fs: built=%s failed=%s", time.time() - started, built, sorted(failed) or "none")
        with _memo_lock:
            _memo.clear()
        for hook in _hooks:
            try:
                hook()
            except Exception:  # noqa: BLE001
                log.exception("Refresh hook failed")
        return {"ok": bool(built), "built": built, "failed": failed}
    finally:
        _status["running"] = False
        _warm_lock.release()


def schedule_warm(force: bool = False, reason: str = "") -> None:
    if constants.DISABLE_BACKGROUND_WARM or not databricks.configured():
        return
    if not force and time.time() - _last_attempt < constants.WARM_RETRY_COOLDOWN_SECONDS:
        return
    if _warm_lock.locked():
        return
    log.info("Background data refresh scheduled%s", f": {reason}" if reason else "")
    threading.Thread(target=warm, kwargs={"force": force}, name="ldt-warm", daemon=True).start()


def startup() -> None:
    for country in countries.REGISTRY:
        found = next((p for p in _candidates(_name("country", country.iso3)) if p.is_file()), None)
        if found is None:
            log.warning("%s: no data artifact yet; its workspace shows a loading message until a refresh builds it", country.iso3)
        else:
            log.info("%s: data artifact %s (%s, built %.1fh ago)", country.iso3, found.name,
                     "cache" if found.parent == constants.CACHE_DIR else "snapshot", (time.time() - found.stat().st_mtime) / 3600)
    if constants.FORCE_WARM_ON_START:
        schedule_warm(force=True, reason="LDT_FORCE_WARM_ON_START is set")
        return
    newest = 0.0
    for country in countries.REGISTRY:
        for path in _candidates(_name("country", country.iso3)):
            if path.is_file():
                newest = max(newest, path.stat().st_mtime)
                break
    plans_file = next((p for p in _candidates(_name("plans")) if p.is_file()), None)
    documents = {iso3: len(b.get("national", [])) + sum(len(d) for d in b.get("local", {}).values()) for iso3, b in plan_sources().items()}
    (log.info if any(documents.values()) else log.warning)("Plan sources artifact %s: documents per country %s", plans_file or "missing", documents or "none")
    if time.time() - newest > constants.DATA_MAX_AGE_SECONDS:
        schedule_warm(force=True, reason=f"newest artifact is older than {constants.DATA_MAX_AGE_SECONDS / 3600:.0f}h")
    elif not any(documents.values()) and databricks.configured():
        # File times are not reliable after a deploy (a fresh checkout looks new), so an empty plan list triggers a refresh too.
        schedule_warm(force=True, reason="the plan sources artifact has no plans")


def status() -> dict[str, Any]:
    artifacts = {}
    for country in countries.REGISTRY:
        for path in _candidates(_name("country", country.iso3)):
            if path.is_file():
                artifacts[country.iso3] = {"ageSeconds": int(time.time() - path.stat().st_mtime), "from": "cache" if path.parent == constants.CACHE_DIR else "snapshot"}
                break
        else:
            artifacts[country.iso3] = None
    return {
        "databricksConfigured": databricks.configured(),
        "artifacts": artifacts,
        "running": _status["running"],
        "lastWarm": _status["lastWarm"],
        "failed": _status["failed"],
    }
