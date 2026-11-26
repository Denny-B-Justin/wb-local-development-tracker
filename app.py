"""Local Development Tracker — Dash entry point (Posit Connect: app:app / app:server)."""

from __future__ import annotations

import logging
import mimetypes
import os
from importlib import metadata
from typing import Any

from dash import Dash, Input, Output, dcc, html
from flask import Flask

import constants
from pages import about, brief, compare, data_trust, home, map as map_page, methodology, not_found, profile, release_notes, resources, strategy_inventory, units, why_ldt
from services import api, databricks, logs, security, state, store
from utils import shell
from ai import client as ai_client, models

logs.setup()
log = logging.getLogger("ldt")
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("font/woff2", ".woff2")

SITE_PAGES = {
    "home": home, "why-ldt": why_ldt, "methodology": methodology, "resources": resources,
    "release-notes": release_notes, "about": about, "not-found": not_found,
}
WORKSPACE_PAGES = {
    "map": map_page, "compare": compare, "municipalities": units, "profile": profile,
    "brief": brief, "data": data_trust, "strategy-inventory": strategy_inventory,
}

INDEX = """<!DOCTYPE html>
<html lang="en">
<head>
{%metas%}
<title>{%title%}</title>
<link rel="icon" type="image/png" href="assets/img/brand/icon.png">
{%css%}
</head>
<body>
{%app_entry%}
<footer>{%config%}{%scripts%}{%renderer%}</footer>
</body>
</html>"""

_attached: set[int] = set()
_csp_hashes: list[str] | None = None


def attach(flask_app: Flask) -> None:
    """Give a Flask server the tracker's API routes, config and hardening (once per server)."""
    if _csp_hashes is None or id(flask_app) in _attached:
        return
    _attached.add(id(flask_app))
    flask_app.config.update(MAX_CONTENT_LENGTH=64 * 1024, JSON_SORT_KEYS=False, SESSION_COOKIE_SECURE=True, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
    api.register(flask_app)
    security.harden(flask_app, _csp_hashes)
    rules = sorted(str(r) for r in flask_app.url_map.iter_rules() if str(r).startswith("/api/"))
    log.info("API routes attached to Flask server %r (id %x): %s", flask_app.name, id(flask_app), rules)


class TrackerDash(Dash):
    """Dash that keeps the tracker's Flask routes on whichever server it is bound to.

    A host (Posit Connect's Dash runner) may call ``init_app`` to bind the app to its own
    Flask server. Routes added to the original server would then be unreachable, and
    /api/* would fall through to Dash's catch-all and return the HTML page instead.
    """

    def init_app(self, app: Any = None, **kwargs) -> None:
        previous = getattr(self, "server", None)
        super().init_app(app, **kwargs)
        if previous is not None and self.server is not previous:
            log.warning("Dash was re-bound to another Flask server (id %x -> %x) by the host; attaching the API routes there too",
                        id(previous), id(self.server))
        attach(self.server)


app = TrackerDash(
    __name__,
    title=constants.APP_NAME,
    update_title=None,
    suppress_callback_exceptions=True,
    serve_locally=True,
    compress=True,
    assets_ignore=r".*\.mjs$|.*/geo/.*",
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"},
        {"name": "description", "content": "Compare local development conditions, read municipality-level score drivers, and link planning evidence to public investment choices."},
        {"name": "theme-color", "content": "#141a2e"},
    ],
)
app.index_string = INDEX

app.layout = html.Div([dcc.Location(id="url", refresh="callback-nav"), html.Div(id="page", className="page-root")])


def _loading(req: state.Request) -> html.Div:
    names = state.localized_country(req.country, req.t)
    return html.Div(html.Div([
        html.H1(names["name"], className="page-title"),
        html.P(req.t.t("workspace.loading" if databricks.configured() else "workspace.notLoaded"), className="page-subtitle"),
    ], className="card empty-card"), className="stack gap-5")


