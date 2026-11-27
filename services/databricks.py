"""Azure Databricks access: OAuth service principal, TLS, parameterized SQL only."""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Any, Iterator

import pandas as pd

import constants

log = logging.getLogger(__name__)

_lock = threading.Lock()
_missing_tables: set[str] = set()


class DatabricksNotConfigured(RuntimeError):
    pass


_SETTINGS = ("DATABRICKS_SERVER_HOSTNAME", "DATABRICKS_HTTP_PATH", "DATABRICKS_CLIENT_ID", "DATABRICKS_CLIENT_SECRET")
_warned_unconfigured = False


def missing_settings() -> list[str]:
    return [name for name in _SETTINGS if not getattr(constants, name)]


def configured() -> bool:
    global _warned_unconfigured
    missing = missing_settings()
    if missing and not _warned_unconfigured:
        _warned_unconfigured = True
        log.warning("Databricks is not configured (missing: %s); the app serves data_snapshot/ and cached artifacts only", ", ".join(missing))
    return not missing


def _describe(statement: str, parameters: dict[str, Any]) -> str:
    """The statement for logs: one line, with the IDENTIFIER table parameter written out. Never other values."""
    text = " ".join(statement.split())
    table = parameters.get("table")
    return text.replace("IDENTIFIER(:table)", str(table)) if isinstance(table, str) else text


def _identifier(part: str) -> str:
    if not constants.IDENTIFIER_PATTERN.fullmatch(part or ""):
        raise ValueError(f"Unsafe SQL identifier: {part!r}")
    return part


def table_name(table: str) -> str:
    """Fully qualified catalog.schema.table; every part is allowlist-validated."""
    return ".".join(_identifier(p) for p in (constants.UC_CATALOG, constants.UC_SCHEMA, table))


def _credentials():
    from databricks.sdk.core import Config, oauth_service_principal

    config = Config(
        host=f"https://{constants.DATABRICKS_SERVER_HOSTNAME}",
        client_id=constants.DATABRICKS_CLIENT_ID,
        client_secret=constants.DATABRICKS_CLIENT_SECRET,
    )
    return oauth_service_principal(config)


@contextmanager
def connection() -> Iterator[Any]:
    if not configured():
        raise DatabricksNotConfigured("DATABRICKS_* environment variables are not set")
    from databricks import sql

    started = time.time()
    try:
        conn = sql.connect(
            server_hostname=constants.DATABRICKS_SERVER_HOSTNAME,
            http_path=constants.DATABRICKS_HTTP_PATH,
            credentials_provider=_credentials,
            _socket_timeout=constants.DATABRICKS_QUERY_TIMEOUT_SECONDS,
            user_agent_entry="wb-local-development-tracker",
        )
    except Exception as exc:
        log.error("Databricks connection to %s (warehouse %s) failed after %.2fs: %s: %s",
                  constants.DATABRICKS_SERVER_HOSTNAME, constants.DATABRICKS_HTTP_PATH, time.time() - started, type(exc).__name__, exc)
        raise
    try:
        yield conn
    finally:
        conn.close()


def query(statement: str, parameters: dict[str, Any] | None = None) -> pd.DataFrame:
    """Run a parameterized statement (named :markers). Never format values into SQL."""
    parameters = parameters or {}
    described = _describe(statement, parameters)
    started = time.time()
    log.debug("Databricks query: %s", described)
    try:
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(statement, parameters)
            if cursor.description is None:
                return pd.DataFrame()
            try:
                frame = cursor.fetchall_arrow().to_pandas()
            except Exception:  # noqa: BLE001 - connector without pyarrow
                rows = cursor.fetchall()
                frame = pd.DataFrame(rows, columns=[d[0] for d in cursor.description])
    except DatabricksNotConfigured:
        raise
    except Exception as exc:
        log.error("Databricks query FAILED after %.2fs: %s | %s: %s", time.time() - started, described, type(exc).__name__, exc)
        raise
    log.info("Databricks query OK in %.2fs: %d rows x %d columns | %s", time.time() - started, len(frame), len(frame.columns), described)
    return frame


def execute(statement: str, parameters: dict[str, Any] | None = None) -> None:
    parameters = parameters or {}
    started = time.time()
    try:
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(statement, parameters)
    except Exception as exc:
        log.error("Databricks statement FAILED after %.2fs: %s | %s: %s", time.time() - started, _describe(statement, parameters), type(exc).__name__, exc)
        raise
    log.info("Databricks statement OK in %.2fs: %s", time.time() - started, _describe(statement, parameters).split(" USING ")[0])


