from __future__ import annotations

import json
from typing import Any

from dash import dcc, html

from services import security, state
from ai import parse as ai_parse
from ai import pipeline
from services.state import Request
from utils.components import badge, button, card, card_label, card_title, cx, icon, link, page_header, rich, widget

from .data_trust import describe
from .pages_constants import BRIEF_OUTPUTS, SCORE_THEMES

OUTPUT_LABELS = {"narrative": "brief.outputs.narrative", "alignment": "brief.outputs.alignment", "swot": "brief.outputs.swot", "recommendations": "brief.outputs.recommendations"}


def selection(req: Request) -> tuple[dict[str, Any] | None, str]:
    theme = security.choice(req.params.get("score"), SCORE_THEMES, "prosperity")
    unit_id = security.unit_id(req.params.get("scope"))
    row = req.model.row(req.year, unit_id) if unit_id else None
    return (row if row and row["scored"] else None), theme


def _check_row(label: str, hint: str | None, checked: bool, disabled: bool, key: str | None = None, cls: str = "") -> html.Label:
    return html.Label(
        [
            html.Span(icon("check-bold", "size-3"), className=cx("check-box", checked and "is-checked", disabled and "is-disabled"), **{"aria-hidden": "true"}),
            html.Span([html.Span(label, className="check-label"), html.Span(hint, className="check-hint") if hint else None], className="flex-col"),
        ],
        className=cx("check-row", disabled and "is-disabled", cls), role="checkbox", tabIndex="-1" if disabled else "0",
        **{"aria-checked": "true" if checked else "false", "aria-disabled": "true" if disabled else "false", **({"data-key": key} if key else {})},
    )


def _cite(t, item: dict[str, Any], sources: list[dict[str, Any]], stage: str | None = None):
    numbers = ai_parse.citation_numbers(item["sources"], sources, stage)
    if not numbers:
        return None
    parts: list[Any] = []
    for index, number in enumerate(numbers):
        parts += ["," if index else "", html.A(str(number), href=f"#source-{number}", className="cite-link")]
    return html.Sup([*parts, html.Span(t.t("brief.output.sources", sources="; ".join(item["sources"])), className="sr-only")], className="cite", title="; ".join(item["sources"]))


def _bullets(t, items, sources, stage=None) -> html.Ul:
    return html.Ul([html.Li([item["text"], _cite(t, item, sources, stage)]) for item in items], className="brief-bullets")


def _skeleton(t, title: str):
    return card([html.Div([card_title(title), html.Span(t.t("brief.output.generating"), className="text-meta font-semibold text-indigo-700")], className="card-head-center"),
                 *[html.Div(className="skeleton", style={"width": f"{w}%"}) for w in (92, 80, 86, 64)]], "card-pad stack gap-3", **{"aria-busy": "true"})


def _stage_error(t, title: str, result: dict[str, Any]):
    message = result.get("errorMessage") or t.t("brief.output.stageFailed")
    if message.startswith("AI generation limit reached"):
        message = t.t("brief.output.rateLimited")
    elif message.startswith("AI generation is turned off"):
        message = t.t("brief.blocked.off")
    network = any(k in message.lower() for k in ("network", "timed out", "could not be downloaded", "connection"))
    return card([card_title(title), html.P(message, className="text-small text-warning mt-1-5", role="alert"),
                 html.P(t.t("brief.output.networkHint"), className="text-meta text-muted mt-1") if network else None], "card-pad stage-error")


def _narrative(t, result, sources):
    blocks = ai_parse.narrative(result.get("renderedOutput") or "")
    out: list[Any] = [card_title(t.t("brief.sections.narrative"))]
    for index, block in enumerate(blocks):
        if block["kind"] == "heading":
            if index:
                out.append(html.H3(block["text"], className="brief-h3"))
        elif block["kind"] == "bullet":
            out.append(html.P([block["item"]["text"], _cite(t, block["item"], sources, "indicator_narrative")], className="brief-p brief-bullet"))
        else:
            out.append(html.P([block["item"]["text"], _cite(t, block["item"], sources, "indicator_narrative")], className="brief-p"))
    return card(out, "card-pad stack gap-2-5")


