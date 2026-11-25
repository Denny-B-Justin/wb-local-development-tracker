from __future__ import annotations

from typing import Any

from dash import html

import constants
from services import catalog, model as model_module, security, state
from services.state import Request
from utils.components import (
    button, card, card_label, card_title, cx, diverging_bars, ext, icon, link, score_pill, view_select, widget,
)

from .pages_constants import PROFILE_TABS

OVERVIEW = "pil"


def _baseline_name(t, baseline: dict[str, Any]) -> str:
    return baseline["areaName"] or t.t("profile.national")


def score_cards(req: Request, summary: dict[str, Any], row: dict[str, Any], ranked: int) -> html.Div:
    t = req.t
    vs = _baseline_name(t, summary["baseline"])

    def score_card(label, value, extra):
        return card([card_label(label), html.Div([html.Span("–" if value is None else str(round(value)), className="score-big"), extra], className="score-line")], "score-card")

    cards = [score_card(t.t("data.pillars.composite"), summary["scores"]["composite"], html.Span(
        t.t("profile.scoreCards.notRanked") if row["rank"] is None else t.t("profile.scoreCards.rank", rank=t.count(row["rank"]), total=t.count(ranked)),
        className="text-small text-muted"))]
    for pillar in catalog.PILLARS:
        value, base = summary["scores"][pillar], summary["baseline"]["scores"][pillar]
        delta = None if value is None or base is None else value - base
        extra = None
        if delta is not None:
            tone = "text-success" if round(delta) > 0 else "text-warning" if round(delta) < 0 else "text-muted"
            extra = html.Span(t.t("profile.scoreCards.delta", delta=t.delta(delta), baseline=vs), className=cx("text-small font-semibold", tone))
        cards.append(score_card(t.t(f"data.pillars.{pillar}"), value, extra))
    return html.Div(cards, className="score-cards")


def drivers_tab(req: Request, summary: dict[str, Any], unit_singular: str, unit_plural: str) -> html.Div:
    t = req.t
    baseline = state.baseline_label(t, summary["baseline"])
    vs = _baseline_name(t, summary["baseline"])
    label = lambda d: t.t_or(f"data.indicators.{d['id']}", d["label"])  # noqa: E731
    ordered = sorted(summary["drivers"], key=lambda d: d["driver"] if d["driver"] is not None else float("-inf"), reverse=True)
    bars = card([
        html.Div([card_title(t.t("profile.drivers.title")), html.Span(t.t("profile.drivers.pointsVs", baseline=baseline), className="text-meta text-muted")], className="card-head"),
        diverging_bars(t, [{"id": d["id"], "label": label(d), "value": d["driver"]} for d in ordered], track=200, bar_height=10, cls="gap-2-5"),
        html.P(t.t("profile.drivers.note", baseline=baseline, units=t.tp("units.count", summary["baseline"]["unitCount"], one=unit_singular, other=unit_plural), year=str(summary["year"])),
               className="text-meta text-faint mt-1"),
    ], "card-pad stack gap-3")
    rows = []
    for d in summary["drivers"]:
        delta = d["driver"]
        tone = "text-muted" if delta is None or round(delta) == 0 else ("text-success" if delta > 0 else "text-warning")
        rows.append(html.Tr([
            html.Td(label(d), className="dt-first text-ink-2"),
            html.Td(html.Span(t.t(f"data.pillars.{d['pillar']}"), className="tag")),
            html.Td(score_pill(t, d["score"], 0), className="num"),
            html.Td("–" if delta is None else t.delta(delta), className=cx("num dt-last font-semibold", tone)),
        ], className="zebra-row"))
    table = card(html.Table([
        html.Caption(t.t("profile.drivers.caption", baseline=baseline), className="sr-only"),
        html.Thead(html.Tr([html.Th(t.t("profile.drivers.indicator"), scope="col", className="dt-first"), html.Th(t.t("profile.drivers.pillar"), scope="col", className="w-120"),
                            html.Th(t.t("profile.drivers.score"), scope="col", className="num w-70"), html.Th(t.t("profile.drivers.vs", baseline=vs), scope="col", className="num dt-last w-120 nowrap")])),
        html.Tbody(rows),
    ], className="data-table min-480"), "overflow-x-auto")
    return html.Div([bars, table], className="drivers-grid")


