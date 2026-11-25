from __future__ import annotations

from typing import Any

from dash import html

from services import inventory, model as model_module, state
from services.state import Request
from utils.components import badge, card, card_label, card_title, ext, icon, link, page_header, rich

from .profile import data_sources_list

TONE = {"ready": "success", "partial": "warning", "blocked": "warning"}


def describe(req: Request, item: dict[str, Any]) -> dict[str, str]:
    t = req.t
    facts = item["facts"]
    names = state.localized_country(req.country, t)
    units = lambda n: state.units_label(req, n)  # noqa: E731
    key = item["key"]
    if key == "coverage":
        return {"label": t.t("trust.coverage"), "value": t.t("trust.ready") if item["status"] == "ready" else t.t("common.noData"),
                "detail": t.t("trust.coverageDetail", units=units(facts["units"]), year=str(facts["year"]), key=facts["releaseKey"])}
    if key == "boundaries":
        return {"label": t.t("trust.boundaries"), "value": t.t("trust.matched") if item["status"] == "ready" else t.tp("trust.gaps", facts["gaps"]),
                "detail": t.t("trust.mappedDetail", units=units(facts["mapped"]))}
    if key == "planSources":
        level = names["filters"][0] if facts["planLevel"] == "top" else names["local"]
        return {"label": t.t("trust.planSources"), "value": t.t("trust.sourced", percent=facts["percent"]),
                "detail": t.t("trust.planDetail", sourced=facts["sourced"], total=facts["total"], areas=(level["singular"] if facts["total"] == 1 else level["plural"]).lower())}
    status = item["status"]
    return {"label": t.t("trust.aiReadiness"), "value": t.t("trust.blocked") if status == "blocked" else t.t("trust.ready") if status == "ready" else t.t("trust.partial"),
            "detail": names["ai_message"]}


