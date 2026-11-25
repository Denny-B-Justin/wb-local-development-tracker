from __future__ import annotations

from dash import html

import countries
from services import catalog, model, state
from services.state import Request
from utils.components import icon

from .pages_constants import METHODOLOGY_PIPELINE, PIL_DIAGRAM


def _section(section_id: str, title: str, children) -> html.Details:
    return html.Details(
        [html.Summary([title, icon("chevron-down", "acc-chevron")], className="acc-summary"), html.Div(children, className="acc-body")],
        id=section_id, className="acc",
    )


def _bullets(items) -> html.Ul:
    return html.Ul([html.Li(item) for item in items], className="bullets")


def render(req: Request) -> dict:
    t = req.t
    applies = []
    for index, country in enumerate(countries.published()):
        data = model.get(country)
        release = country.release_key(max(data.years)) if data else None
        applies.append(html.Span([" · " if index else "", state.localized_country(country, t)["name"],
                                  html.Span(f" {release}", className="font-mono text-meta") if release else None]))
    pipeline = html.Ol(
        [
            html.Li(
                [
                    html.A(
                        [html.Span([html.Span(str(i + 1), className="pipe-num"), t.t(f"methodology.pipeline.{key}.title")], className="pipe-title"),
                         html.Span(t.t(f"methodology.pipeline.{key}.detail"), className="text-meta text-muted")],
                        href=f"#{section}", className="pipe-step",
                    ),
                    icon("arrow-right", "pipe-arrow") if i < len(METHODOLOGY_PIPELINE) - 1 else None,
                ],
                className="pipe-item",
            )
            for i, (key, section) in enumerate(METHODOLOGY_PIPELINE)
        ],
        className="pipeline", **{"aria-label": t.t("methodology.pipelineAria")},
    )
    pillar_cards = html.Section(
        [
            html.Article(
                [
                    html.H2(t.t(f"data.pillars.{pillar}"), className="card-title"),
                    html.P(t.t_or(f"landing.pillars.{pillar}.description", ""), className="text-small text-muted mt-1"),
                    html.P(t.tp("methodology.indicatorCount", len(catalog.components_of(pillar))), className="label-caps text-muted mt-3"),
                    html.P(" · ".join(t.t_or(f"data.indicators.{c.id}", c.label) for c in catalog.components_of(pillar)), className="text-small text-ink-2 mt-1 relaxed"),
                ],
                className="card method-pillar",
            )
            for pillar in catalog.PILLARS
        ],
        className="grid-3 gap-4", **{"aria-label": t.t("methodology.pillarsAria")},
    )

    def groups(key: str):
        return html.Div(
            [html.Div([html.H3(group["title"], className="subheading"), _bullets(group["items"].values())], className="stack gap-2") for _, group in t.entries(key)],
            className="grid-3 gap-5",
        )

    sections = html.Div(
        [
            _section("framework", t.t("methodology.framework.title"), [
                *[html.P(p) for p in t.items("methodology.framework.paragraphs")],
                html.Img(src=PIL_DIAGRAM, alt=t.t("methodology.framework.diagramAlt"), className="diagram-img"),
            ]),
            _section("indicator-selection", t.t("methodology.indicatorSelection.title"), [
                html.P(t.t("methodology.indicatorSelection.intro")),
                _bullets(t.items("methodology.indicatorSelection.criteria")),
                html.Div(
                    [html.Div([html.H3(t.t(f"data.pillars.{pid}"), className="subheading"), html.P(p["body"], className="text-small text-ink-3"), _bullets(p["items"].values())], className="stack gap-2")
                     for pid, p in t.entries("methodology.indicatorSelection.pillars")],
                    className="grid-3 gap-5",
                ),
            ]),
            _section("data-sources", t.t("methodology.dataSources.title"), [html.P(t.t("methodology.dataSources.intro")), groups("methodology.dataSources.groups")]),
            _section("preprocessing", t.t("methodology.preprocessing.title"), [
                html.P(t.t("methodology.preprocessing.intro")),
                html.Dl([html.Div([html.Dt(step["title"], className="subheading"), html.Dd(step["body"], className="text-small text-ink-3 mt-1")])
                         for _, step in t.entries("methodology.preprocessing.steps")], className="grid-2 gap-5"),
            ]),
            _section("scoring", t.t("methodology.scoring.title"), [html.P(t.t("methodology.scoring.intro")), _bullets(t.items("methodology.scoring.steps"))]),
            _section("limitations", t.t("methodology.limitations.title"), [groups("methodology.limitations.groups"), html.P(t.t("methodology.limitations.references"))]),
        ],
        className="acc-list",
    )
    content = html.Div(
        [
            html.Header([
                html.P(t.t("methodology.eyebrow"), className="eyebrow"),
                html.H1(t.t("methodology.title"), className="doc-title"),
                html.P(t.t("methodology.intro"), className="doc-intro"),
                html.P([t.t("methodology.appliesTo"), " ", *applies], className="text-small text-muted mt-3"),
            ]),
            pipeline,
            pillar_cards,
            sections,
        ],
        className="doc-page gap-8",
    )
    return {"content": content, "title": t.t("methodology.metaTitle")}
