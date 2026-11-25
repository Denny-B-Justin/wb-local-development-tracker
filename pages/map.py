from __future__ import annotations

from dash import html

from services import catalog, model as model_module, security, state
from services.state import Request
from utils.components import (
    badge, button, card_label, cx, diverging_bars, icon, link, page_header, pillar_bars, ramp_legend, rich,
    segmented, share_button, view_select, widget,
)

from .pages_constants import MAP_PILLARS

ALL = "__all__"


def metric_label(t, metric: str) -> str:
    if metric == "composite":
        return t.t("metrics.compositeScore")
    if catalog.is_pillar(metric):
        return t.t("metrics.pillarScore", pillar=t.t(f"data.pillars.{metric}"))
    component = catalog.COMPONENT_BY_ID[metric]
    return t.t_or(f"data.indicators.{metric}", component.label)


def drawer(req: Request, selected: str | None, pillar: str, indicator: str | None) -> html.Aside:
    t = req.t
    names = state.localized_country(req.country, t)
    unit_label = names["local"]["singular"].lower()
    unit_plural = names["local"]["plural"].lower()
    if not selected:
        return html.Aside(html.Div(html.P(t.t("map.drawer.empty", unit=unit_label), className="drawer-empty-text"), className="drawer-empty"),
                          className="drawer", **{"aria-label": t.t("map.drawer.label")})
    header = html.Div([html.Span(t.t("map.drawer.selected"), className="label-caps text-muted"),
                       link(icon("x", "size-4"), req.with_params(selected=None), "icon-btn", **{"aria-label": t.t("common.close")})], className="drawer-head")
    summary = req.model.summary(selected, req.year, req.filters, req.area)
    if summary is None:
        return html.Aside([header, html.P(t.t("map.drawer.notFound"), className="text-small text-warning mt-4", role="alert")], className="drawer", **{"aria-label": t.t("map.drawer.label")})
    baseline = state.baseline_label(t, summary["baseline"])
    drivers = []
    for d in summary["drivers"]:
        if pillar != "composite" and d["pillar"] != pillar:
            continue
        detail = None
        if d["score"] is not None:
            detail = t.t("map.drawer.scoreDetail", score=t.score(d["score"], 0), baseline=baseline,
                         average="–" if d["driver"] is None else t.score(d["score"] - d["driver"], 0))
        drivers.append({"id": d["id"], "label": t.t_or(f"data.indicators.{d['id']}", d["label"]), "value": d["driver"], "highlight": d["id"] == indicator, "detail": detail})
    drivers.sort(key=lambda r: r["value"] if r["value"] is not None else float("-inf"), reverse=True)
    areas = " · ".join(t.t("labels.area", name=a["name"], level=t.t_or(f"data.levels.{a['levelKey']}.one", a["levelKey"])) for a in summary["areas"])
    in_compare = selected in req.compare
    full = len(req.compare) >= 5
    return html.Aside(
        [
            header,
            html.H2(summary["name"], className="drawer-name"),
            html.P(areas, className="text-small text-muted mt-1"),
            html.Div([
                pillar_bars([(t.t(f"data.pillars.{p}"), summary["scores"][p]) for p in catalog.PILLARS]),
                html.P(rich(t.t("map.drawer.composite", value=t.score(summary["scores"]["composite"], 1)), {"value": lambda s: html.Span(s, className="font-semibold text-ink")}),
                       className="text-meta text-muted mt-2"),
            ], className="mt-4"),
            html.Div(
                [
                    html.Div([html.H3(t.t("map.drawer.drivers"), className="label-caps text-muted"), html.Span(t.t("map.drawer.vs", baseline=baseline), className="text-meta text-muted")],
                             className="drivers-head"),
                    html.Div(diverging_bars(t, drivers, track=180), className="drivers-scroll", tabIndex="0", **{"aria-label": t.t("map.drawer.drivers")}),
                    html.P(t.t("map.drawer.note", baseline=baseline, units=t.tp("units.count", summary["baseline"]["unitCount"], one=unit_label, other=unit_plural), year=str(summary["year"])),
                           className="text-meta text-faint mt-3"),
                ],
                className="drawer-drivers",
            ),
            html.Div(
                [
                    button(t.t("map.drawer.openProfile"), "primary", req.href("profile", unit=summary["id"]), cls="flex-1"),
                    button([icon("check" if in_compare else "plus"), t.t("map.compare.added") if in_compare else t.t("map.compare.add")], "secondary",
                           req.toggle_compare(selected), disabled=full and not in_compare,
                           title=t.t("map.compare.full") if full and not in_compare else None, **{"aria-pressed": "true" if in_compare else "false"}),
                ],
                className="drawer-actions",
            ),
        ],
        className="drawer", **{"aria-label": t.t("map.drawer.label")},
    )


