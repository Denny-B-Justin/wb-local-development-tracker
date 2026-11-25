from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlencode

from dash import dcc, html

from services import model as model_module, security, state
from services.state import Request
from services.text import fold
from utils.components import button, cx, icon, link, page_header, score_pill, share_button

from .pages_constants import UNIT_PAGE_SIZE, UNIT_SORT_KEYS


def default_dir(key: str) -> str:
    return "asc" if key in ("name", "rank") else "desc"


def search_rows(rows: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    words = fold(query).split()
    if not words:
        return rows
    out = []
    for row in rows:
        haystack = fold(" ".join([row["name"], *[a["name"] for a in row["areas"].values()]]))
        if all(word in haystack for word in words):
            out.append(row)
    return out


def sort_rows(rows: list[dict[str, Any]], key: str, direction: str) -> list[dict[str, Any]]:
    field = {"area": "areaKm2"}.get(key, key)
    present = [r for r in rows if r.get(field) is not None]
    missing = sorted((r for r in rows if r.get(field) is None), key=lambda r: fold(r["name"]))
    if key == "name":
        ordered = sorted(present, key=lambda r: fold(r["name"]), reverse=direction == "desc")
    else:
        ordered = sorted(present, key=lambda r: fold(r["name"]))
        ordered.sort(key=lambda r: r[field], reverse=direction == "desc")
    return ordered + missing


def _results(req: Request) -> tuple[Any, Any]:
    t = req.t
    data = req.model
    names = state.localized_country(req.country, t)
    unit = names["local"]
    levels = names["filters"]
    query = req.params.get("q", "")
    sort = security.choice(req.params.get("sort"), UNIT_SORT_KEYS, "rank")
    direction = security.choice(req.params.get("dir"), ("asc", "desc"), default_dir(sort))
    try:
        limit = max(UNIT_PAGE_SIZE, min(100000, int(req.params.get("limit", UNIT_PAGE_SIZE))))
    except ValueError:
        limit = UNIT_PAGE_SIZE

    rows = [r for r in data.rows(req.year) if r["scored"]]
    context_rows = [r for r in rows if model_module.in_context(r, req.filters)]
    visible = sort_rows(search_rows(context_rows, query), sort, direction)
    shown = visible[:limit]
    summary = data.context_summary(req.year, req.filters)

    def sort_href(key: str) -> str:
        next_dir = ("desc" if direction == "asc" else "asc") if key == sort else default_dir(key)
        return req.with_params(sort=None if key == "rank" else key, dir=None if next_dir == default_dir(key) else next_dir, limit=None)

    columns = [("rank", t.t("unitList.columns.rank"), True, "w-14"), ("name", unit["singular"], False, None)]
    columns += [(None, level["singular"], False, None) for level in levels]
    columns += [("population", t.t("unitList.columns.population"), True, None), ("area", t.t("unitList.columns.area"), True, None),
                ("composite", t.t("data.pillars.composite"), True, None), ("prosperity", t.t("data.pillars.prosperity"), True, None),
                ("infrastructure", t.t("data.pillars.infrastructure"), True, None), ("livability", t.t("data.pillars.livability"), True, None),
                (None, t.t("unitList.columns.planSource"), False, None)]
    head = []
    for key, label, right, extra in columns:
        active = key is not None and key == sort
        content = link([label, icon("arrow-up" if direction == "asc" else "arrow-down", "size-3") if active else None], sort_href(key), cx("th-sort", active and "is-active")) if key else label
        props = {"aria-sort": "ascending" if direction == "asc" else "descending"} if active else {}
        head.append(html.Th(content, scope="col", className=cx("ut-th", right and "num", extra), **props))

    body = []
    for row in shown:
        cells = [
            html.Td(str(row["rank"]) if row["rank"] is not None else "–", className="num text-muted ut-first"),
            html.Td(link(row["name"], req.href("profile", unit=row["id"]), "unit-link")),
            *[html.Td(row["areas"].get(level["key"], {}).get("name", "–"), className="nowrap text-ink-3") for level in levels],
            html.Td(t.count(row["population"]), className="num"),
            html.Td(t.area(row["areaKm2"]), className="num nowrap"),
            html.Td(score_pill(t, row["composite"]), className="num"),
            *[html.Td(t.score(row[p], 1), className="num text-ink-2") for p in ("prosperity", "infrastructure", "livability")],
            html.Td(
                html.A([t.t("common.yes"), icon("external-link", "size-3"), html.Span(t.t("unitList.planLink", title=row["plan"]["title"]), className="sr-only")],
                       href=row["plan"]["link"], target="_blank", rel="noopener noreferrer", title=row["plan"]["title"], className="plan-link")
                if row["plan"] else html.Span(t.t("unitList.noPlan"), className="text-faint"),
                className="ut-last",
            ),
        ]
        body.append(html.Tr(cells, className="ut-row"))

    if not context_rows:
        table = html.P(t.t("unitList.noneInContext", units=unit["plural"].lower()), className="empty-note")
    elif not visible:
        table = html.P(t.t("unitList.noMatch", units=unit["plural"].lower(), query=query), className="empty-note")
    else:
        more = None
        if len(visible) > len(shown):
            more = html.Div([
                t.t("unitList.showing", shown=t.count(len(shown)), total=t.count(len(visible))),
                button(t.t("unitList.showMore", count=t.count(min(UNIT_PAGE_SIZE, len(visible) - len(shown)))), "secondary", req.with_params(limit=limit + UNIT_PAGE_SIZE)),
                button(t.t("common.showAll"), "ghost", req.with_params(limit=len(visible))),
            ], className="ut-more")
        table = html.Div([html.Table([html.Thead(html.Tr(head)), html.Tbody(body)], className="unit-table"), more], className="ut-scroll")
    meta = t.t("unitList.matches", shown=t.count(len(visible)), total=t.count(len(context_rows))) if query else state.context_line(req, summary["unitCount"])
    return meta, table


def render(req: Request) -> dict:
    t = req.t
    names = state.localized_country(req.country, t)
    unit = names["local"]
    levels = names["filters"]
    meta, table = _results(req)
    sort = security.choice(req.params.get("sort"), UNIT_SORT_KEYS, "rank")
    direction = security.choice(req.params.get("dir"), ("asc", "desc"), default_dir(sort))
    has_rows = any(r["scored"] and model_module.in_context(r, req.filters) for r in req.model.unit_scores(req.year))
    export_query = state.build({"country": req.country.slug, "year": req.year, **{k: v for k, v in req.filters.items() if v}, "sort": sort, "dir": direction})
    toolbar = html.Div(
        [
            html.Label(
                [
                    html.Span(t.t("unitList.search", units=unit["plural"].lower()), className="sr-only"),
                    icon("search", "search-icon"),
                    dcc.Input(id="unit-search", type="search", value=req.params.get("q", ""), debounce=0.25, maxLength=80, autoComplete="off",
                              placeholder=t.t("unitList.searchPlaceholder", units=unit["plural"].lower(), areas=", ".join(l["plural"].lower() for l in levels)),
                              className="search-input"),
                ],
                className="search-box",
            ),
            html.P(meta, id="unit-meta", className="text-small text-muted", **{"aria-live": "polite"}),
            html.A([icon("download"), t.t("common.exportCsv")], href=f"api/export/units.csv{export_query}", download="",
                   className=cx("btn btn-secondary ml-auto", not has_rows and "is-disabled")),
        ],
        className="ut-toolbar",
    )
    content = [
        page_header(unit["plural"], t.t("unitList.subtitle", unit=unit["singular"].lower())),
        html.Section([toolbar, html.Div(table, id="unit-results")], className="card unit-card", **{"aria-label": t.t("unitList.label", units=unit["plural"])}),
    ]
    return {"content": content, "actions": share_button(t), "title": unit["plural"]}


def register(app) -> None:
    from dash import ClientsideFunction, Input, Output, State, no_update

    app.clientside_callback(ClientsideFunction("ldt", "syncSearch"), Output("unit-search", "name"), Input("unit-search", "value"), prevent_initial_call=True)

    @app.callback(Output("unit-meta", "children"), Output("unit-results", "children"), Input("unit-search", "value"), State("url", "search"), prevent_initial_call=True)
    def _search(value, search):
        pairs = [(k, v) for k, v in parse_qsl((search or "").lstrip("?")) if k not in ("q", "limit")]
        if value and value.strip():
            pairs.append(("q", value.strip()[:80]))
        req = state.parse("?" + urlencode(pairs))
        if req.page != "municipalities" or req.model is None:
            return no_update, no_update
        return _results(req)