def _alignment(t, result, sources):
    parts = ai_parse.alignment(result.get("renderedOutput") or "")
    groups = [(t.t("brief.output.alignmentSummary"), parts["summary"]), (t.t("brief.output.strongest"), parts["strengths"]),
              (t.t("brief.output.gaps"), parts["gaps"]), (t.t("brief.output.implications"), parts["implications"])]
    return card([card_title(t.t("brief.sections.alignment")),
                 html.Div([html.Section([card_label(label, "mb-2"), _bullets(t, items, sources)]) for label, items in groups if items], className="grid-2 gap-brief xl-only")],
                "card-pad stack gap-4")


def _swot(t, result, sources):
    swot = ai_parse.swot(result.get("renderedOutput") or "")
    quadrants = (("strengths", "brief.output.strengths", "swot-s"), ("weaknesses", "brief.output.weaknesses", "swot-w"),
                 ("opportunities", "brief.output.opportunities", "swot-o"), ("threats", "brief.output.threats", "swot-t"))
    return html.Section([
        html.Div([card([html.H3(t.t(label), className="card-title mb-2"), _bullets(t, swot[key], sources)], f"swot-card {tone}") for key, label, tone in quadrants], className="swot-grid"),
        card([card_label(t.t("brief.output.missing"), "mb-2"), _bullets(t, swot["missing"], sources)], "swot-card") if swot["missing"] else None,
    ], className="stack gap-3", **{"aria-label": t.t("brief.output.swotLabel")})


def _recommendations(t, result, sources):
    recs = ai_parse.recommendations(result.get("renderedOutput") or "")
    if not recs:
        return card([card_title(t.t("brief.sections.recommendations")), html.Pre(result.get("renderedOutput"), className="brief-pre")], "card-pad stack gap-4")
    items = []
    for rec in recs:
        groups = [html.Section([card_label(label, "mb-1-5"), _bullets(t, entries, sources)]) for label, entries in
                  ((t.t("brief.output.dataJustification"), rec["data"]), (t.t("brief.output.planJustification"), rec["plan"]), (t.t("brief.output.risks"), rec["risks"])) if entries]
        if rec["actions"]:
            groups.append(html.Section([card_label(t.t("brief.output.actions"), "mb-1-5"), html.Ol([html.Li(a) for a in rec["actions"]], className="brief-actions")]))
        items.append(html.Li([
            html.Span(str(rec["rank"]), className="rec-rank"),
            html.Div([html.H3(rec["title"], className="text-body font-semibold text-ink"), html.P(rec["description"], className="brief-p") if rec["description"] else None,
                      html.Div(groups, className="grid-2 gap-rec lg-only")], className="rec-body"),
        ], className="rec-item"))
    return card([card_title(t.t("brief.sections.recommendations")), html.Ol(items, className="rec-list")], "card-pad stack gap-4")


def _web(t, result, sources):
    skipped = (result.get("structuredOutput") or {}).get("skipped")
    web = ai_parse.web_context(result.get("renderedOutput") or "")
    groups = [(t.t("brief.output.takeaways"), web["takeaways"]), (t.t("brief.output.signals"), web["signals"]), (t.t("brief.output.risks"), web["risks"]), (t.t("brief.output.local"), web["local"])]
    groups = [g for g in groups if g[1]]
    body = html.P(result.get("renderedOutput"), className="text-small text-muted") if skipped or not groups else [html.Section([card_label(label, "mb-1-5"), _bullets(t, items, sources, "web_context_search")]) for label, items in groups]
    return html.Details([html.Summary([t.t("brief.sections.webContext"), html.Span(t.t("brief.output.show"), className="web-show")], className="web-summary"),
                         html.Div(body, className="stack gap-3 mt-3")], className="web-card")


def _source_list(t, sources):
    items = []
    for source in sources:
        links = [html.A([l["label"], icon("external-link", "size-3")], href=l["url"], target="_blank", rel="noopener noreferrer", className="text-link inline-flex") if l["url"] else html.Span(l["label"])
                 for l in source["links"]]
        items.append(html.Li([html.Span(str(source["number"]), className="src-num"), html.Span([html.Span(source["label"], className="text-ink-2"), *links], className="flex-col gap-0-5")],
                             id=f"source-{source['number']}", className="src-item"))
    return html.Footer([html.Ol(items, className="stack gap-1-5"), html.P(t.t("brief.output.screening"), className="font-semibold text-ink-3 mt-1"), html.P(t.t("brief.output.disclaimer"))], className="brief-sources")


