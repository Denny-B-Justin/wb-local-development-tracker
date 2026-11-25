from __future__ import annotations

from dash import html

import countries
from services import model, state
from services.state import Request
from utils.components import cx, dropdown, icon, link

from .pages_constants import HERO_BACKGROUND, LANDING_FEATURES, LANDING_PILLARS, LANDING_SHOTS, WHY_POINTS


def _country_select(req: Request) -> html.Details:
    t = req.t
    items = []
    for country in countries.visible(req.preview):
        names = state.localized_country(country, t)
        data = model.get(country)
        meta = names["landing_meta"].replace("{units}", t.count(data.context_summary(data.default_year, {})["unitCount"])) if data else names["landing_meta"].replace("{units} ", "")
        href = state.build({"page": "map", "country": country.slug, **({"lang": req.lang} if req.lang != "en" else {})})
        items.append(link(
            [html.Span(names["name"], className="cs-name"), html.Span([meta, icon("arrow-right", "cs-arrow")], className="cs-meta")],
            href, "dd-item cs-item", role="menuitem",
        ))
    return dropdown(
        [t.t("landing.selectCountry"), icon("chevron-down", "size-4 text-indigo-600")], items,
        cls="country-select", trigger_cls="cs-trigger", panel_cls="cs-panel", label=t.t("landing.selectCountryAria"),
    )


def _feature_list(req: Request) -> html.Div:
    t = req.t
    labels = [t.t(f"landing.features.{key}") for key in LANDING_FEATURES]
    items = [
        html.Li(
            html.Button(
                [html.Span(f"{i + 1:02d}", className="fl-num"), labels[i]],
                type="button", className=cx("fl-item js-feature", i == 0 and "is-active"),
                **{"data-index": str(i), "aria-pressed": "true" if i == 0 else "false"},
            ),
            className=cx(i > 0 and "fl-divider"),
        )
        for i in range(len(labels))
    ]
    shots = [
        html.Img(src=LANDING_SHOTS[key], alt=t.t("landing.featureScreenshot", feature=labels[i]) if i == 0 else "",
                 className=cx("fl-shot", i == 0 and "is-active"), **{"data-index": str(i), "data-alt": t.t("landing.featureScreenshot", feature=labels[i]),
                                                                    "aria-hidden": "false" if i == 0 else "true"})
        for i, key in enumerate(LANDING_FEATURES)
    ]
    return html.Div([html.Ol(items, className="fl-list"), html.Div(shots, className="fl-media")], className="feature-list js-features")


def render(req: Request) -> dict:
    t = req.t
    hero = html.Section(
        [
            html.Div(className="grid-overlay", **{"aria-hidden": "true"}),
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(t.t("landing.eyebrow"), className="eyebrow-pill label-caps"),
                            html.H1(t.t("landing.title"), id="hero-title", className="hero-title"),
                            html.P(t.t("landing.lead"), className="hero-lead"),
                            html.Div([html.Span(t.t("landing.openWorkspace"), className="hero-open", id="open-workspace"), _country_select(req)], className="hero-cta"),
                        ],
                        className="hero-copy",
                    ),
                    html.Div(
                        [
                            html.Div(className="hero-stage", **{"aria-hidden": "true"}),
                            html.Button(icon("pause", "size-3-5"), type="button", className="hero-toggle",
                                        **{"aria-label": t.t("landing.pauseAnimation"), "data-play": t.t("landing.playAnimation"), "data-pause": t.t("landing.pauseAnimation")}),
                        ],
                        className="hero-animation", role="img", **{"aria-label": t.t("landing.heroAnimation"), "data-widget": "hero"},
                    ),
                ],
                className="hero-grid pad",
            ),
        ],
        className="hero", style={"background": HERO_BACKGROUND}, **{"aria-labelledby": "hero-title"},
    )

    why = html.Section(
        [
            html.Div(
                [
                    html.P(t.t("why.eyebrow"), className="eyebrow"),
                    html.H2(t.t("why.home.title"), id="why-title", className="why-home-title"),
                    link([t.t("why.home.link"), " ", icon("arrow-right", "size-4")], req.site_href("why-ldt"), "arrow-link"),
                ],
                className="stack-start gap-4",
            ),
            html.Div(
                [html.Div([html.H3(t.t(f"why.home.{p}.title"), className="card-title"), html.P(t.t(f"why.home.{p}.body"), className="why-point-body")], className="why-point")
                 for p in WHY_POINTS],
                className="why-points",
            ),
        ],
        className="home-why pad", **{"aria-labelledby": "why-title"},
    )

    workspace = html.Section(
        [html.H2(t.t("landing.workspaceTitle"), id="workspace-title", className="dark-h2"), _feature_list(req)],
        className="home-workspace pad", **{"aria-labelledby": "workspace-title"},
    )

    band = html.Div(html.Div(html.Img(src="assets/img/landing/data-band.jpg", alt=t.t("landing.bandPhoto"), className="band-img"), className="band-frame"), className="home-band pad")

    scores = html.Section(
        [
            html.Div(
                [
                    html.H2(t.t("landing.scoresTitle"), id="scores-title", className="section-h2"),
                    html.P(t.t("landing.scoresLead"), className="lead-15"),
                    link([t.t("landing.readMethodology"), " ", icon("arrow-right", "size-4")], req.site_href("methodology"), "arrow-link"),
                ],
                className="stack-start gap-4",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(icon(icon_name, "pillar-icon-glyph"), className="pillar-icon"),
                            html.H3(t.t(f"data.pillars.{pillar}"), className="pillar-title"),
                            html.P(t.t(f"landing.pillars.{pillar}.description"), className="pillar-desc"),
                            html.P(t.t(f"landing.pillars.{pillar}.indicators"), className="pillar-indicators"),
                        ],
                        className="pillar-card",
                    )
                    for pillar, icon_name in LANDING_PILLARS
                ],
                className="pillar-cards",
            ),
        ],
        className="home-scores pad", **{"aria-labelledby": "scores-title"},
    )
    return {"content": [hero, why, workspace, band, scores], "title": t.t("site.name")}
