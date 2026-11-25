"""Local Development Tracker — Dash entry point (Posit Connect: app:app / app:server)."""

from __future__ import annotations

import logging
import mimetypes

from dash import Dash, Input, Output, dcc, html

import constants
from pages import about, brief, compare, data_trust, home, map as map_page, methodology, not_found, profile, release_notes, resources, strategy_inventory, units, why_ldt
from services import api, databricks, security, state, store
from utils import shell

logging.basicConfig(level=constants.LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
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

app = Dash(
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
server = app.server
server.config.update(MAX_CONTENT_LENGTH=64 * 1024, JSON_SORT_KEYS=False, SESSION_COOKIE_SECURE=True, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

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


for module in (units, brief):
    module.register(app)
api.register(server)
security.harden(server, app.csp_hashes())
store.startup()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=constants.PORT, debug=constants.DEBUG, dev_tools_ui=constants.DEBUG, dev_tools_props_check=constants.DEBUG)
