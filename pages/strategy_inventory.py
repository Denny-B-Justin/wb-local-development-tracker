from __future__ import annotations

from typing import Any

from dash import html

from services import inventory, state, store
from services.text import fold
from services.state import Request
from utils.components import card, card_label, card_title, cx, icon, page_header

from .pages_constants import INVENTORY_READINESS_BAR


def _humanize(value: str) -> str:
    return value.replace("_", " ").capitalize()


def year_chart(t, summary: dict[str, Any]) -> html.Div:
    known = [e for e in summary["publication_year_counts"] if e["year"] != "Unknown"]
    years = [int(e["year"]) for e in known]
    counts = {int(e["year"]): e["count"] for e in known}
    series = [(y, counts.get(y, 0)) for y in range(min(years), max(years) + 1)] if years else []
    peak = max([1, *[c for _, c in series]])
    last = years[-1] if years else 0
    bars = [html.Div([
        html.Span(t.tp("inventory.yearTooltip", count, year=str(year)), className="yc-tip"),
        html.Span(str(count), className="yc-count") if count else None,
        html.Div(className="yc-bar", style={"height": f"{count / peak * 100}%", "minHeight": "2px" if count else "0"}),
    ], className="yc-col") for year, count in series]
    labels = [html.Span(f"’{str(year)[2:]}" if year % 2 == last % 2 else "", className="yc-label") for year, _ in series]
    table = html.Table([html.Caption(t.t("inventory.byYear")), html.Tbody([*[html.Tr([html.Th(str(y), scope="row"), html.Td(str(c))]) for y, c in series],
                                                                        html.Tr([html.Th(t.t("inventory.unknownYear"), scope="row"), html.Td(str(summary["unknown_year_count"]))])])], className="sr-only")
    return html.Div([html.Div(bars, className="yc-bars", **{"aria-hidden": "true"}), html.Div(labels, className="yc-labels", **{"aria-hidden": "true"}), table])


def readiness_chart(t, summary: dict[str, Any]) -> html.Dl:
    peak = max([1, *[e["count"] for e in summary["status_breakdown"]]])
    rows = []
    for entry in summary["status_breakdown"]:
        key = inventory.READINESS_KEYS[entry["category"]]
        rows.append(html.Div([
            html.Dt([html.Span(t.t(f"inventory.readiness.{key}.label"), className="font-semibold text-ink"), html.Span(t.t(f"inventory.readiness.{key}.note"), className="text-meta text-muted")], className="flex-col"),
            html.Div(html.Div(className=cx("rc-fill", INVENTORY_READINESS_BAR[entry["category"]]), style={"width": f"{entry['count'] / peak * 100}%"}), className="rc-track", **{"aria-hidden": "true"}),
            html.Dd(str(entry["count"]), className="num font-semibold text-ink-2"),
        ], className="rc-row"))
    return html.Dl(rows, className="stack gap-3")


def table_rows(req: Request, records: list[dict[str, Any]]) -> list:
    t = req.t
    out = []
    for record in records:
        category = inventory.readiness(record)
        key = inventory.READINESS_KEYS[category]
        doc_type = record.get("document_type")
        status = record.get("translation_status")
        search = " ".join(str(record.get(k) or "") for k in ("lsg_name", "lsg_name_local", "region_name", "document_title", "notes"))
        attrs = {
            "data-search": fold(search), "data-year": str(record["publication_year"]) if record.get("publication_year") else "Unknown",
            "data-readiness": category, "data-type": doc_type or "", "data-translation": status or "",
            "data-sort-lsg_name": fold(record.get("lsg_name")), "data-sort-region_name": fold(record.get("region_name")),
            "data-sort-document_type": doc_type or "", "data-sort-publication_year": str(record.get("publication_year") or ""),
            "data-sort-readiness": str(inventory.READINESS.index(category)), "data-sort-translation_status": status or "",
        }
        out.append(html.Tr([
            html.Th([record.get("lsg_name", ""), html.Span(record["document_title"], className="inv-title") if record.get("document_title") else None], scope="row", className="inv-unit"),
            html.Td(record.get("region_name") or "–", className="text-ink-2"),
            html.Td(t.t_or(f"inventory.documentTypes.{doc_type}", _humanize(doc_type)) if doc_type else "–", className="text-ink-2"),
            html.Td(str(record["publication_year"]) if record.get("publication_year") else "–", className="text-ink-2 tabular"),
            html.Td(html.Span([html.Span(className=cx("dot", INVENTORY_READINESS_BAR[category]), **{"aria-hidden": "true"}), t.t(f"inventory.readiness.{key}.label")], className="inv-ready")),
            html.Td(t.t_or(f"inventory.translationStatus.{status}", _humanize(status)) if status else "–", className="text-ink-2"),
            html.Td(html.A([t.t("common.open"), " ", icon("external-link", "size-3"), html.Span(t.t("common.opensInNewTab"), className="sr-only")], href=record["source_url"],
                           target="_blank", rel="noopener noreferrer", className="text-link inline-flex") if record.get("source_url") else html.Span("–", className="text-faint")),
        ], className="inv-row", **attrs))
    return out


