"""Flask routes: geometry, CSV exports, the brief stage runner, health and data refresh."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from flask import Flask, Response, jsonify, request

import constants
import countries

from . import catalog, model as model_module, security, state, store
from .ai import cache as ai_cache
from .ai import pipeline


def _csv_cell(value: str) -> str:
    return f'"{value.replace(chr(34), chr(34) * 2)}"' if any(c in value for c in ',"\r\n') else value


def _formula_safe(value: str) -> str:
    return f"'{value}" if value[:1] in ("=", "+", "-", "@") and not _is_number(value) else value


def _is_number(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def _csv(rows: list[list[str]], newline: str) -> str:
    return newline.join(",".join(_csv_cell(_formula_safe(cell)) for cell in row) for row in rows)


def _fixed(value: float | None) -> str:
    return "" if value is None else f"{value:.2f}"


def _download(body: str, filename: str, mimetype: str = "text/csv; charset=utf-8") -> Response:
    safe = "".join(c for c in filename if c.isalnum() or c in "-_.") or "export.csv"
    return Response(body, mimetype=mimetype, headers={"Content-Disposition": f'attachment; filename="{safe}"', "Cache-Control": "no-store"})


def _workspace(page: str) -> state.Request | None:
    req = state.parse("?" + request.query_string.decode("utf-8", "ignore") + f"&page={page}")
    return req if req.country and req.model and req.page == page else None


def units_csv(req: state.Request) -> tuple[str, str]:
    from pages.units import default_dir, sort_rows

    country = req.country
    data = req.model
    parent = country.filter_levels[0]
    sort = security.choice(req.params.get("sort"), ("rank", "name", "population", "area", "composite", "prosperity", "infrastructure", "livability"), "rank")
    direction = security.choice(req.params.get("dir"), ("asc", "desc"), default_dir(sort))
    rows = sort_rows([r for r in data.rows(req.year) if r["scored"] and model_module.in_context(r, req.filters)], sort, direction)
    level = "Provincial" if country.plan_source_level == "top" else "Local"
    header = [country.local_level.singular, parent.singular, "Population", "Area (km2)", "Infrastructure Score", "Livability Score", "Prosperity Score",
              "PIL Aggregate", "Has Development Strategy", "Strategy Level", "Link"]
    lines = [header] + [[
        r["name"], r["areas"][parent.key]["name"], "" if r["population"] is None else str(round(r["population"])),
        "" if r["areaKm2"] is None else f"{r['areaKm2']:.2f}", _fixed(r["infrastructure"]), _fixed(r["livability"]), _fixed(r["prosperity"]), _fixed(r["composite"]),
        "Yes" if r["plan"] else "No", level if r["plan"] else "", r["plan"]["link"] if r["plan"] else "",
    ] for r in rows]
    return _csv(lines, "\r\n"), f"{country.slug}-sng-{country.local_level.singular.lower()}-metrics.csv"


def compare_csv(req: state.Request) -> tuple[str, str]:
    country = req.country
    data = req.model
    labels = {"composite": "PIL Aggregate", **{p: f"{p.capitalize()} Score" for p in catalog.PILLARS}, **{c.id: f"{c.label} Score" for c in catalog.COMPONENTS}}
    x = security.choice(req.params.get("x"), labels, "prosperity")
    y = security.choice(req.params.get("y"), labels, "infrastructure")
    levels = list(reversed(country.filter_levels))
    same = x == y
    header = ["id", country.local_level.singular, *[l.singular for l in levels], f"X: {labels[x]}" if same else labels[x], f"Y: {labels[y]}" if same else labels[y], "selected"]
    rows = [r for r in data.rows(req.year) if r["scored"] and model_module.in_context(r, req.filters)]
    cell = lambda v: "" if v is None else repr(float(v)).removesuffix(".0") if float(v).is_integer() else repr(float(v))  # noqa: E731
    lines = [header] + [[r["id"], r["name"], *[r["areas"][l.key]["name"] for l in levels], cell(model_module.metric_value(r, x)), cell(model_module.metric_value(r, y)),
                         "true" if r["id"] in req.compare else "false"] for r in rows]
    kebab = lambda metric: "".join(c if c.isalnum() else "-" for c in labels[metric].lower()).strip("-").replace("--", "-")  # noqa: E731
    return _csv(lines, "\n"), f"{kebab(x)}-{kebab(y)}-comparison.csv"


def _brief_context(body: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    search = str(body.get("search", ""))[: constants.MAX_QUERY_STRING_LENGTH]
    req = state.parse(search)
    if req.page != "brief" or not req.model:
        return None, "Not a brief page."
    from pages.brief import selection

    row, theme = selection(req)
    if not row:
        return None, "Choose a unit to brief."
    return pipeline.build_context(req.model, row["id"], req.year, theme), None


def register(server: Flask) -> None:
    @server.get("/api/geometry/<iso3>")
    def geometry(iso3: str):
        country = countries.BY_ISO3.get(iso3.upper()[:3])
        if not country or not countries.is_visible(country, request.cookies.get(state.PREVIEW_COOKIE)):
            return Response("Not found", status=404)
        found = store.geometry_gz(country.iso3)
        if not found:
            return Response("Not found", status=404)
        data, mtime = found
        etag = hashlib.sha1(f"{country.iso3}{mtime}{len(data)}".encode()).hexdigest()
        if request.headers.get("If-None-Match") == etag:
            return Response(status=304)
        return Response(data, mimetype="application/json", headers={"Content-Encoding": "gzip", "ETag": etag, "Cache-Control": "public, max-age=3600", "Vary": "Accept-Encoding"})

    @server.get("/api/export/units.csv")
    def export_units():
        req = _workspace("municipalities")
        if not req:
            return Response("Not found", status=404)
        body, name = units_csv(req)
        return _download(body, name)

    @server.get("/api/export/compare.csv")
    def export_compare():
        req = _workspace("compare")
        if not req:
            return Response("Not found", status=404)
        body, name = compare_csv(req)
        return _download(body, name)

    @server.get("/api/brief/export.md")
    def export_brief():
        req = _workspace("brief")
        if not req:
            return Response("Not found", status=404)
        from pages.brief import selection

        row, theme = selection(req)
        if not row:
            return Response("Not found", status=404)
        context = pipeline.build_context(req.model, row["id"], req.year, theme)
        country_en = state.localized_country(req.country, state.translator("en"))
        area = " · ".join(f"{row['areas'][l['key']]['name']} {l['singular']}" for l in reversed(country_en["filters"]))
        slug = "".join(c if c.isalnum() else "-" for c in row["name"].lower()).strip("-")
        return _download(pipeline.markdown_export(context, pipeline.load_cached(context), area), f"ldt-ai-brief-{slug}-{theme}-{req.year}.md", "text/markdown; charset=utf-8")

    def _json_body() -> dict[str, Any] | None:
        if not security.same_origin() or request.content_length is None or request.content_length > 8192:
            return None
        body = request.get_json(silent=True)
        return body if isinstance(body, dict) else None

    @server.post("/api/brief/stage")
    def brief_stage():
        body = _json_body()
        if body is None:
            return jsonify({"error": "Bad request"}), 400
        stage = body.get("stage")
        mode = body.get("mode")
        if stage not in pipeline.STAGES or mode not in ("generate", "regenerate", "load_cached"):
            return jsonify({"error": "Bad request"}), 400
        context, error = _brief_context(body)
        if context is None:
            return jsonify({"error": error}), 400
        result = pipeline.run_stage(context, stage, mode, security.client_key())
        return jsonify({"stage": stage, "status": result["status"], "errorMessage": result.get("errorMessage")})

    @server.post("/api/brief/load")
    def brief_load():
        body = _json_body()
        if body is None:
            return jsonify({"error": "Bad request"}), 400
        context, error = _brief_context(body)
        if context is None:
            return jsonify({"arrived": 0})
        try:
            arrived = ai_cache.pull_remote(pipeline.scope_of(context), list(pipeline.STAGES))
        except Exception:  # noqa: BLE001
            arrived = 0
        return jsonify({"arrived": arrived})

    @server.get("/api/preview")
    def preview():
        token = request.args.get("token", "")[:200]
        response = Response(status=302, headers={"Location": "../", "Cache-Control": "no-store"})
        if countries.preview_ok(token):
            response.set_cookie(state.PREVIEW_COOKIE, token, max_age=7 * 86400, secure=request.is_secure, httponly=True, samesite="Lax")
        return response

    @server.get("/healthz")
    def health():
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip() or request.headers.get("X-LDT-Token")
        if constants.REFRESH_TOKEN and security.constant_time_equals(constants.REFRESH_TOKEN, token):
            return jsonify({"ok": True, "version": constants.APP_VERSION, "data": store.status()})
        return jsonify({"ok": True})

    @server.post("/api/admin/refresh")
    def refresh():
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip() or request.headers.get("X-LDT-Token")
        if not constants.REFRESH_TOKEN or not security.constant_time_equals(constants.REFRESH_TOKEN, token):
            return jsonify({"error": "Forbidden"}), 403
        store.schedule_warm(force=True)
        return jsonify({"scheduled": True}), 202