def trend_tab(req: Request, name: str, trend: list[dict[str, Any]], area_label: str | None) -> html.Section:
    t = req.t
    options = [{"value": OVERVIEW, "label": t.t("profile.trend.overview")}]
    options.append({"value": "composite", "label": t.t("data.pillars.composite"), "group": t.t("profile.trend.oneScore")})
    options += [{"value": p, "label": t.t(f"data.pillars.{p}"), "group": t.t("profile.trend.oneScore")} for p in catalog.PILLARS]
    options += [{"value": c.id, "label": t.t_or(f"data.indicators.{c.id}", c.label), "group": t.t("profile.trend.indicators", pillar=t.t(f"data.pillars.{c.pillar}"))} for c in catalog.COMPONENTS]
    metric = security.choice(req.params.get("trend"), {o["value"] for o in options}, OVERVIEW)
    for option in options:
        option["href"] = req.with_params(trend=None if option["value"] == OVERVIEW else option["value"])
    years = [str(p["year"]) for p in trend]
    missing = [str(p["year"]) for p in trend if p["unit"] is None]
    value = model_module.score_set_value
    if metric == OVERVIEW:
        series = [
            {"id": "composite", "label": t.t("data.pillars.composite"), "values": [value(p["unit"], "composite") for p in trend], "tone": "navy", "emphasis": True},
            {"id": "prosperity", "label": t.t("data.pillars.prosperity"), "values": [value(p["unit"], "prosperity") for p in trend], "tone": "indigo"},
            {"id": "infrastructure", "label": t.t("data.pillars.infrastructure"), "values": [value(p["unit"], "infrastructure") for p in trend], "tone": "ramp3", "dash": "6 3"},
            {"id": "livability", "label": t.t("data.pillars.livability"), "values": [value(p["unit"], "livability") for p in trend], "tone": "orange", "dash": "2 3"},
        ]
    else:
        series = [{"id": "unit", "label": name, "values": [value(p["unit"], metric) for p in trend], "tone": "indigo", "emphasis": True}]
        if area_label:
            series.append({"id": "area", "label": area_label, "values": [value(p["area"], metric) for p in trend], "tone": "indigo500", "dash": "6 3"})
        series.append({"id": "national", "label": t.t("profile.trend.nationalAvg"), "values": [value(p["national"], metric) for p in trend], "tone": "faint", "dash": "2 3"})
    metric_name = next(o["label"] for o in options if o["value"] == metric)
    table = html.Table([
        html.Caption(t.t("profile.trend.caption"), className="sr-only"),
        html.Thead(html.Tr([html.Th(t.t("profile.trend.series"), scope="col", className="tt-first"), *[html.Th(y, scope="col", className="num") for y in years]])),
        html.Tbody([html.Tr([html.Th(s["label"], scope="row", className="tt-first font-normal text-ink-2"), *[html.Td(t.score(v, 1), className="num") for v in s["values"]]], className="tt-row") for s in series]),
    ], className="trend-table")
    return card([
        html.Div([card_title(t.t("profile.trend.title", metric=t.t("profile.trend.pilScores") if metric == OVERVIEW else metric_name, **{"from": years[0] if years else "", "to": years[-1] if years else ""})),
                  view_select(t, t.t("profile.trend.show"), metric, options)], className="card-head wrap"),
        widget("line", {"x": years, "series": series, "title": t.t("profile.trend.chart", metric=metric_name, unit=name), "decimal": "," if req.lang == "fr" else "."}, cls="line-widget"),
        html.P(t.t("profile.trend.missing", unit=name, years=", ".join(missing)), className="text-meta text-muted") if missing else None,
        html.Div(table, className="overflow-x-auto"),
    ], "card-pad stack gap-4")


