"""Deployment constants: environment, Unity Catalog tables, caching, security."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env", override=False)


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    value = _env(name, "1" if default else "0").lower()
    return value in {"1", "true", "yes", "on"}


APP_NAME = "Local Development Tracker"
APP_SHORT_NAME = "LDT"
APP_VERSION = "2.0.0"

ENVIRONMENT = _env("LDT_ENV", "production").lower()
DEBUG = _env_bool("DASH_DEBUG", False) and ENVIRONMENT == "development"
PORT = _env_int("PORT", 8050)
LOG_LEVEL = _env("LDT_LOG_LEVEL", "INFO").upper()

# --------------------------------------------------------------------------
# Azure Databricks: OAuth service principal for prd_mega.sgpbpi163
# --------------------------------------------------------------------------
DATABRICKS_SERVER_HOSTNAME = _env("DATABRICKS_SERVER_HOSTNAME")
DATABRICKS_HTTP_PATH = _env("DATABRICKS_HTTP_PATH")
DATABRICKS_CLIENT_ID = _env("DATABRICKS_CLIENT_ID")
DATABRICKS_CLIENT_SECRET = _env("DATABRICKS_CLIENT_SECRET")
DATABRICKS_QUERY_TIMEOUT_SECONDS = _env_int("DATABRICKS_QUERY_TIMEOUT_SECONDS", 120)

UC_CATALOG = _env("LDT_CATALOG", "prd_mega")
UC_SCHEMA = _env("LDT_SCHEMA", "sgpbpi163")
UC_DOCUMENTS_VOLUME = _env(
    "LDT_DOCUMENTS_VOLUME",
    "/Volumes/prd_mega/sgpbpi163/vgpbpi163/LDT/Local Development Plans",
)

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")

# Per-country Unity Catalog tables. Current production names first; the
# recommended names for new loads are in UC_TABLE_NAMING below and README §6.
UC_COUNTRY_TABLES: dict[str, dict[str, str]] = {
    "NPL": {
        "indicators": _env("LDT_NPL_INDICATORS_TABLE", "ldt_gpbp_ldt_npl_admin_2_demo"),
        "scores": _env("LDT_NPL_SCORES_TABLE", "ldt_gpbp_ldt_npl_scores_admin_2_demo"),
        "boundaries": _env("LDT_NPL_BOUNDARIES_TABLE", "ldt_boundaries_admin2_nepal"),
    },
    "SRB": {
        "indicators": _env("LDT_SRB_INDICATORS_TABLE", "ldt_gpbp_ldt_srb_admin_2_demo"),
        "scores": _env("LDT_SRB_SCORES_TABLE", "ldt_gpbp_ldt_srb_scores_admin_2_demo"),
        "boundaries": _env("LDT_SRB_BOUNDARIES_TABLE", "ldt_boundaries_admin2_serbia"),
    },
    "ZMB": {
        "indicators": _env("LDT_ZMB_INDICATORS_TABLE", "ldt_gpbp_ldt_zmb_admin_2_demo"),
        "scores": _env("LDT_ZMB_SCORES_TABLE", "ldt_gpbp_ldt_zmb_scores_admin_2_demo"),
        "boundaries": _env("LDT_ZMB_BOUNDARIES_TABLE", "ldt_boundaries_admin2_zambia"),
    },
    "VNM": {
        "indicators": _env("LDT_VNM_INDICATORS_TABLE", "ldt_indicators_vietnam"),
        "scores": _env("LDT_VNM_SCORES_TABLE", "ldt_scores_vietnam"),
        "boundaries": _env("LDT_VNM_BOUNDARIES_TABLE", "ldt_boundaries_admin2_vietnam"),
    },
    "GIN": {
        "indicators": _env("LDT_GIN_INDICATORS_TABLE", "ldt_indicators_guinea"),
        "scores": _env("LDT_GIN_SCORES_TABLE", "ldt_scores_guinea"),
        "boundaries": _env("LDT_GIN_BOUNDARIES_TABLE", "ldt_boundaries_admin2_guinea"),
    },
}

# Shared (all-country) tables. Each is optional: a missing table means the
# feature shows its empty state rather than failing.
UC_SHARED_TABLES: dict[str, str] = {
    "plan_sources": _env("LDT_PLAN_SOURCES_TABLE", "ldt_plan_document_sources"),
    "strategy_inventory": _env("LDT_STRATEGY_INVENTORY_TABLE", "ldt_strategy_inventory_documents"),
    "ai_stage_cache": _env("LDT_AI_STAGE_CACHE_TABLE", "ldt_ai_stage_cache"),
}

# Naming convention for tables created from now on (Guinea, re-loads, ...).
UC_TABLE_NAMING = {
    "indicators": "ldt_{iso3}_admin2_indicators",
    "scores": "ldt_{iso3}_admin2_scores",
    "boundaries": "ldt_{iso3}_admin2_boundaries",
}

# --------------------------------------------------------------------------
# Data artifacts (built off the request path; see services/store.py)
# --------------------------------------------------------------------------
def _writable_dir(path: Path) -> Path:
    """``path`` if the app can write there, else a folder in the system temp dir (the deployed app folder may be read-only)."""
    for candidate in (path, Path(tempfile.gettempdir()) / "ldt_cache"):
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / f".write-test-{os.getpid()}"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return candidate
        except OSError:
            continue
    return path


CACHE_DIR_REQUESTED = Path(_env("LDT_CACHE_DIR", str(ROOT_DIR / ".ldt_cache")))
CACHE_DIR = _writable_dir(CACHE_DIR_REQUESTED)
SNAPSHOT_DIR = Path(_env("LDT_SNAPSHOT_DIR", str(ROOT_DIR / "data_snapshot")))
DATA_MAX_AGE_SECONDS = _env_int("LDT_DATA_MAX_AGE_SECONDS", 12 * 3600)
WARM_RETRY_COOLDOWN_SECONDS = _env_int("LDT_WARM_RETRY_COOLDOWN_SECONDS", 600)
DISABLE_BACKGROUND_WARM = _env_bool("LDT_DISABLE_BG_WARM", False)
FORCE_WARM_ON_START = _env_bool("LDT_FORCE_WARM_ON_START", False)
REFRESH_TOKEN = _env("LDT_REFRESH_TOKEN")
PREVIEW_TOKEN = _env("LDT_PREVIEW_TOKEN")

REFERENCE_DIR = ROOT_DIR / "services" / "reference"
LOCALES_DIR = ROOT_DIR / "locales"
ASSETS_DIR = ROOT_DIR / "assets"

# --------------------------------------------------------------------------
# AI planning brief (optional; Posit mAI Gateway, see ai/client.py)
# --------------------------------------------------------------------------
# Gateway URL keeps its trailing "/". No API key: mAI identifies the app by
# CONNECT_CONTENT_GUID, which Posit Connect sets and ai/client.py reads per call.
MAI_BASE_URL = _env("MAI_BASE_URL")
MAI_ENDPOINT = _env("MAI_ENDPOINT")
MAI_MODEL = _env("MAI_MODEL") or "gpt-6-luna"
AI_GENERATION_DISABLED = _env_bool("AI_GENERATION_DISABLED", False)
AI_PROMPT_VERSION = _env("AI_PROMPT_VERSION", "v2")
AI_INVALIDATION_VERSION = _env("AI_INVALIDATION_VERSION", "v1")
AI_VISITOR_HOURLY_LIMIT = _env_int("AI_VISITOR_HOURLY_LIMIT", 70)
AI_DAILY_RUN_LIMIT = _env_int("AI_DAILY_RUN_LIMIT", 500)
AI_HTTP_TIMEOUT_SECONDS = _env_int("AI_HTTP_TIMEOUT_SECONDS", 90)
AI_DOCUMENT_MAX_BYTES = _env_int("AI_DOCUMENT_MAX_BYTES", 40 * 1024 * 1024)

# --------------------------------------------------------------------------
# Security
# --------------------------------------------------------------------------
ALLOWED_ORIGINS = [o.strip() for o in _env("LDT_ALLOWED_ORIGINS").split(",") if o.strip()]
MAX_QUERY_STRING_LENGTH = 2048
MAX_SEARCH_LENGTH = 80
COMPARE_MAX = 5
UNIT_ID_PATTERN = re.compile(r"^[a-f0-9]{12}$")
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+){0,15}$")
METRIC_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
API_RATE_LIMIT_PER_MINUTE = _env_int("LDT_API_RATE_LIMIT_PER_MINUTE", 120)
HSTS_SECONDS = 31536000

LOCALES = ("en", "fr")
DEFAULT_LOCALE = "en"
BETA_LOCALES = ("fr",)
LOCALE_NAMES = {"en": "English", "fr": "Français"}