def _stepper(t, stages: list[str], results: dict[str, dict], running: str | None):
    items = []
    for group_id, label, group in pipeline.STEP_GROUPS:
        members = [s for s in group if s in stages]
        if not members:
            continue
        done = all((results.get(s) or {}).get("status") == "completed" or (s == "web_context_search" and results.get(s)) for s in members)
        failed = any((results.get(s) or {}).get("status") == "failed" and s != "web_context_search" for s in members)
        active = running in members
        tone = "is-done" if done else "is-active" if active else "is-failed" if failed else ""
        glyph = icon("check-bold", "size-3") if done else icon("x", "size-3") if failed else icon("loader-circle", "size-3 spin") if active else None
        status = t.t("brief.steps.done") if done else t.t("brief.steps.failed") if failed else t.t("brief.steps.inProgress") if active else t.t("brief.steps.notRun")
        items.append(html.Li([html.Span(className="step-line", **{"aria-hidden": "true"}) if items else None,
                              html.Span([glyph, t.t_or(f"brief.steps.{group_id}", label), "…" if active else "", html.Span(status, className="sr-only")], className=cx("step-pill", tone))], className="step"))
    return html.Ol(items, className="stepper", **{"aria-label": t.t("brief.steps.label")})


def output(req: Request, run: dict[str, Any] | None = None) -> list[Any]:
    t = req.t
    row, theme = selection(req)
    run = run or {}
    if row is None:
        return [card(rich(t.t("brief.chooseUnit"), {"b": lambda s: html.Span(s, className="font-semibold")}), "empty-card brief-empty")]
    context = pipeline.build_context(req.model, row["id"], req.year, theme)
    results = pipeline.load_cached(context)
    errors = {k: v for k, v in (run.get("errors") or {}).items() if k in pipeline.STAGES and isinstance(v, str)}
    for stage, message in errors.items():
        if stage not in results:
            results[stage] = pipeline.failure(stage, message[:400])
    planned = [s for s in (run.get("planned") or []) if s in pipeline.STAGES]
    running = run.get("running") if run.get("running") in pipeline.STAGES else None
    default_stages = pipeline.plan_stages(list(BRIEF_OUTPUTS), pipeline.availability()["web"], context["localPlanAvailable"])
    stages = planned or default_stages
    has = lambda s: (results.get(s) or {}).get("status") == "completed"  # noqa: E731
    failed = lambda s: results.get(s) if (results.get(s) or {}).get("status") == "failed" else None  # noqa: E731
    pending = lambda s: running is not None and s in planned and not has(s)  # noqa: E731
    has_brief = any(has(s) for s in pipeline.STAGES)
    score_label = t.t("metrics.pillarScore", pillar=t.t(f"data.pillars.{theme}")) if req.lang != "en" else pipeline.catalog.SCORE_LABELS[f"{theme}_score"]
    sources = ai_parse.build_sources(results, t.t("brief.sourceScores", country=state.localized_country(req.country, t)["name"], key=req.country.release_key(req.year)))
    updated = sorted(r["updatedAt"] for r in results.values() if r.get("updatedAt") and r.get("status") == "completed")
    area = state.area_line(req, row["areas"])
    meta = (t.t("brief.metaUpdated", area=area, score=score_label, year=str(req.year), key=req.country.release_key(req.year), date=t.date(updated[-1], short=True))
            if updated else t.t("brief.meta", area=area, score=score_label, year=str(req.year), key=req.country.release_key(req.year)))
    md_query = state.build({"country": req.country.slug, "year": req.year, "scope": row["id"], "score": theme})
    out: list[Any] = [
        html.Div([
            _stepper(t, stages, results, running),
            html.Div([button([icon("printer"), t.t("brief.exportPdf")], "secondary", cls="js-print", disabled=not has_brief),
                      html.A([icon("download"), t.t("brief.markdown")], href=f"api/brief/export.md{md_query}", download="", className=cx("btn btn-ghost", not has_brief and "is-disabled"))],
                     className="flex gap-2"),
        ], className="brief-toolbar print-hidden"),
        html.Header([
            html.H1(t.t("brief.heading", name=row["name"]), className="brief-title"),
            html.P(meta, className="text-small text-muted mt-1"),
            link(t.t("brief.openProfile"), req.href("profile", unit=row["id"]), "text-small text-link mt-1 inline-block print-hidden"),
        ]),
    ]
    if not has_brief and not running:
        out.append(card([icon("file-text", "size-6 text-faint"), html.P(t.t("brief.noBrief", name=row["name"], score=score_label, year=str(req.year))),
                         html.P(t.t("brief.chooseOutputs"), className="text-meta js-blocked-copy")], "brief-none"))
    sections = (("indicator_narrative", "brief.sections.narrative", _narrative), ("swot_analysis", "brief.sections.swot", _swot),
                ("investment_recommendations", "brief.sections.recommendations", _recommendations), ("plan_alignment", "brief.sections.alignment", _alignment))
    for stage, title_key, renderer in sections[:1]:
        out.append(renderer(t, results[stage], sources) if has(stage) else _skeleton(t, t.t(title_key)) if pending(stage) else _stage_error(t, t.t(title_key), failed(stage)) if failed(stage) else None)
    for stage, key in (("national_plan_context", "brief.sections.nationalPlan"), ("province_plan_context", "brief.sections.localPlan")):
        if failed(stage):
            out.append(_stage_error(t, t.t(key), failed(stage)))
    for stage, title_key, renderer in sections[1:]:
        out.append(renderer(t, results[stage], sources) if has(stage) else _skeleton(t, t.t(title_key)) if pending(stage) else _stage_error(t, t.t(title_key), failed(stage)) if failed(stage) else None)
    if has("web_context_search"):
        out.append(_web(t, results["web_context_search"], sources))
    elif failed("web_context_search"):
        out.append(_stage_error(t, t.t("brief.sections.webContext"), failed("web_context_search")))
    if has_brief:
        out.append(_source_list(t, sources))
    cached = [s for s in pipeline.STAGES if has(s)]
    return [html.Div(out, className="stack gap-5", **{"data-cached": json.dumps(cached), "data-local-plan": "1" if context["localPlanAvailable"] else "0"})]


