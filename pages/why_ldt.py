from __future__ import annotations

from dash import html

import countries
from services import state
from services.state import Request
from utils.components import icon, link

from .pages_constants import INNER_HERO_BACKGROUND, WHY_GLANCE, WHY_SECTIONS


def _section(section_id: str, number: int, title: str, children) -> html.Section:
    return html.Section(
        [
            html.Div([html.Span(f"{number:02d}", className="why-num"), html.H2(title, id=f"{section_id}-title", className="why-h2")], className="why-aside"),
            html.Div(children, className="why-body"),
        ],
        id=section_id, className="why-section", **{"aria-labelledby": f"{section_id}-title"},
    )


def render(req: Request) -> dict:
    t = req.t
    lead, *problem = t.items("why.problem.paragraphs")
    header = html.Header(
        [
            html.Div(className="grid-overlay", **{"aria-hidden": "true"}),
            html.Div(
                [
                    html.Span(t.t("why.eyebrow"), className="eyebrow-pill label-caps"),
                    html.H1(t.t("why.title"), className="why-title"),
                    html.P(t.t("why.home.title"), className="why-lead"),
                    html.Nav(
                        [html.A([html.Span(f"{i + 1:02d}", className="why-chip-num"), t.t(f"why.{sid}.title")], href=f"#{sid}", className="why-chip")
                         for i, sid in enumerate(WHY_SECTIONS)],
                        className="why-chips", **{"aria-label": t.t("why.onThisPage")},
                    ),
                ],
                className="why-header-inner pad",
            ),
        ],
        className="dark-header", style={"background": INNER_HERO_BACKGROUND},
    )
    glance = html.Div(
        [
            html.Div(
                [
                    html.Span(icon(name, "size-5"), className="glance-icon"),
                    html.H4(t.t(f"why.glance.{gid}.title"), className="glance-title"),
                    html.P(t.t(f"why.glance.{gid}.body"), className="glance-body"),
                ],
                className="glance-card",
            )
            for gid, name in WHY_GLANCE
        ],
        className="glance-grid",
    )
    body = html.Div(
        [
            _section("problem", 1, t.t("why.problem.title"), [html.P(lead, className="why-leadpara"), *[html.P(p, className="prose") for p in problem]]),
            _section("does", 2, t.t("why.does.title"), [*[html.P(p, className="prose") for p in t.items("why.does.paragraphs")],
                                                        html.H3(t.t("why.glance.title"), className="label-caps text-indigo-label mt-3"), glance]),
            _section("scope", 3, t.t("why.scope.title"), html.Div([icon("info", "scope-icon"), html.P(t.t("why.scope.body"), className="prose")], className="scope-note")),
            _section("modules", 4, t.t("why.modules.title"), html.Div(html.P(t.t("why.modules.body"), className="prose"), className="modules-note")),
        ],
        className="why-sections pad",
    )
    cta_links = [
        link([state.localized_country(c, t)["name"], icon("arrow-right", "size-4")], state.build({"page": "map", "country": c.slug, **({"lang": req.lang} if req.lang != "en" else {})}), "cta-country")
        for c in countries.published()
    ]
    cta = html.Section(
        [
            html.Div(className="grid-overlay", **{"aria-hidden": "true"}),
            html.Div(
                [
                    html.Div([html.H2(t.t("why.cta.title"), id="why-cta", className="cta-title"), html.P(t.t("why.cta.body"), className="cta-body")], className="max-w-560"),
                    html.Div(
                        [html.Div(cta_links, className="cta-links"),
                         link([t.t("why.cta.methodology"), " ", icon("arrow-right", "size-4")], req.site_href("methodology"), "cta-method")],
                        className="stack-start gap-4",
                    ),
                ],
                className="cta-inner pad",
            ),
        ],
        className="dark-header", style={"background": INNER_HERO_BACKGROUND}, **{"aria-labelledby": "why-cta"},
    )
    return {"content": [header, body, cta], "title": t.t("why.metaTitle")}
