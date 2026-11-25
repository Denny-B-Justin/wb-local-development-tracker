from __future__ import annotations

from dash import html

from services.state import Request
from utils.components import bold_lead, rich

from .pages_constants import RELEASE_TYPES, RELEASES


def _type_badge(t, kind: str) -> html.Span:
    return html.Span(t.t(f"releaseNotes.types.{kind}.label"), className=f"rn-badge rn-{kind} label-caps")


def render(req: Request) -> dict:
    t = req.t
    entries_lang = None if req.lang == "en" else "en"
    header = html.Header(
        html.Div(
            [
                html.P(t.t("releaseNotes.eyebrow"), className="eyebrow"),
                html.H1(t.t("releaseNotes.title"), className="doc-title"),
                html.P(t.t("releaseNotes.intro"), className="doc-intro max-w-2xl"),
                html.P(t.t("releaseNotes.englishOnly"), className="text-small text-muted mt-2 max-w-2xl") if entries_lang else None,
                html.Dl(
                    [html.Div([html.Dt(_type_badge(t, kind), className="rn-dt"), html.Dd(t.t(f"releaseNotes.types.{kind}.description"))], className="rn-type")
                     for kind in RELEASE_TYPES],
                    className="rn-types", **{"aria-label": t.t("releaseNotes.typesAria")},
                ),
            ],
            className="rn-wrap rn-head",
        ),
        className="rn-header",
    )
    coming = html.Section(
        [
            html.H2(t.t("releaseNotes.comingNextTitle"), id="coming-next", className="card-title text-indigo-800"),
            html.Ul([html.Li(rich(item, {"b": lambda s: html.Strong(s, className="font-semibold text-ink")})) for item in t.items("releaseNotes.comingNext")], className="coming-list"),
        ],
        className="coming-next", **{"aria-labelledby": "coming-next"},
    )
    articles = []
    for index, release in enumerate(RELEASES):
        version = release["version"]
        anchor = version.replace(".", "-")
        lang_props = {"lang": entries_lang} if entries_lang else {}
        articles.append(html.Article(
            [
                html.Div(
                    [
                        html.H2(version, id=f"{anchor}-title", className="rn-version"),
                        _type_badge(t, release["type"]),
                        html.Span(t.date(release["date"]) if release.get("date") else t.t("releaseNotes.inPreview"), className="text-small text-muted"),
                        html.Span(t.t("releaseNotes.latest"), className="rn-latest") if index == 0 else None,
                    ],
                    className="rn-title-row",
                ),
                html.P(release["summary"], className="rn-summary", **lang_props),
                *[
                    html.Section([html.H3(section["title"], className="text-small font-semibold text-ink"),
                                  html.Ul([html.Li(bold_lead(item)) for item in section["items"]], className="rn-items")],
                                 className="mt-5", **lang_props)
                    for section in release["sections"]
                ],
            ],
            id=anchor, className="rn-article", **{"aria-labelledby": f"{anchor}-title"},
        ))
    body = html.Div([coming, *articles], className="rn-wrap rn-body")
    return {"content": html.Div([header, body], className="bg-canvas"), "title": t.t("releaseNotes.metaTitle")}