def render(req: Request) -> dict:
    t = req.t
    data = req.model
    names = state.localized_country(req.country, t)
    pillar = security.choice(req.params.get("pillar"), MAP_PILLARS, "composite")
    raw_indicator = req.params.get("indicator")
    component = catalog.COMPONENT_BY_ID.get(raw_indicator or "")
    indicator = raw_indicator if component and (pillar == "composite" or component.pillar == pillar) else None
    metric = indicator or pillar
    label = metric_label(t, metric)

    top = data.tree[0]
    subtitle = " · ".join([
        t.t("map.tagline"),
        t.tp("units.count", len(top["nodes"]), one=names["filters"][0]["singular"].lower(), other=names["filters"][0]["plural"].lower()),
        state.units_label(req, len(data.units)),
    ])
    pillar_options = [(p, t.t("data.pillars.composite") if p == "composite" else t.t(f"data.pillars.{p}"), req.with_params(pillar=None if p == "composite" else p, indicator=None))
                      for p in MAP_PILLARS]
    indicator_options = [{"value": ALL, "label": t.t("map.allIndicators"), "href": req.with_params(indicator=None)}]
    for c in catalog.COMPONENTS:
        if pillar == "composite" or c.pillar == pillar:
            indicator_options.append({"value": c.id, "label": t.t_or(f"data.indicators.{c.id}", c.label), "href": req.with_params(indicator=c.id),
                                      "group": t.t(f"data.pillars.{c.pillar}") if pillar == "composite" else None})

    rows = data.unit_scores(req.year)
    units = [[r["id"], model_module.metric_value(r, metric), 1 if model_module.in_context(r, req.filters) else 0] for r in rows]
    selected = security.unit_id(req.params.get("selected"))
    if selected and not any(u[0] == selected and u[2] for u in units):
        selected = None
    summary = data.context_summary(req.year, req.filters)
    gaps = data.trust(req.year)["boundaryGapCount"]

    map_card = html.Section(
        [
            html.Div(state.context_line(req, summary["unitCount"]), className="text-body text-muted mb-3"),
            widget("map", {
                "iso3": req.country.iso3,
                "slug": req.country.slug,
                "units": units,
                "selected": selected,
                "metricLabel": label,
                "maxZoom": req.country.map_max_zoom,
                "selectHref": req.with_params(selected="__ID__"),
                "deselectHref": req.with_params(selected=None),
                "openHref": req.href("profile", unit="__ID__"),
                "text": {
                    "loading": t.t("map.loading"), "error": t.t("map.loadError"), "noData": t.t("map.noData"),
                    "outside": t.t("map.outsideContext"), "none": t.t("common.noData"), "tooltip": t.t("map.tooltipValue", metric=label, value="{value}"),
                    "zoomIn": t.t("map.zoomIn"), "zoomOut": t.t("map.zoomOut"), "fit": t.t("map.fitContext"), "decimal": "," if req.lang == "fr" else ".",
                },
            }, cls="map-widget", role="region", **{"aria-label": t.t("map.aria", metric=label, unit=names["local"]["singular"].lower(), units=names["local"]["plural"].lower())}),
            html.Div(
                [
                    html.Div(ramp_legend(t, label), className="legend-box"),
                    html.Span(t.t("map.outsideContextNote"), className="text-meta text-muted"),
                    html.Span(className="flex-1"),
                    badge(t.tp("map.boundaryGaps", gaps), "warning") if gaps else badge(t.t("map.boundariesMatched"), "success"),
                ],
                className="map-foot",
            ),
        ],
        className="card map-card", **{"aria-label": t.t("map.region", metric=label)},
    )
    content = [
        page_header(t.t("workspace.sections.map"), subtitle, html.Div([segmented(t.t("map.pillar"), pillar_options, pillar), view_select(t, t.t("map.indicator"), indicator or ALL, indicator_options)], className="header-controls")),
        html.Div([map_card, drawer(req, selected, pillar, indicator)], className="map-row"),
    ]
    return {"content": content, "actions": share_button(t), "title": t.t("workspace.sections.map")}