def peers_tab(req: Request, row: dict[str, Any], peers: list[dict[str, Any]], unit_plural: str, country_name: str):
    t = req.t
    if not peers:
        return card(t.t("profile.peers.none", name=row["name"], year=str(req.year)), "empty-card")
    full = len(req.compare) >= constants.COMPARE_MAX
    body = []
    for index, item in enumerate([{"unit": row, "distance": None}, *peers]):
        unit = item["unit"]
        is_self = index == 0
        in_compare = unit["id"] in req.compare
        action = None
        if not is_self:
            disabled = full and not in_compare
            action = html.Button([icon("check" if in_compare else "plus", "size-3-5"), t.t("map.compare.added") if in_compare else t.t("map.compare.add")],
                                 type="button", disabled=disabled, className="peer-compare js-compare-toggle", title=t.t("map.compare.full") if disabled else None,
                                 **{"data-unit": unit["id"], "aria-pressed": "true" if in_compare else "false",
                                    "aria-label": t.t("profile.peers.remove" if in_compare else "profile.peers.add", name=unit["name"])})
        body.append(html.Tr([
            html.Td([html.Span(unit["name"], className="font-semibold text-indigo-800") if is_self else link(unit["name"], req.href("profile", unit=unit["id"]), "unit-link"),
                     html.Div(t.t("profile.peers.thisProfile") if is_self else state.area_line(req, unit["areas"]), className="text-meta text-muted")], className="pt-first"),
            html.Td(score_pill(t, unit["composite"]), className="num"),
            *[html.Td(t.score(unit[p], 1), className="num text-ink-2") for p in catalog.PILLARS],
            html.Td(t.score(item["distance"], 1), className="num text-muted"),
            html.Td(action, className="pt-last num"),
        ], className=cx("peer-row", is_self and "is-self")))
    return card([
        html.Div([card_title(t.t("profile.peers.title", units=unit_plural)),
                  html.P(t.t("profile.peers.lead", count=len(peers), units=unit_plural, country=country_name, name=row["name"], year=str(req.year)), className="text-small text-muted mt-1")],
                 className="peers-head"),
        html.Div(html.Table([
            html.Thead(html.Tr([html.Th(t.t("profile.peers.name"), scope="col", className="pt-first"),
                                *[html.Th(t.t(f"data.pillars.{p}"), scope="col", className="num") for p in ("composite", *catalog.PILLARS)],
                                html.Th(t.t("profile.peers.distance"), scope="col", className="num"),
                                html.Th(html.Span(t.t("profile.peers.compare"), className="sr-only"), scope="col", className="pt-last")])),
            html.Tbody(body),
        ], className="peers-table"), className="overflow-x-auto"),
        html.P(t.t("profile.peers.note"), className="card-note"),
    ], "overflow-hidden")


def _plan_item(t, doc: dict[str, Any]) -> html.Li:
    from urllib.parse import urlparse
    kind = doc.get("type")
    kind_label = t.t_or(f"profile.plans.types.{kind}", kind.replace("_", " ").capitalize()) if kind else None
    host = urlparse(doc["link"]).hostname or ""
    meta = " · ".join(x for x in (kind_label, host.removeprefix("www.")) if x)
    return html.Li([ext([doc["title"], icon("external-link", "plan-ext")], doc["link"], "plan-title", t.t("common.opensInNewTab")), html.Span(meta, className="text-meta text-muted")], className="plan-item")


def data_sources_list(t, cls: str = "") -> html.Div:
    sections = []
    for pillar in catalog.PILLARS:
        sources = [s for s in catalog.data_sources() if s["pillar"] == pillar]
        indicators = list(dict.fromkeys(s["indicator"] for s in sources))
        items = []
        for name in indicators:
            links: list[Any] = []
            for i, s in enumerate(x for x in sources if x["indicator"] == name):
                if i:
                    links.append(html.Span(", ", className="text-muted"))
                links.append(ext(s["label"], s["url"], "src-link"))
            items.append(html.Li([html.Span(name, className="text-ink-2"), html.Span(": ", className="text-muted"), *links]))
        sections.append(html.Section([html.H3(t.t(f"data.pillars.{pillar}"), className="label-caps text-muted"), html.Ul(items, className="src-list")]))
    return html.Div(sections, className=cx("sources", cls))


def plans_tab(req: Request, name: str, plan_area: str, local: list, national: list) -> html.Div:
    t = req.t
    return html.Div([
        card([
            html.Section([card_title(t.t("profile.plans.plansFor", area=plan_area)),
                          html.Ul([_plan_item(t, d) for d in local], className="plan-list") if local else html.P(t.t("profile.plans.noLocal", area=plan_area, unit=name), className="text-small text-muted mt-2")]),
            html.Section([card_title(t.t("profile.plans.national")),
                          html.Ul([_plan_item(t, d) for d in national], className="plan-list") if national else html.P(t.t("profile.plans.noNational"), className="text-small text-muted mt-2")],
                         className="plans-national"),
        ], "card-pad stack gap-5"),
        card([card_title(t.t("profile.plans.dataSources")), html.P(t.t("profile.plans.dataSourcesLead"), className="text-small text-muted mt-1"), data_sources_list(t, "mt-4")], "card-pad"),
    ], className="grid-2 gap-5 xl-only")