def read_table(table: str) -> pd.DataFrame:
    return query("SELECT * FROM IDENTIFIER(:table)", {"table": table_name(table)})


def table_exists(table: str) -> bool:
    if table in _missing_tables:
        return False
    try:
        frame = query(
            "SELECT 1 FROM system.information_schema.tables "
            "WHERE table_catalog = :catalog AND table_schema = :schema AND table_name = :table LIMIT 1",
            {"catalog": constants.UC_CATALOG, "schema": constants.UC_SCHEMA, "table": table.lower()},
        )
    except DatabricksNotConfigured:
        return False
    exists = not frame.empty
    if not exists:
        log.warning("Table %s does not exist (or is not visible to the service principal); features that read it stay empty", table_name(table))
        with _lock:
            _missing_tables.add(table)
    return exists


def read_optional(table: str, where: str = "", parameters: dict[str, Any] | None = None) -> pd.DataFrame:
    if not table_exists(table):
        return pd.DataFrame()
    params = {"table": table_name(table), **(parameters or {})}
    return query(f"SELECT * FROM IDENTIFIER(:table) {where}", params)


VOLUME_LISTING_TTL_SECONDS = 600
_volume_listings: dict[str, tuple[float, list[dict[str, Any]]]] = {}


def _workspace_client():
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.core import Config

    return WorkspaceClient(config=Config(
        host=f"https://{constants.DATABRICKS_SERVER_HOSTNAME}",
        client_id=constants.DATABRICKS_CLIENT_ID,
        client_secret=constants.DATABRICKS_CLIENT_SECRET,
        http_timeout_seconds=20,
        retry_timeout_seconds=40,
    ))


def download_file(path: str, max_bytes: int) -> bytes:
    """A file from a Unity Catalog volume, with a size cap."""
    if not configured():
        raise DatabricksNotConfigured("Databricks is not configured")
    started = time.time()
    contents = _workspace_client().files.download(path).contents
    data = contents.read(max_bytes + 1)
    if len(data) > max_bytes:
        log.warning("Volume download ABORTED: %s is larger than %.0f MB", path, max_bytes / 1048576)
        raise RuntimeError("The plan document is too large to process.")
    log.info("Volume download OK in %.1fs: %s (%.1f KB)", time.time() - started, path, len(data) / 1024)
    return data


def list_volume(root: str, max_depth: int = 12) -> list[dict[str, Any]]:
    """Every file under ``root``, recursively. ``folders`` holds the folder names between ``root`` and the file.
    Listings are reused for a few minutes, so plan sources and the strategy inventory share one walk."""
    if not configured():
        return []
    root = root.rstrip("/")
    with _lock:
        hit = _volume_listings.get(root)
    if hit and time.time() - hit[0] < VOLUME_LISTING_TTL_SECONDS:
        return hit[1]
    client = _workspace_client()
    files: list[dict[str, Any]] = []
    folders_seen = 0
    started = time.time()

    def listing(path: str) -> list[Any] | None:
        try:
            return list(client.files.list_directory_contents(path))
        except Exception as exc:  # noqa: BLE001
            log.warning("Cannot list volume path %s: %s", path, exc)
            return None

    # One level at a time, the folders of a level in parallel: a country can have hundreds of folders.
    level, depth = [root], 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        while level:
            if depth > max_depth:
                log.warning("Volume: %d folders more than %d levels below %s were not listed, e.g. %s", len(level), max_depth, root, level[:3])
                break
            next_level = []
            for entries in pool.map(listing, level):
                if entries is None:
                    continue
                folders_seen += 1
                for entry in entries:
                    entry_path = (entry.path or "").rstrip("/")
                    if entry.is_directory:
                        next_level.append(entry_path)
                        continue
                    relative = entry_path[len(root) + 1:] if entry_path.startswith(root + "/") else entry_path.rsplit("/", 1)[-1]
                    files.append({
                        "path": entry_path,
                        "name": entry_path.rsplit("/", 1)[-1],
                        "parent": entry_path.rsplit("/", 2)[-2] if entry_path.count("/") > 1 else "",
                        "folders": relative.split("/")[:-1],
                        "size": getattr(entry, "file_size", None),
                    })
            level, depth = next_level, depth + 1
    log.info("Volume %s: %d files in %d folders, listed in %.1fs (deepest file %d folders down)", root, len(files), folders_seen,
             time.time() - started, max((len(f["folders"]) for f in files), default=0))
    with _lock:
        _volume_listings[root] = (time.time(), files)
    return files
