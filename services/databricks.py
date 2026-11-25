"""Azure Databricks access: OAuth service principal, TLS, parameterized SQL only."""

from __future__ import annotations

import logging
import threading
import time
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


def list_volume(root: str, max_depth: int = 4) -> list[dict[str, Any]]:
    if not configured():
        return []
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.core import Config

    client = WorkspaceClient(config=Config(
        host=f"https://{constants.DATABRICKS_SERVER_HOSTNAME}",
        client_id=constants.DATABRICKS_CLIENT_ID,
        client_secret=constants.DATABRICKS_CLIENT_SECRET,
        http_timeout_seconds=20,
        retry_timeout_seconds=40,
    ))
    files: list[dict[str, Any]] = []

    def walk(path: str, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            entries = list(client.files.list_directory_contents(path))
        except Exception as exc:  # noqa: BLE001
            log.warning("Cannot list volume path %s: %s", path, exc)
            return
        for entry in entries:
            entry_path = (entry.path or "").rstrip("/")
            if entry.is_directory:
                walk(entry_path, depth + 1)
            else:
                files.append({
                    "path": entry_path,
                    "name": entry_path.rsplit("/", 1)[-1],
                    "parent": entry_path.rsplit("/", 2)[-2] if entry_path.count("/") > 1 else "",
                    "size": getattr(entry, "file_size", None),
                })

    walk(root.rstrip("/"), 0)
    return files