def render(req: Request) -> dict:
    t = req.t
    data = req.model
    unit_id = security.unit_id(req.params.get("unit"))
    row = data.row(req.year, unit_id) if unit_id else None
    if row is None:
        from . import not_found
        return {**not_found.render(req), "workspace": True}
    names = state.localized_country(req.country, t)
    level = names["local"]
    top = names["filters"][0]
    top_area = t.t("labels.area", name=row["areas"][top["key"]]["name"], level=top["singular"])
    plan_area = top_area if req.country.plan_source_level == "top" else row["name"]
    plans = data.plan_sources
    local = plans["local"].get(data.plan_key(row), [])
    national = []
    if req.country.national_plan:
        national.append({"title": req.country.national_plan.title, "link": req.country.national_plan.url, "type": "national_development_plan"})
    national += [d for d in plans["national"] if not req.country.national_plan or d["link"] != req.country.national_plan.url]
    summary = data.summary(row["id"], req.year, req.filters, req.area)
    in_compare = row["id"] in req.compare
    full = len(req.compare) >= constants.COMPARE_MAX
    actions = html.Div([
        html.Button([icon("check" if in_compare else "plus"), t.t("map.compare.added") if in_compare else t.t("map.compare.add")], type="button",
                    className="btn btn-secondary js-compare-toggle", disabled=full and not in_compare, title=t.t("map.compare.full") if full and not in_compare else None,
                    **{"data-unit": row["id"], "aria-pressed": "true" if in_compare else "false"}),
        button([icon("sparkles"), t.t("profile.generateBrief")], "primary", req.href("brief", scope=row["id"])),
    ], className="profile-actions")
    header = [
        link([icon("arrow-left", "size-4"), f"{names['name']} / {top_area}"], req.href("municipalities"), "back-link"),
        html.Div([
            html.Div([html.H1(row["name"], className="page-title"),
                      html.P(f"{level['singular']} · {state.area_line(req, row['areas'])} · {req.year}", className="page-subtitle")]),
            actions,
        ], className="profile-head"),
    ]
    if summary is None:
        trend = data.trend(row["id"], req.filters, req.area)
        other = [str(p["year"]) for p in trend if p["unit"]]
        body = [card([t.t("profile.noScores", name=row["name"], year=str(req.year)), " ", t.t("profile.otherYears", years=", ".join(other)) if other else None], "empty-card")]
    else:
        tab = security.choice(req.params.get("tab"), PROFILE_TABS, "drivers")
        years = data.years
        labels = {
            "drivers": t.t("profile.tabs.drivers"),
            "trend": t.t("profile.tabs.trend", **{"from": str(years[0]), "to": str(years[-1])}),
            "peers": t.t("profile.tabs.peers"),
            "plans": t.t("profile.tabs.plans"),
        }
        if tab == "drivers":
            panel = drivers_tab(req, summary, level["singular"].lower(), level["plural"].lower())
        elif tab == "trend":
            area_label = state.baseline_label(t, summary["baseline"]) if summary["baseline"]["scope"] != "national" else None
            panel = trend_tab(req, row["name"], data.trend(row["id"], req.filters, req.area), area_label)
        elif tab == "peers":
            panel = peers_tab(req, row, data.peers(req.year, row["id"]), level["plural"].lower(), names["name"])
        else:
            panel = plans_tab(req, row["name"], plan_area, local, national)
        ranked = sum(1 for r in data.rows(req.year) if r["rank"] is not None)
        tabs = html.Div(
            [link(labels[key], req.with_params(tab=None if key == "drivers" else key), cx("ptab", key == tab and "is-active"),
                  role="tab", id=f"tab-{key}", **{"aria-selected": "true" if key == tab else "false", "aria-controls": f"panel-{key}"}) for key in PROFILE_TABS],
            className="ptabs", role="tablist", **{"aria-label": t.t("profile.tabs.label")},
        )
        body = [score_cards(req, summary, row, ranked), html.Div([tabs, html.Div(panel, role="tabpanel", id=f"panel-{tab}", **{"aria-labelledby": f"tab-{tab}"})], className="stack gap-5")]
    return {"content": [*header, *body], "title": row["name"], "active_unit": {"id": row["id"], "name": row["name"]}}