def plan_groups(req: Request, units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    data = req.model
    top = req.country.filter_levels[0].key
    local = data.plan_sources["local"]
    groups: dict[str, dict[str, Any]] = {}
    for unit in units:
        area = unit["areas"].get(top) or {"slug": "", "name": req.t.t("dataTrust.plans.unassigned")}
        group = groups.get(area["slug"])
        if group is None:
            docs = local.get(data.plan_key(unit), []) if req.country.plan_source_level == "top" else []
            group = groups[area["slug"]] = {"name": area["name"], "slug": area["slug"], "documents": docs, "units": [], "sourced": 0}
        docs = local.get(data.plan_key(unit), []) if req.country.plan_source_level == "local" else []
        group["units"].append({"id": unit["id"], "name": unit["name"], "documents": docs})
        if group["documents"] or docs:
            group["sourced"] += 1
    ordered = sorted(groups.values(), key=lambda g: g["name"])
    for group in ordered:
        group["units"].sort(key=lambda u: u["name"])
    return ordered


def _doc_link(t, doc) -> html.A:
    return ext([doc["title"], icon("external-link", "size-3 doc-ext")], doc["link"], "doc-link", t.t("common.opensInNewTab"))


def plan_availability(req: Request, groups: list[dict[str, Any]]) -> html.Ul:
    t = req.t
    per_unit = req.country.plan_source_level == "local"
    items = []
    for group in groups:
        total = len(group["units"])
        tone = "success" if group["sourced"] == total else "warning"
        label = t.t("dataTrust.plans.sourcedOf", sourced=group["sourced"], total=total) if per_unit else (t.t("dataTrust.plans.plan") if group["documents"] else t.t("dataTrust.plans.noPlan"))
        if per_unit:
            detail = html.Ul([
                html.Li([link(u["name"], req.href("profile", unit=u["id"]), "pa-unit"),
                         *([html.Span(_doc_link(t, d), className="text-meta") for d in u["documents"]] or [html.Span(t.t("dataTrust.plans.noPlanTracked"), className="text-meta text-muted")])],
                        className="pa-unit-item") for u in group["units"]], className="pa-units")
        elif group["documents"]:
            detail = html.Ul([*[html.Li(_doc_link(t, d)) for d in group["documents"]],
                              html.Li(t.t("dataTrust.plans.usedForAll", units=state.units_label(req, total), area=group["name"]), className="text-meta text-muted")], className="stack gap-1")
        else:
            detail = html.P(t.t("dataTrust.plans.noneForArea", area=group["name"]), className="text-muted")
        items.append(html.Li(html.Details([
            html.Summary([icon("chevron-down", "pa-chev"), html.Span(group["name"], className="pa-name"), html.Span(state.units_label(req, total), className="text-meta text-muted"),
                          badge(label, tone, "pa-badge")], className="pa-summary"),
            html.Div(detail, className="pa-detail"),
        ], className="pa")))
    return html.Ul(items, className="pa-list")


def render(req: Request) -> dict:
    t = req.t
    data = req.model
    names = state.localized_country(req.country, t)
    unit_plural = names["local"]["plural"].lower()
    unit_singular = names["local"]["singular"].lower()
    trust = data.trust(req.year)
    gaps = data.boundary_gaps(req.year)
    coverage = data.coverage()
    rows = [r for r in data.rows(req.year) if r["scored"] and model_module.in_context(r, req.filters)]
    filtered = any(req.filters.values())
    groups = plan_groups(req, rows)
    sourced = sum(g["sourced"] for g in groups)
    translation = None
    if req.country.features.translation_check:
        from services import store
        records = store.strategy_inventory(req.country.iso3) or []
        translation = inventory.summarize(records, coverage[-1]["units"] if coverage else 0)

    cards = []
    for item in trust["items"]:
        text = describe(req, item)
        note = None
        if item["key"] == "aiReadiness" and translation:
            note = html.P(rich(t.t("dataTrust.inventoryNote", ready=translation["ai_ready_documents"], total=translation["total_documents_found"], needs=translation["needs_translation"]),
                               {"link": lambda s: link(s, req.href("strategy-inventory"), "text-link")}), className="text-small text-ink-3")
        cards.append(card([card_label(text["label"]), badge(text["value"], TONE[item["status"]], "self-start text-small"), html.P(text["detail"], className="text-small text-ink-3"), note], "trust-card"))

    unmapped = [u for u in gaps["unmapped"] if not filtered or any(r["id"] == u["id"] for r in rows)]
    releases = card([
        html.Div([card_title(t.t("dataTrust.releases.title")), badge(t.t("dataTrust.pilVersion", version=trust["pilVersion"]), "neutral", "uppercase")], className="card-head-center"),
        html.Table([
            html.Thead(html.Tr([html.Th(t.t("common.year"), scope="col"), html.Th(t.t("dataTrust.releases.release"), scope="col"), html.Th(t.t("dataTrust.releases.scored", units=unit_plural), scope="col", className="num")])),
            html.Tbody([html.Tr([html.Td([str(r["year"]), badge(t.t("dataTrust.releases.viewing"), "info", "ml-2") if r["year"] == req.year else None], className="text-ink-2"),
                                 html.Td(r["releaseKey"], className="font-mono text-meta text-ink-3"), html.Td(t.count(r["units"]), className="num text-ink-2")]) for r in coverage]),
        ], className="mini-table mt-3"),
        html.P(rich(t.t("dataTrust.releases.note"), {"link": lambda s: link(s, req.site_href("methodology"), "text-link")}), className="text-meta text-muted mt-3"),
    ], "card-pad")
    gap_card = card([
        html.Div([card_title(t.t("dataTrust.gaps.title")), badge(t.tp("trust.gaps", trust["boundaryGapCount"]) if trust["boundaryGapCount"] else t.t("trust.matched"), "warning" if trust["boundaryGapCount"] else "success")],
                 className="card-head-center"),
        html.P(t.t("dataTrust.gaps.hatched"), className="text-small text-muted mt-1"),
        html.Dl([
            html.Div([html.Dt(t.t("dataTrust.gaps.unmapped", count=len(gaps["unmapped"])), className="font-semibold text-ink"),
                      html.Dd(html.Ul([html.Li([link(u["name"], req.href("profile", unit=u["id"]), "text-link"), html.Span(f" · {', '.join(u['areaNames'])}", className="text-muted") if u["areaNames"] else None])
                                       for u in unmapped], className="inline-list") if unmapped
                              else t.t("dataTrust.gaps.allMappedInArea" if filtered else "dataTrust.gaps.allMapped", unit=unit_singular), className="mt-1 text-ink-3")]),
            html.Div([html.Dt(t.t("dataTrust.gaps.boundaryOnly", count=gaps["boundaryOnly"]), className="font-semibold text-ink"),
                      html.Dd(t.tp("dataTrust.gaps.boundaryOnlyDetail", gaps["boundaryOnly"], unit=unit_singular) if gaps["boundaryOnly"] else t.t("dataTrust.gaps.allMatched"), className="mt-1 text-ink-3")]),
        ], className="stack gap-3 text-small mt-3"),
    ], "card-pad")

    plan_vars = {"sourced": t.count(sourced), "total": t.count(len(rows)), "units": unit_plural, "area": names["filters"][0]["singular"].lower()}
    covered_key = ("dataTrust.plans.coveredByAreaInArea" if filtered else "dataTrust.plans.coveredByArea") if req.country.plan_source_level == "top" else ("dataTrust.plans.coveredInArea" if filtered else "dataTrust.plans.covered")
    national = data.plan_sources["national"]
    needed: list[Any] = [t.t("dataTrust.plans.needed")]
    if national:
        links: list[Any] = []
        for i, doc in enumerate(national):
            links += [", " if i else "", ext(doc["title"], doc["link"], "text-link")]
        needed += [" ", *rich(t.t("dataTrust.plans.national"), {"plans": lambda _s: html.Span(links)})]
    plans_card = card([
        html.Div([card_title(t.t("trust.planSources")), html.Span(t.t(covered_key, **plan_vars), className="text-small text-muted")], className="card-head-center wrap"),
        html.P(needed, className="text-small text-muted mt-1 mb-3"),
        plan_availability(req, groups),
    ], "card-pad")
    sources_card = card([card_title(t.t("dataTrust.sources.title")), html.P(t.t("dataTrust.sources.lead"), className="text-small text-muted mt-1"), data_sources_list(t, "mt-4 sources-3")], "card-pad")

    content = [
        page_header(t.t("trust.title"), t.t("dataTrust.subtitle", year=str(req.year))),
        html.Div([
            html.Section(cards, className="trust-cards", **{"aria-label": t.t("dataTrust.releaseStatus")}),
            html.Div([releases, gap_card], className="grid-2 gap-5 xl-only"),
            plans_card,
            sources_card,
        ], className="stack gap-5"),
    ]
    return {"content": content, "title": t.t("trust.title")}
