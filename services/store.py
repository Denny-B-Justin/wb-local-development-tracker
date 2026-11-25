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
        schedule_warm()
        return None
    payload, mtime = loaded
    with _memo_lock:
        _memo[name] = (mtime, payload)
    if time.time() - mtime > constants.DATA_MAX_AGE_SECONDS:
        schedule_warm()
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
        return {"ok": False, "reason": "Databricks is not configured"}
    if not _warm_lock.acquire(blocking=False):
        return {"ok": False, "reason": "A refresh is already running"}
    _status["running"] = True
    _last_attempt = time.time()
    built, failed = [], {}
    try:
        for country in countries.REGISTRY:
            if country.status == "draft" and not force:
                continue
            try:
                payload, geometry = assemble.from_databricks(country)
                geometry = _keep_boundaries(country.iso3, payload, geometry)
                write_country(country.iso3, payload, geometry, directory)
                built.append(country.iso3)
            except Exception as exc:  # noqa: BLE001
                log.exception("Warm failed for %s", country.iso3)
                failed[country.iso3] = str(exc)[:300]
        try:
            write_shared(plans.load_from_databricks(), inventory.load_all_from_databricks(), directory)
        except Exception as exc:  # noqa: BLE001
            log.exception("Warm failed for shared tables")
            failed["shared"] = str(exc)[:300]
        _status.update(lastWarm=time.time(), failed=failed, lastError=None if built else "No country could be rebuilt")
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


def schedule_warm(force: bool = False) -> None:
    if constants.DISABLE_BACKGROUND_WARM or not databricks.configured():
        return
    if not force and time.time() - _last_attempt < constants.WARM_RETRY_COOLDOWN_SECONDS:
        return
    if _warm_lock.locked():
        return
    threading.Thread(target=warm, kwargs={"force": force}, name="ldt-warm", daemon=True).start()


def startup() -> None:
    if constants.FORCE_WARM_ON_START:
        schedule_warm(force=True)
        return
    newest = 0.0
    for country in countries.REGISTRY:
        for path in _candidates(_name("country", country.iso3)):
            if path.is_file():
                newest = max(newest, path.stat().st_mtime)
                break
    if time.time() - newest > constants.DATA_MAX_AGE_SECONDS:
        schedule_warm(force=True)


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