SORTS = ("lsg_name", "region_name", "document_type", "publication_year", "readiness", "translation_status")


def sort_records(records: list[dict[str, Any]], key: str, direction: str) -> list[dict[str, Any]]:
    def value(r):
        if key == "readiness":
            return inventory.READINESS.index(inventory.readiness(r))
        return r.get(key)
    present = [r for r in records if value(r) is not None]
    missing = [r for r in records if value(r) is None]
    present.sort(key=lambda r: value(r) if isinstance(value(r), int) else str(value(r)).lower(), reverse=direction == "desc")
    return present + missing


def render(req: Request) -> dict:
    t = req.t
    if not req.country.features.strategy_inventory:
        from . import not_found
        return not_found.render(req)
    data = req.model
    names = state.localized_country(req.country, t)
    unit = names["local"]
    region = names["filters"][0]
    records = store.strategy_inventory(req.country.iso3) or []
    coverage = data.coverage()
    summary = inventory.summarize(records, coverage[-1]["units"] if coverage else 0)
    lower = {"unit": unit["singular"].lower(), "units": unit["plural"].lower()}
    kpis = [
        (t.t("inventory.kpis.expected", units=unit["plural"]), t.count(summary["expected_lsgs"]), t.t("inventory.kpis.expectedNote", year=str(coverage[-1]["year"]) if coverage else "")),
        (t.t("inventory.kpis.withDocuments"), t.count(summary["lsgs_with_any_document"]), t.t("inventory.kpis.withDocumentsNote")),
        (t.t("trust.coverage"), t.percent(summary["coverage_rate"]), t.t("inventory.kpis.coverageNote", **lower)),
        (t.t("inventory.kpis.documents"), t.count(summary["total_documents_found"]), t.t("inventory.kpis.documentsNote")),
        (t.t("inventory.kpis.aiReady"), t.count(summary["ai_ready_documents"]), t.t("inventory.kpis.aiReadyNote")),
        (t.t("inventory.kpis.blocked"), f"{t.count(summary['needs_translation'])} / {t.count(summary['needs_validation'])}", t.t("inventory.kpis.blockedNote")),
    ]
    years = sorted({str(r["publication_year"]) if r.get("publication_year") else "Unknown" for r in records}, key=lambda y: (y == "Unknown", -int(y) if y != "Unknown" else 0))
    select = lambda sid, label, options: html.Label([html.Span(label, className="sr-only"), html.Select([html.Option(o["label"], value=o["value"]) for o in options], className="native-select", **{"data-filter": sid})])  # noqa: E731
    controls = html.Div([
        html.Label([html.Span(t.t("common.search"), className="sr-only"), icon("search", "search-icon sm"),
                    html.Span(className="inv-query-slot", **{"data-placeholder": t.t("inventory.table.searchPlaceholder", unit=unit["singular"].lower(), region=region["singular"].lower())})],
                   className="search-box inv-search"),
        select("inv-year", t.t("inventory.table.publicationYear"), [{"label": t.t("inventory.table.allYears"), "value": "all"}] + [{"label": t.t("inventory.unknown") if y == "Unknown" else y, "value": y} for y in years]),
        select("inv-readiness", t.t("inventory.table.readiness"), [{"label": t.t("inventory.table.allReadiness"), "value": "all"}] + [{"label": t.t(f"inventory.readiness.{inventory.READINESS_KEYS[c]}.label"), "value": c} for c in inventory.READINESS]),
        select("inv-type", t.t("inventory.table.documentType"), [{"label": t.t("inventory.table.allTypes"), "value": "all"}] + [{"label": t.t(f"inventory.documentTypes.{d}"), "value": d} for d in inventory.DOCUMENT_TYPES]),
        select("inv-translation", t.t("inventory.table.translation"), [{"label": t.t("inventory.table.allTranslation"), "value": "all"}] + [{"label": t.t(f"inventory.translationStatus.{s}"), "value": s} for s in inventory.TRANSLATION_STATUSES]),
    ], className="inv-controls")
    head = html.Thead(html.Tr([
        *[html.Th(html.Button([label, html.Span(className="sort-ind")], type="button", className=cx("th-sort js-inv-sort", key == "lsg_name" and "is-active"), **{"data-key": key, "data-dir": "asc" if key == "lsg_name" else ""}), scope="col",
                  **({"aria-sort": "ascending"} if key == "lsg_name" else {}))
          for key, label in (("lsg_name", unit["singular"]), ("region_name", region["singular"]), ("document_type", t.t("inventory.table.type")),
                             ("publication_year", t.t("common.year")), ("readiness", t.t("inventory.table.readiness")), ("translation_status", t.t("inventory.table.translation")))],
        html.Th(t.t("inventory.table.source"), scope="col"),
    ]))
    missing = summary["missing_lsgs"]
    content = [
        page_header(t.t("workspace.sections.inventory"), t.t("inventory.subtitle", **lower)),
        html.Div([
            html.Section([card([card_label(label), html.Span(value, className="kpi-value"), html.Span(note, className="text-meta text-muted")], "kpi-card") for label, value, note in kpis],
                         className="kpi-grid", **{"aria-label": t.t("inventory.summary")}),
            html.Div([
                card([html.Div([card_title(t.t("inventory.byYear")), html.Span(t.t("inventory.unknownYearCount", count=summary["unknown_year_count"]), className="text-meta text-muted")], className="card-head"),
                      html.Div(year_chart(t, summary), className="mt-8")], "card-pad"),
                card([card_title(t.t("inventory.readinessTitle")),
                      html.P([t.t("inventory.readinessLead", missing=t.t("inventory.readiness.missing.label"), units=lower["units"]), f" {t.t('inventory.serbianNote')}" if req.country.features.translation_check else ""],
                             className="text-small text-muted mt-1 mb-4"),
                      readiness_chart(t, summary)], "card-pad"),
            ], className="grid-2 gap-5 xl-only"),
            card([card_title(t.t("inventory.documentsTitle")), html.Div([
                controls,
                html.P(t.t("inventory.table.showing", shown=len(records), total=len(records)), className="text-meta text-muted inv-showing",
                       **{"aria-live": "polite", "data-template": t.t("inventory.table.showing", shown="{shown}", total="{total}")}),
                html.Div(html.Table([head, html.Tbody(table_rows(req, sort_records(records, "lsg_name", "asc")))], className="inv-table"), className="inv-scroll"),
            ], className="stack gap-3 mt-3 js-inventory", **{"data-widget": "inventory"})], "card-pad"),
            card([
                card_title(t.t("inventory.missingTitle", units=unit["plural"], count=len(missing) + summary["unlisted_missing_lsg_count"])),
                html.Ul([html.Li([html.Span(m["lsg_name"], className="font-medium text-ink-2"), html.Span(f" · {m['region_name']}", className="text-muted") if m.get("region_name") else None]) for m in missing], className="inline-list mt-3")
                if missing else html.P(t.t("inventory.noneMissing", **lower), className="text-small text-muted mt-2"),
                html.P(t.tp("inventory.unlisted", summary["unlisted_missing_lsg_count"], **lower), className="text-small text-muted mt-2") if summary["unlisted_missing_lsg_count"] else None,
                html.P(t.t("inventory.lastUpdated", date=summary["latest_last_updated"]), className="text-meta text-muted mt-4") if summary["latest_last_updated"] else None,
            ], "card-pad"),
        ], className="stack gap-5"),
    ]
    return {"content": content, "title": t.t("workspace.sections.inventory")}
