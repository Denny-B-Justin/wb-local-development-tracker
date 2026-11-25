from __future__ import annotations

from typing import Any

from dash import html

import constants
from services import catalog, model as model_module, security, state
from services.state import Request
from utils.components import button, card, cx, icon, link, page_header, segmented, share_button, view_select, widget

from .pages_constants import COMPARE_BASELINES, COMPARE_SIZES, COMPARE_VIEWS

SIZE_LABELS = {"population": "compare.size.population", "area": "compare.size.area", "none": "compare.size.none"}


def metrics(t) -> list[dict[str, Any]]:
    scores = t.t("compare.groups.scores")
    out = [{"value": "composite", "label": t.t("data.pillars.composite"), "csv": "PIL Aggregate", "group": scores}]
    out += [{"value": p, "label": t.t(f"data.pillars.{p}"), "csv": f"{p.capitalize()} Score", "group": scores} for p in catalog.PILLARS]
    out += [{"value": c.id, "label": t.t_or(f"data.indicators.{c.id}", c.label), "csv": f"{c.label} Score",
             "group": t.t("compare.groups.indicators", pillar=t.t(f"data.pillars.{c.pillar}"))} for c in catalog.COMPONENTS]
    return out


def unit_search(req: Request, rows: list[dict[str, Any]], exclude: list[str], disabled: bool, units_plural: str) -> html.Details:
    t = req.t
    units = [[r["id"], r["name"], state.area_line(req, r["areas"])] for r in rows if r["id"] not in exclude]
    return html.Details(
        [
            html.Summary([icon("plus", "size-3-5"), t.t("compare.tray.add")], className=cx("tray-add", disabled and "is-disabled"),
                         title=t.t("compare.tray.full", max=constants.COMPARE_MAX) if disabled else None),
            html.Div(widget("unit-search", {"units": units, "param": "compare", "mode": "append", "placeholder": t.t("compare.tray.search", units=units_plural),
                                            "empty": t.t("compare.tray.noMatches"), "limit": 8}), className="dd-panel dd-start search-panel"),
        ],
        className=cx("dd tray-add-dd", disabled and "is-disabled"),
    )


def side_by_side(req: Request, selected: list[dict[str, Any]], baselines: list[dict[str, Any]], units_singular: str, units_plural: str):
    t = req.t
    if not selected:
        return card(t.t("compare.table.empty", max=constants.COMPARE_MAX, units=units_plural), "empty-card")
    columns = [{"kind": "unit", **r} for r in selected] + [{"kind": "baseline", **b} for b in baselines]

    def value(column, metric):
        return model_module.metric_value(column, metric) if column["kind"] == "unit" else model_module.score_set_value(column["scores"], metric)

    def score_row(metric, label, depth=0, strong=False, group=None):
        values = [value(c, metric) for c in columns]
        unit_values = [v for v in values[: len(selected)] if v is not None]
        best = max(unit_values) if len(selected) > 1 and unit_values and len(set(unit_values)) > 1 else None
        cells = []
        for index, v in enumerate(values):
            is_best = best is not None and index < len(selected) and v == best
            cells.append(html.Td([t.score(v, 1), html.Span(t.t("compare.table.highest"), className="sr-only") if is_best else None],
                                 className=cx("num", index >= len(selected) and "text-muted", is_best and "is-best", strong and "font-semibold")))
        return html.Tr([html.Th(label, scope="row", className=cx("sbs-label", depth and "is-child", strong and "is-strong")), *cells],
                       className=cx("sbs-row", depth and "is-child"), **({"data-group": group} if group else {}))

    head = [html.Th([t.t("compare.table.indicator"),
                     html.Button(t.t("compare.table.expandAll"), type="button", className="sbs-toggle-all js-expand-all",
                                 **{"data-expand": t.t("compare.table.expandAll"), "data-collapse": t.t("compare.table.collapseAll")})],
                    scope="col", className="sbs-head-label")]
    for c in columns:
        if c["kind"] == "unit":
            head.append(html.Th([
                html.Div([link(c["name"], req.href("profile", unit=c["id"]), "sbs-unit"),
                          html.Button(icon("x", "size-3-5"), type="button", className="sbs-remove js-compare-toggle", **{"data-unit": c["id"], "aria-label": t.t("common.remove", name=c["name"])})],
                         className="sbs-unit-head"),
                html.Div(state.area_line(req, c["areas"]), className="text-meta text-muted font-normal"),
            ], scope="col", className="sbs-col"))
        else:
            head.append(html.Th(c["label"], scope="col", className="sbs-col sbs-base"))

    def plain_row(label, render, last=False):
        return html.Tr([html.Th(label, scope="row", className="sbs-label"), *[html.Td(render(c) if c["kind"] == "unit" else "–", className="num text-muted nowrap") for c in columns]],
                       className=cx("sbs-row", last and "is-last"))

    body = [
        plain_row(t.t("compare.table.rank"), lambda c: t.count(c["rank"]) if c.get("rank") is not None else "–"),
        plain_row(t.t("compare.table.population"), lambda c: t.count(c["population"]) if c.get("population") is not None else "–"),
        plain_row(t.t("compare.table.landArea"), lambda c: t.area(c.get("areaKm2")), last=True),
        score_row("composite", t.t("compare.table.composite"), strong=True),
    ]
    for pillar in catalog.PILLARS:
        toggle = html.Button([icon("chevron-right", "size-4 sbs-chev"), t.t(f"data.pillars.{pillar}")], type="button", className="sbs-pillar js-group-toggle",
                             **{"data-group": pillar, "aria-expanded": "false"})
        body.append(score_row(pillar, toggle))
        body += [score_row(c.id, t.t_or(f"data.indicators.{c.id}", c.label), depth=1, group=pillar) for c in catalog.components_of(pillar)]
    return card([
        html.Table([html.Caption(t.t("compare.table.caption", units=units_plural), className="sr-only"), html.Thead(html.Tr(head)), html.Tbody(body)], className="sbs-table js-sbs"),
        html.P(t.t("compare.table.note", unit=units_singular), className="card-note"),
    ], "overflow-x-auto")


