from __future__ import annotations

from dash import html

from services.state import Request

from .pages_constants import ABOUT_FIGURES, ABOUT_HIGHLIGHTS, ABOUT_NOTE_VERSION, ABOUT_REFERENCES


def _figure(src: str, alt: str, caption: str) -> html.Figure:
    return html.Figure([html.Img(src=src, alt=alt, className="fig-img"), html.Figcaption(caption, className="fig-caption")], className="figure-card")


def _section(section_id: str, title: str, children, eyebrow: str | None = None) -> html.Section:
    return html.Section(
        [html.P(eyebrow, className="eyebrow") if eyebrow else None, html.H2(title, id=section_id, className=f"about-h2{' after-eyebrow' if eyebrow else ''}"), *children],
        className="about-section", **{"aria-labelledby": section_id},
    )


def render(req: Request) -> dict:
    t = req.t
    prose = "prose-14"
    paragraphs = lambda key: [html.P(p, className=prose) for p in t.items(key)]  # noqa: E731
    findings = t.raw("about.findings")
    content = html.Div(
        [
            html.Header([
                html.P(t.t("about.eyebrow"), className="eyebrow"),
                html.H1(t.t("about.title"), className="about-title"),
                html.P(t.t("about.version", date=t.date(ABOUT_NOTE_VERSION)), className="text-small text-muted mt-1"),
                html.P(t.t("about.lead"), className="about-lead"),
            ]),
            _section("challenge", t.t("about.challenge.title"), paragraphs("about.challenge.paragraphs")),
            _section("method", t.t("about.method.title"), [html.P(t.t("about.method.intro"), className=prose)]),
            _section("layer-1", t.t("about.layerOne.title"), [
                html.P(t.t("about.layerOne.intro"), className=prose),
                html.Div([
                    html.Ol([html.Li([html.H3(step["title"], className="text-body font-semibold text-ink"), html.P(step["body"], className="text-small relaxed text-ink-3 mt-1-5")], className="step-card")
                             for _, step in t.entries("about.layerOne.steps")], className="stack gap-4"),
                    _figure(ABOUT_FIGURES["sizeDistribution"], t.t("about.layerOne.figureAlt"), t.t("about.layerOne.figureCaption")),
                ], className="grid-2 gap-6 items-start"),
            ], eyebrow=t.t("about.layerOne.eyebrow")),
            _section("layer-2", t.t("about.layerTwo.title"), [
                html.P(t.t("about.layerTwo.intro"), className=prose),
                html.Ol([html.Li([html.Span(t.t("about.layerTwo.step", n=i + 1), className="label-caps text-indigo-label nowrap"), html.P(step, className="text-small relaxed text-ink-2")], className="step-card row-card")
                         for i, step in enumerate(t.items("about.layerTwo.steps"))], className="grid-2 gap-4"),
            ], eyebrow=t.t("about.layerTwo.eyebrow")),
            _section("highlights", t.t("about.highlights.title"), [
                html.Div([_figure(ABOUT_HIGHLIGHTS[fid], fig["alt"], fig["caption"]) for fid, fig in t.entries("about.highlights.figures")], className="grid-2 gap-4 items-start"),
            ]),
            _section("replicability", t.t("about.replicability.title"), paragraphs("about.replicability.paragraphs")),
            _section("limitations", t.t("about.limitations.title"), [
                html.P(t.t("about.limitations.intro"), className=prose),
                html.Div([html.Div([html.H3(item["title"], className="text-body font-semibold text-ink"), html.P(item["body"], className="text-small relaxed text-ink-3 mt-1-5")], className="step-card")
                          for _, item in t.entries("about.limitations.items")], className="grid-2 gap-4"),
                html.P(t.t("about.limitations.principle"), className="principle"),
            ]),
            _section("findings", t.t("about.findings.title"), [
                html.P(t.t("about.findings.intro"), className=prose),
                html.Div(html.Table([
                    html.Thead(html.Tr([html.Th(h, scope="col") for h in findings["columns"].values()])),
                    html.Tbody([html.Tr([html.Th(t.t_or(f"data.countries.{iso3}", iso3), scope="row"), html.Td(row["focus"]), html.Td(row["levelOne"]),
                                         html.Td(row["levelTwo"]), html.Td(row["strategies"]), html.Td(row["topic"])]) for iso3, row in findings["rows"].items()]),
                ], className="findings-table"), className="table-card"),
                html.Div([html.P(note) for note in findings["notes"].values()], className="findings-notes"),
                html.Div([html.Article([html.H3(story["title"], className="text-body font-semibold text-ink"), html.P(story["p1"], className="text-small relaxed text-ink-3 mt-2"),
                                        html.P(story["p2"], className="text-small relaxed text-ink-3 mt-2")], className="step-card")
                          for story in findings["stories"].values()], className="grid-3 gap-4"),
                html.Div([
                    _figure(ABOUT_FIGURES["recommendations"], t.t("about.findings.figures.recommendations.alt"), t.t("about.findings.figures.recommendations.caption")),
                    _figure(ABOUT_FIGURES["projects"], t.t("about.findings.figures.projects.alt"), t.t("about.findings.figures.projects.caption")),
                ], className="grid-2 gap-4 items-start"),
            ]),
            _section("contacts", t.t("about.contacts.title"), paragraphs("about.contacts.paragraphs")),
            _section("references", t.t("about.referencesTitle"), [html.Ul([html.Li(r) for r in ABOUT_REFERENCES], className="bullets max-w-3xl")]),
        ],
        className="doc-page gap-10",
    )
    return {"content": content, "title": t.t("about.metaTitle")}
