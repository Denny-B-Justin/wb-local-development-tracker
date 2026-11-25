from __future__ import annotations

from dash import html

from services.state import Request
from utils.components import link


def render(req: Request) -> dict:
    t = req.t
    return {
        "content": html.Div(
            [html.H1(t.t("notFound.title"), className="nf-title"), html.P(t.t("notFound.body"), className="text-body text-muted"),
             link(t.t("notFound.home"), req.site_href("home"), "font-semibold text-indigo-700 hover-indigo-800")],
            className="not-found",
        ),
        "title": t.t("notFound.title"),
    }
