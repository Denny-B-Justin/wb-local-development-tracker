from __future__ import annotations

from dash import html

from services.state import Request
from utils.components import icon

from .pages_constants import COUNTRY_PACKS, RESOURCE_FILES, RESOURCE_FOLDER


def _file_card(req: Request, file: dict) -> html.A:
    t = req.t
    return html.A(
        [
            html.Span(t.t(f"resources.formats.{file['format']}"), className="format-tag label-caps"),
            html.Span([file["title"], icon("external-link", "file-ext")], className="file-title"),
            html.Span(t.t(f"resources.files.{file['id']}"), className="text-small relaxed text-ink-3"),
            html.Span(t.t("common.opensInNewTab"), className="sr-only"),
        ],
        href=file["href"], target="_blank", rel="noopener noreferrer", className="file-card",
    )


def _folder_link(href: str, label: str) -> html.A:
    return html.A([icon("folder", "size-3-5"), label, icon("external-link", "size-3")], href=href, target="_blank", rel="noopener noreferrer", className="folder-link")


def render(req: Request) -> dict:
    t = req.t
    sections = [
        html.Header([
            html.P(t.t("resources.eyebrow"), className="eyebrow"),
            html.H1(t.t("resources.title"), className="doc-title"),
            html.P(t.t("resources.intro"), className="doc-intro"),
        ]),
        html.Section(
            [
                html.Div([html.Div([html.H2(t.t("resources.core.title"), id="core", className="h2-20"), html.P(t.t("resources.core.description"), className="text-small text-ink-3 mt-1 max-w-3xl")]),
                          _folder_link(RESOURCE_FOLDER, t.t("resources.openFolder"))], className="res-head"),
                html.Div([_file_card(req, f) for f in RESOURCE_FILES], className="grid-3 gap-4"),
            ],
            className="stack gap-4", **{"aria-labelledby": "core"},
        ),
    ]
    for pack in COUNTRY_PACKS:
        country = t.t_or(f"data.countries.{pack['iso3']}", pack["iso3"])
        body = (html.Div([_file_card(req, f) for f in pack["files"]], className="grid-4 gap-4") if pack["files"]
                else html.P(t.t_or(f"resources.packs.{pack['iso3']}.empty", ""), className="empty-pack"))
        sections.append(html.Section(
            [
                html.Div([html.Div([html.H2(t.t("resources.packTitle", country=country), id=f"pack-{pack['iso3']}", className="h2-20"),
                                    html.P(t.t(f"resources.packs.{pack['iso3']}.description"), className="text-small text-ink-3 mt-1 max-w-3xl")]),
                          _folder_link(pack["href"], t.t("resources.openCountryFolder", country=country))], className="res-head"),
                body,
            ],
            className="stack gap-4 res-pack", **{"aria-labelledby": f"pack-{pack['iso3']}"},
        ))
    return {"content": html.Div(sections, className="doc-page gap-12"), "title": t.t("resources.metaTitle")}