def render(search: str | None) -> list:
    req = state.parse(search)
    page_key = f"{req.page}:{req.country.slug if req.country else ''}:{req.lang}"
    if req.page in WORKSPACE_PAGES:
        name = state.localized_country(req.country, req.t)["name"]
        if req.model is None:
            result = {"content": _loading(req), "title": name}
        else:
            result = WORKSPACE_PAGES[req.page].render(req)
        body = shell.workspace_frame(req, result["content"], result.get("actions"), result.get("active_unit"))
        title = f"{result['title']} · {name} · {constants.APP_SHORT_NAME}"
    else:
        result = SITE_PAGES.get(req.page, not_found).render(req)
        body = shell.site_frame(req, result["content"])
        title = result["title"] if req.page == "home" else f"{result['title']} · {constants.APP_SHORT_NAME}"
    return [html.Div(id="page-meta", hidden=True, **{"data-title": title, "data-lang": req.lang, "data-page": page_key}), body]


@app.callback(Output("page", "children"), Input("url", "search"))
def route(search):
    try:
        return render(search)
    except Exception:  # noqa: BLE001
        log.exception("Page render failed for %s", search)
        req = state.parse("")
        return [html.Div(id="page-meta", hidden=True, **{"data-title": constants.APP_NAME, "data-lang": "en", "data-page": "error"}),
                shell.site_frame(req, html.Div([html.H1("Something went wrong", className="nf-title"),
                                                html.P("This view could not be shown. Try again, or go back to the home page.", className="text-body text-muted")],
                                               className="not-found"))]


def _log_runtime() -> None:
    def version(name: str) -> str:
        try:
            return metadata.version(name)
        except metadata.PackageNotFoundError:
            return "not installed"

    log.info("Runtime: dash %s, flask %s, werkzeug %s, flask-compress %s, gunicorn %s", version("dash"), version("flask"),
             version("werkzeug"), version("flask-compress"), version("gunicorn"))
    log.info("Dash paths: routes_pathname_prefix=%s requests_pathname_prefix=%s; host env: %s", app.config.routes_pathname_prefix,
             app.config.requests_pathname_prefix, {k: v for k, v in os.environ.items() if k.startswith(("DASH_", "SCRIPT_NAME"))} or "none")


def _log_settings() -> None:
    """Which settings this process sees: names and set/missing only, never secret values."""
    missing = databricks.missing_settings()
    log.info("Settings: Databricks %s", "configured" if not missing else f"NOT configured (missing {missing}); data comes from the shipped snapshot only")
    mai = {name: bool(os.environ.get(name, "").strip()) for name in ("MAI_BASE_URL", "MAI_ENDPOINT", "CONNECT_CONTENT_GUID")}
    model = constants.MAI_MODEL if models.selected() else f"{constants.MAI_MODEL} (NOT an allowed model: {sorted(models.MODELS)})"
    (log.info if all(mai.values()) and models.selected() else log.warning)(
        "Settings: AI brief %s; model %s; %s", "ready" if ai_client.configured() else "NOT configured",
        model, ", ".join(f"{k} {'set' if v else 'MISSING'}" for k, v in mai.items()))
    if constants.CACHE_DIR != constants.CACHE_DIR_REQUESTED:
        log.warning("Settings: cache folder %s is not writable; using %s instead (not shared between processes, cleared on restart)",
                    constants.CACHE_DIR_REQUESTED, constants.CACHE_DIR)
    else:
        log.info("Settings: cache folder %s (writable)", constants.CACHE_DIR)
    shipped = sorted(p.name for p in constants.SNAPSHOT_DIR.glob("*.json.gz")) if constants.SNAPSHOT_DIR.is_dir() else []
    (log.info if shipped else log.error)("Settings: snapshot folder %s holds %d artifacts%s", constants.SNAPSHOT_DIR, len(shipped),
                                         "" if shipped else " (LDT_SNAPSHOT_DIR wrong, or data_snapshot/ was not deployed)")
    log.info("Settings: LDT_ALLOWED_ORIGINS has %d entries; background refresh %s, max artifact age %.0fh", len(constants.ALLOWED_ORIGINS),
             "disabled" if constants.DISABLE_BACKGROUND_WARM else "enabled", constants.DATA_MAX_AGE_SECONDS / 3600)


for module in (units, brief):
    module.register(app)
# Hashes are final only once every callback is defined; servers bound later reuse them.
_csp_hashes = list(app.csp_hashes())
attach(app.server)
server = app.server
_log_runtime()
_log_settings()
store.startup()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=constants.PORT, debug=constants.DEBUG, dev_tools_ui=constants.DEBUG, dev_tools_props_check=constants.DEBUG)