def render(req: Request) -> dict:
    t = req.t
    names = state.localized_country(req.country, t)
    if not req.country.features.ai:
        return {"content": [page_header(t.t("brief.title"), t.t("brief.subtitle", unit=names["local"]["singular"].lower())), html.P(names["ai_message"], className="text-small text-muted")],
                "title": t.t("brief.title")}
    row, theme = selection(req)
    available = pipeline.availability()
    context = pipeline.build_context(req.model, row["id"], req.year, theme) if row else None
    local_plan = bool(context and context["localPlanAvailable"])
    plan_label = None
    if row and context:
        plan_label = t.t("brief.planLabel.top" if req.country.plan_source_level == "top" else "brief.planLabel.local", name=context["localPlanUnitName"])
    blocked = (t.t("brief.blocked.chooseUnit") if not row else t.t("brief.blocked.noKey") if not available["ai"]
               else t.t("brief.blocked.off") if not available["enabled"] else None)
    themes = []
    for key in SCORE_THEMES:
        full = t.t("metrics.pillarScore", pillar=t.t(f"data.pillars.{key}")) if req.lang != "en" else pipeline.catalog.SCORE_LABELS[f"{key}_score"]
        short = t.t(f"data.pillars.{key}")
        themes.append(link(short, req.with_params(score=None if key == "prosperity" else key), cx("theme-item", key == theme and "is-active"), title=full,
                           role="radio", **{"aria-checked": "true" if key == theme else "false"}))
    scope_units = [[r["id"], r["name"], state.area_line(req, r["areas"])] for r in req.model.rows(req.year) if r["scored"]]
    scope = html.Details([
        html.Summary([html.Span([html.Span(row["name"] if row else t.t("brief.scopePicker.choose"), className="scope-name"),
                                 html.Span(state.area_line(req, row["areas"]), className="scope-area") if row else None], className="min-w-0"),
                      icon("chevron-down", "size-4 text-muted shrink-0")], className="scope-trigger"),
        html.Div(widget("unit-search", {"units": scope_units, "param": "scope", "mode": "set", "placeholder": t.t("brief.scopePicker.placeholder"),
                                        "empty": t.t("brief.scopePicker.noMatches"), "limit": 30, "current": row["id"] if row else None}), className="dd-panel dd-start search-panel"),
    ], className="dd scope-picker")
    readiness = next((i for i in req.model.trust(req.year)["items"] if i["key"] == "aiReadiness"), None)
    readiness_row = None
    if readiness:
        status = readiness["status"]
        readiness_row = html.Div([badge(t.t("trust.ready") if status == "ready" else t.t("trust.partial") if status == "partial" else t.t("brief.notReady"),
                                        "success" if status == "ready" else "warning" if status == "partial" else "neutral"),
                                  html.Span(t.t("brief.readiness", detail=describe(req, readiness)["detail"]))], className="readiness-row")
    outputs = [_check_row(t.t(OUTPUT_LABELS[o]), None, True, False, key=f"output:{o}", cls="js-output") for o in BRIEF_OUTPUTS]
    setup = card([
        html.H2(t.t("brief.setup"), className="card-title"),
        html.Section([card_label(t.t("brief.scope")), scope, html.Div(themes, className="theme-switch", role="radiogroup", **{"aria-label": t.t("brief.themeLabel")})], className="stack gap-2"),
        html.Section([
            card_label(t.t("brief.evidence")),
            _check_row(t.t("brief.scores"), t.t("brief.alwaysUsed"), True, True),
            _check_row(plan_label or t.t("brief.localPlan"), t.t("brief.noPlan") if row and not local_plan else t.t("brief.usedBy"), local_plan, True, key="evidence:local"),
            _check_row(req.country.national_plan.title if req.country.national_plan else t.t("brief.nationalPlan"), t.t("brief.usedBy"), True, True, key="evidence:national"),
            _check_row(t.t("brief.webSearch"), t.t("brief.webSearchHint") if available["web"] else t.t("brief.notConfigured"), available["web"], not available["web"], key="web"),
            _check_row(t.t("brief.upload"), t.t("brief.comingSoon"), False, True),
        ], className="stack gap-2"),
        html.Section([card_label(t.t("brief.outputsLabel")), *outputs], className="stack gap-2"),
        html.Div([
            html.Button([icon("sparkles", "gen-icon"), icon("refresh-cw", "regen-icon"), icon("loader-circle", "run-icon spin"), html.Span(t.t("brief.generate"), className="gen-label")],
                        type="button", className="btn btn-primary js-generate", disabled=bool(blocked)),
            html.P(blocked, className="text-meta text-muted js-blocked") if blocked else html.P(className="text-meta text-muted js-blocked", hidden=True),
            html.P(t.t("brief.regenerateNote"), className="text-meta text-faint js-regen-note", hidden=True),
            html.P(t.t("brief.englishOnly"), className="text-meta text-muted") if req.lang != "en" else None,
        ], className="stack gap-2"),
        readiness_row,
    ], "brief-setup print-hidden", tag=html.Section)
    config = {
        "blocked": blocked, "web": available["web"], "localPlan": local_plan, "scope": f"{row['id'] if row else ''}:{theme}:{req.year}",
        "text": {"generate": t.t("brief.generate"), "regenerate": t.t("brief.regenerate"), "generating": t.t("brief.generating"), "noOutputs": t.t("brief.blocked.noOutputs"),
                 "needsPlan": t.t("brief.needsPlan"), "implied": t.t("brief.impliedOutput"), "usedBy": t.t("brief.usedBy"), "noPlan": t.t("brief.noPlan"),
                 "chooseOutputs": t.t("brief.chooseOutputs")},
    }
    content = [
        html.Div(page_header(t.t("brief.title"), t.t("brief.subtitle", unit=names["local"]["singular"].lower())), className="print-hidden"),
        html.Div([setup, html.Div(output(req), id="brief-output", className="brief-main")], className="brief-grid", **{"data-widget": "brief", "data-config": json.dumps(config)}),
        dcc.Store(id="brief-run", data=None),
    ]
    return {"content": content, "title": t.t("brief.title")}


def register(app) -> None:
    from dash import Input, Output, State, no_update

    @app.callback(Output("brief-output", "children"), Input("brief-run", "data"), State("url", "search"), prevent_initial_call=True)
    def _refresh(run, search):
        req = state.parse(search)
        if req.page != "brief" or req.model is None:
            return no_update
        return output(req, run if isinstance(run, dict) else None)