def render(req: Request) -> dict:
    t = req.t
    data = req.model
    names = state.localized_country(req.country, t)
    unit_plural = names["local"]["plural"].lower()
    unit_singular = names["local"]["singular"].lower()
    top = names["filters"][0]
    options = metrics(t)
    valid = {o["value"] for o in options}
    x = security.choice(req.params.get("x"), valid, "prosperity")
    y = security.choice(req.params.get("y"), valid, "infrastructure")
    size = security.choice(req.params.get("size"), COMPARE_SIZES, "population")
    base_raw = req.params.get("base")
    shown = [b for b in (base_raw.split(",") if base_raw is not None else COMPARE_BASELINES) if b in COMPARE_BASELINES]
    if base_raw == "none":
        shown = []
    view = security.choice(req.params.get("view"), COMPARE_VIEWS, "scatter")
    label_of = {o["value"]: o["label"] for o in options}

    rows = [r for r in data.rows(req.year) if r["scored"]]
    context_rows = [r for r in rows if model_module.in_context(r, req.filters)]
    plotted = context_rows + [r for r in rows if r["id"] in req.compare and not model_module.in_context(r, req.filters)]
    points = []
    for r in plotted:
        px, py = model_module.metric_value(r, x), model_module.metric_value(r, y)
        if px is None or py is None:
            continue
        size_value = r["population"] if size == "population" else r["areaKm2"] if size == "area" else None
        points.append([r["id"], r["name"], state.area_line(req, r["areas"]), px, py, size_value, 1 if r["id"] in req.compare else 0])
    context_ids = {r["id"] for r in context_rows}
    missing = len(context_rows) - sum(1 for p in points if p[0] in context_ids)

    national = data.baseline(req.year, {}, None)
    area_base = data.baseline(req.year, req.filters, req.area) if req.area else None
    area_label = state.baseline_label(t, area_base) if area_base else None
    baselines = []
    if area_base and "area" in shown:
        baselines.append({"key": "area", "label": area_label, "x": model_module.score_set_value(area_base["scores"], x), "y": model_module.score_set_value(area_base["scores"], y), "tone": "area"})
    if "national" in shown:
        baselines.append({"key": "national", "label": t.t("compare.nationalAvg"), "x": model_module.score_set_value(national["scores"], x), "y": model_module.score_set_value(national["scores"], y), "tone": "national"})

    def base_href(key: str) -> str:
        nxt = [b for b in shown if b != key] if key in shown else [*shown, key]
        ordered = [b for b in COMPARE_BASELINES if b in nxt]
        return req.with_params(base=None if ordered == list(COMPARE_BASELINES) else (",".join(ordered) or "none"))

    def chip(label, key, active, disabled=False, title=None):
        cls = cx("base-chip", active and "is-active", disabled and "is-disabled")
        if disabled:
            return html.Button(label, type="button", className=cls, disabled=True, title=title)
        return link(label, base_href(key), cls, **{"aria-pressed": "true" if active else "false"})

    metric_options = [{**o, "href": req.with_params(**{"x": o["value"]})} for o in options]
    controls = html.Div(
        [
            view_select(t, "X", x, metric_options),
            view_select(t, "Y", y, [{**o, "href": req.with_params(y=o["value"])} for o in options]),
            view_select(t, t.t("compare.size.label"), size, [{"value": s, "label": t.t(SIZE_LABELS[s]), "href": req.with_params(size=None if s == "population" else s)} for s in COMPARE_SIZES]),
            html.Div([
                html.Span(t.t("compare.baselines"), className="label-caps text-muted"),
                chip(area_label or t.t("baseline.area", area=top["singular"]), "area", bool(area_base) and "area" in shown, disabled=not area_base,
                     title=None if area_base else t.t("compare.areaBaselineHint", level=top["singular"].lower())),
                chip(t.t("compare.nationalAvg"), "national", "national" in shown),
            ], className="base-chips", role="group", **{"aria-label": t.t("compare.baselines")}),
            segmented(t.t("compare.view.label"), [(v, t.t(f"compare.view.{v}"), req.with_params(view=None if v == "scatter" else v)) for v in COMPARE_VIEWS], view),
        ],
        className="header-controls compare-controls",
    )

    selected_rows = [r for i in req.compare for r in rows if r["id"] == i]
    single = selected_rows[0] if len(selected_rows) == 1 else None
    tray_items = [
        html.Li([
            html.Div([link(r["name"], req.href("profile", unit=r["id"]), "tray-name"), html.Span(state.area_line(req, r["areas"]), className="tray-area", title=state.area_line(req, r["areas"]))],
                     className="tray-text"),
            html.Button(icon("x", "size-3-5"), type="button", className="tray-remove js-compare-toggle", **{"data-unit": r["id"], "aria-label": t.t("common.remove", name=r["name"])}),
        ], className="tray-chip")
        for r in selected_rows
    ]
    brief_button = (
        button([icon("sparkles"), html.Span(t.t("compare.tray.briefFor", name=single["name"]), className="truncate")], "primary", req.href("brief", scope=single["id"]))
        if single else
        button([icon("sparkles"), t.t("compare.tray.briefForSelection")], "primary", disabled=True,
               title=t.t("compare.tray.selectToBrief") if not selected_rows else t.t("compare.tray.oneUnitOnly"))
    )
    tray = html.Section(
        [
            html.Div([html.H2(t.t("compare.tray.selected", count=len(selected_rows), max=constants.COMPARE_MAX), className="label-caps text-muted"),
                      html.Button(t.t("compare.tray.clear"), type="button", className="tray-clear js-compare-clear") if len(selected_rows) > 1 else None], className="tray-head"),
            html.P(t.t("compare.tray.empty", units=unit_plural), className="text-small text-muted") if not selected_rows else None,
            html.Ul(tray_items, className="tray-list"),
            unit_search(req, rows, req.compare, len(req.compare) >= constants.COMPARE_MAX, unit_plural),
            html.Div([
                button([icon("table-2" if view == "scatter" else "chart-scatter"), t.t("compare.tray.table") if view == "scatter" else t.t("compare.tray.scatterplot")],
                       "secondary", req.with_params(view="table" if view == "scatter" else None)),
                brief_button,
                html.P(t.t("compare.tray.oneUnitNote", unit=unit_singular), className="text-meta text-faint") if len(selected_rows) > 1 else None,
            ], className="tray-foot"),
        ],
        className="tray", **{"aria-label": t.t("compare.tray.label")},
    )

    summary = data.context_summary(req.year, req.filters)
    full = len(req.compare) >= constants.COMPARE_MAX
    if view == "scatter":
        hint = t.t("compare.trayFull", max=constants.COMPARE_MAX) if full else t.t("compare.clickToSelect")
        if missing > 0:
            hint += f" {t.tp('compare.missing', missing)}"
        size_label = None if size == "none" else t.t(SIZE_LABELS[size])
        body = html.Section(
            [
                html.Div([html.Span(state.context_line(req, summary["unitCount"]), className="text-body text-muted"), html.Span(hint, className="text-meta text-muted")], className="scatter-head"),
                widget("scatter", {
                    "points": points, "baselines": baselines, "x": label_of[x], "y": label_of[y], "size": size_label, "sizeKind": size, "full": full,
                    "openHref": req.href("profile", unit="__ID__"),
                    "text": {"axis": t.t("compare.chart.axis", label="{label}"), "remove": t.t("compare.chart.clickToRemove"), "select": t.t("compare.chart.clickToSelect"),
                             "aria": (t.tp("compare.chart.ariaSized", len(points), x=label_of[x], y=label_of[y], size=size_label.lower()) if size_label else t.tp("compare.chart.aria", len(points), x=label_of[x], y=label_of[y])),
                             "decimal": "," if req.lang == "fr" else ".", "group": " " if req.lang == "fr" else ","},
                }, cls="scatter-widget") if points else html.P(t.t("compare.noPoints", units=unit_plural), className="empty-note"),
            ],
            className="card scatter-card", **{"aria-label": t.t("compare.scatterplot")},
        )
    else:
        bases = ([{"key": "area", "label": area_label, "scores": area_base["scores"]}] if area_base else []) + [{"key": "national", "label": t.t("compare.nationalAvg"), "scores": national["scores"]}]
        body = side_by_side(req, selected_rows, bases, unit_singular, unit_plural)

    export_query = state.build({"country": req.country.slug, "year": req.year, **{k: v for k, v in req.filters.items() if v}, "x": x, "y": y, **({"compare": ",".join(req.compare)} if req.compare else {})})
    actions = [
        share_button(t),
        html.A([icon("download"), t.t("common.exportCsv")], href=f"api/export/compare.csv{export_query}", className=cx("btn btn-secondary btn-sm", not context_rows and "is-disabled"), download=""),
    ]
    content = [
        page_header(t.t("compare.heading", units=unit_plural), t.t("compare.subtitle", level=top["singular"].lower()), controls),
        html.Div([tray, html.Div(body, className="compare-main")], className=cx("compare-row", view == "scatter" and "is-scatter")),
    ]
    return {"content": content, "actions": actions, "title": t.t("compare.title")}
