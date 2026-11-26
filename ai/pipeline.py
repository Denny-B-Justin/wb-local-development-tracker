"""The planning-brief pipeline: one unit × one score theme × one release, stage by stage."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

import constants
from countries import Country
from services import catalog
from services.model import CountryModel
from services.security import RateLimiter

from . import cache, client, documents, models, prompt

log = logging.getLogger(__name__)

STAGES = ("indicator_narrative", "province_plan_context", "national_plan_context", "web_context_search",
          "plan_alignment", "swot_analysis", "investment_recommendations")
ORDER = ("indicator_narrative", "national_plan_context", "province_plan_context", "web_context_search",
         "plan_alignment", "swot_analysis", "investment_recommendations")
STEP_GROUPS = (
    ("evidence", "Evidence", ("indicator_narrative", "national_plan_context", "province_plan_context", "web_context_search")),
    ("alignment", "Alignment", ("plan_alignment",)),
    ("swot", "SWOT", ("swot_analysis",)),
    ("recommendations", "Recommendations", ("investment_recommendations",)),
)
DOCUMENT_STAGES = {"national_plan_context", "province_plan_context"}
DOCUMENT_MODEL = "document-parser"
visitor_limiter = RateLimiter(constants.AI_VISITOR_HOURLY_LIMIT, 3600)


def availability() -> dict[str, bool]:
    ready = client.configured()
    return {"ai": ready, "web": ready and models.supports("web_search"), "enabled": not constants.AI_GENERATION_DISABLED}


def expand_outputs(outputs: list[str], local_plan: bool) -> list[str]:
    chosen = set(outputs)
    if "recommendations" in chosen:
        chosen.add("swot")
    if "swot" in chosen:
        chosen |= {"alignment", "narrative"}
    if not local_plan:
        chosen -= {"alignment", "swot", "recommendations"}
    return [o for o in ("narrative", "alignment", "swot", "recommendations") if o in chosen]


def plan_stages(outputs: list[str], web_search: bool, local_plan: bool) -> list[str]:
    expanded = set(expand_outputs(outputs, local_plan))
    stages: set[str] = set()
    if "narrative" in expanded:
        stages.add("indicator_narrative")
    if "alignment" in expanded:
        stages |= {"national_plan_context", "province_plan_context", "plan_alignment"}
    if "swot" in expanded:
        stages.add("swot_analysis")
    if "recommendations" in expanded:
        stages.add("investment_recommendations")
    if web_search and stages:
        stages.add("web_context_search")
    return [s for s in ORDER if s in stages]


def local_plan_unit(country: Country, row: dict[str, Any]) -> tuple[str, str]:
    if country.plan_source_level == "local":
        return row["name"], country.local_level.singular
    top = country.filter_levels[0]
    return row["areas"][top.key]["name"], top.singular


def _average(values: list[float | None]) -> float | None:
    finite = [v for v in values if v is not None]
    return round(sum(finite) / len(finite), 2) if finite else None


def _peers(data: CountryModel, unit_id: str) -> tuple[dict[int, dict], list[dict], list[dict]]:
    tables = {year: data.scores(year) for year in data.years}
    members = [u for u in data.units if all(u["id"] in tables[y] for y in data.years)]
    me = data.unit_index[unit_id]
    return tables, members, [u for u in members if u["names"]["province"] == me["names"]["province"]]


def _points(data: CountryModel, unit_id: str, index: int) -> list[dict[str, Any]]:
    """Per year: the unit's value at score-row ``index`` and its area and national averages."""
    tables, members, same_area = _peers(data, unit_id)
    points = []
    for year in data.years:
        table = tables[year]
        value = lambda uid: (table.get(uid) or [None] * (index + 1))[index]  # noqa: E731
        points.append({"year": year, "municipalityValue": value(unit_id), "provinceAverage": _average([value(u["id"]) for u in same_area]),
                       "nationalAverage": _average([value(u["id"]) for u in members])})
    return points


def indicator_series(data: CountryModel, unit_id: str, theme: str) -> list[dict[str, Any]]:
    out = []
    for component in catalog.components_of(theme):
        points = _points(data, unit_id, 4 + catalog.COMPONENT_INDEX[component.id])
        out.append({"componentId": component.id, "indicatorId": catalog.COMPONENT_INDICATOR.get(component.id, component.id), "label": component.canonical,
                    "description": catalog.description_of(component.id), "points": points, "singleYearOnly": len(data.years) <= 1})
    return out


def theme_rank(data: CountryModel, unit_id: str, year: int, theme: str) -> dict[str, int] | None:
    """The unit's national rank on the theme score in ``year`` (1 = highest)."""
    index = 1 + catalog.PILLARS.index(theme)
    values = {uid: row[index] for uid, row in data.scores(year).items() if row and row[index] is not None}
    if unit_id not in values:
        return None
    return {"year": year, "rank": 1 + sum(1 for v in values.values() if v > values[unit_id]), "of": len(values)}


def build_context(data: CountryModel, unit_id: str, year: int, theme: str) -> dict[str, Any]:
    country = data.country
    row = data.row(year, unit_id)
    if row is None or not row["scored"]:
        raise ValueError("The unit has no scores in this release.")
    plan_name, plan_label = local_plan_unit(country, row)
    plans = data.plan_sources
    candidates = plans["local"].get(data.plan_key(row), [])
    national = []
    if country.national_plan:
        national.append({"title": country.national_plan.title, "link": country.national_plan.url})
    national += [d for d in plans["national"] if not country.national_plan or d["link"] != country.national_plan.url]
    score_id = f"{theme}_score"
    return {
        "country": {"code": country.iso3, "slug": country.slug, "name": country.name},
        "releaseKey": country.release_key(year),
        "year": year,
        "municipality": {"id": row["id"], "key": row["key"], "name": row["name"], "district": row["names"]["district"], "province": row["names"]["province"]},
        "score": {"id": score_id, "label": catalog.SCORE_LABELS[score_id]},
        "unitLabel": country.local_level.singular,
        "areaLevelLabel": country.filter_levels[0].singular,
        "themeSeries": _points(data, unit_id, 1 + catalog.PILLARS.index(theme)),
        "themeRank": theme_rank(data, unit_id, year, theme),
        "indicatorSeries": indicator_series(data, unit_id, theme),
        "provincePlanCandidates": candidates,
        "nationalPlanSources": national,
        "localPlanUnitName": plan_name,
        "localPlanUnitLabel": plan_label,
        "localPlanAvailable": bool(candidates),
    }


def scope_of(context: dict[str, Any]) -> dict[str, Any]:
    return {"countryCode": context["country"]["code"], "releaseKey": context["releaseKey"], "unitKey": context["municipality"]["key"], "scoreId": context["score"]["id"]}


def _result(stage: str, rendered: str | None, structured: dict[str, Any], refs: list[dict[str, Any]], model: str,
            status: str = "completed", error: str | None = None, cache_status: str = "generated") -> dict[str, Any]:
    return {"stage": stage, "status": status, "cacheHit": False, "cacheStatus": cache_status, "renderedOutput": rendered,
            "structuredOutput": structured, "sourceReferences": refs, "modelName": model, "promptVersion": constants.AI_PROMPT_VERSION,
            "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "errorMessage": error}


def failure(stage: str, message: str) -> dict[str, Any]:
    return _result(stage, None, {}, [], constants.MAI_MODEL, "failed", message, "failed")


def load_cached(context: dict[str, Any]) -> dict[str, dict[str, Any]]:
    scope = scope_of(context)
    out = {}
    for stage in STAGES:
        hit = cache.load_local(scope, stage)
        if hit:
            out[stage] = {**hit, "cacheHit": True, "cacheStatus": "cache_hit"}
    return out


def _document(stage: str, source: dict[str, Any], label: str, area: str | None, country: str) -> dict[str, Any]:
    log.info("%s: %s uses \"%s\" (%s)", stage, label, source["title"], documents.show_url(source["link"]))
    data, content_type, final_url = documents.fetch_document(source["link"])
    text = documents.extract_text(data, content_type)
    if len(text.strip()) < 200:
        log.warning("%s: only %d characters of text from %s (%s); at least 200 are needed", stage, len(text.strip()),
                    documents.show_url(final_url), content_type or "no content-type")
        raise RuntimeError("No readable text could be extracted from the plan document.")
    passages = documents.passages(text)
    log.info("%s: %d characters, %d passages kept from %s", stage, len(text), len(passages), documents.show_url(final_url))
    preview = "\n\n".join(p["text"] for p in passages[:12]) or text[:12000]
    structured = {"countryCode": country, "sourceType": "national_plan" if stage == "national_plan_context" else "province_plan", "title": source["title"],
                  "province": area, "sourceUrlOrPath": final_url, "contentMode": "full_text", "extractedText": text[:200000], "passages": passages,
                  "contentFingerprint": cache.fingerprint(text), "extractionVersion": "v2"}
    rendered = "\n".join([f"Source: {label}", f"Title: {source['title']}", "Content mode: full_text", f"Captured passages: {len(passages)}", "", preview])
    return _result(stage, rendered, structured, [{"label": source["title"], "type": "document", "source": final_url}], DOCUMENT_MODEL)


_DEP_NAMES = {"indicator_narrative": "Indicator narrative", "province_plan_context": "The local/SNG plan context", "national_plan_context": "The national plan context",
              "plan_alignment": "Plan alignment", "swot_analysis": "SWOT"}
_STAGE_NAMES = {"plan_alignment": "plan alignment", "swot_analysis": "SWOT", "investment_recommendations": "recommendations"}


def _needs(results: dict[str, dict], stage: str, *deps: str) -> None:
    for dep in deps:
        if not results.get(dep) or results[dep].get("status") != "completed":
            raise RuntimeError(f"{_DEP_NAMES[dep]} must be generated before {_STAGE_NAMES[stage]} can run.")


def _web_summary(results: dict[str, dict]) -> str | None:
    web = results.get("web_context_search")
    if web and web.get("status") == "completed" and not web.get("structuredOutput", {}).get("skipped"):
        return web.get("renderedOutput")
    return None


def _generate(stage: str, context: dict[str, Any], results: dict[str, dict]) -> dict[str, Any]:
    refs_data = [{"label": f"{context['country']['name']} PIL indicator series", "type": "indicator_series", "source": context["releaseKey"]}]
    if stage == "indicator_narrative":
        reply = client.generate(prompt.SYSTEM, prompt.indicator_narrative(context))
        return _result(stage, reply.text, {"series": len(context["indicatorSeries"])}, refs_data, reply.model)
    if stage == "province_plan_context":
        if not context["provincePlanCandidates"]:
            log.warning("%s: no plan row is filed under \"%s\" for %s in %s; add one there (plan_level, province = that name)", stage,
                        context["localPlanUnitName"], context["country"]["code"], constants.UC_SHARED_TABLES["plan_sources"])
            raise RuntimeError(f"No local/SNG plan URL is available for {context['localPlanUnitName']}.")
        return _document(stage, context["provincePlanCandidates"][0], f"{context['localPlanUnitName']} local/SNG plan", context["localPlanUnitName"], context["country"]["code"])
    if stage == "national_plan_context":
        if not context["nationalPlanSources"]:
            log.warning("%s: %s has no national plan (none in its country config nor in %s)", stage, context["country"]["code"],
                        constants.UC_SHARED_TABLES["plan_sources"])
            raise RuntimeError("No national plan is tracked for this country.")
        return _document(stage, context["nationalPlanSources"][0], f"{context['country']['name']} national plan", None, context["country"]["code"])
    if stage == "web_context_search":
        if not models.supports("web_search"):
            return _result(stage, "Web search is not available with the configured model.", {"skipped": True}, [], "none", cache_status="failed")
        reply = client.generate(prompt.SYSTEM, prompt.web_search(context), web_search=True)
        # Uncited web text cannot be checked, so it never reaches later stages.
        if reply.text.strip().upper().startswith("NO RELEVANT RESULTS") or not reply.citations:
            return _result(stage, "The web search found no relevant, citable sources.", {"skipped": True}, [], reply.model)
        refs = [{"label": c["title"], "type": "web_search", "source": c["url"]} for c in reply.citations]
        return _result(stage, reply.text, {"hits": reply.citations}, refs, reply.model)
    if stage == "plan_alignment":
        _needs(results, stage, "province_plan_context", "national_plan_context")
        reply = client.generate(prompt.SYSTEM, prompt.plan_alignment(results["province_plan_context"]["structuredOutput"],
                                                                     results["national_plan_context"]["structuredOutput"], context, _web_summary(results)))
        return _result(stage, reply.text, {}, [{"label": "Local/SNG plan", "type": "generated", "source": "province_plan_context"},
                                               {"label": "National plan", "type": "generated", "source": "national_plan_context"}], reply.model)
    if stage == "swot_analysis":
        _needs(results, stage, "indicator_narrative", "province_plan_context", "national_plan_context")
        reply = client.generate(prompt.SYSTEM, prompt.swot(context, results["indicator_narrative"]["renderedOutput"], results["province_plan_context"]["structuredOutput"],
                                                           results["national_plan_context"]["structuredOutput"], _web_summary(results)))
        return _result(stage, reply.text, {}, [{"label": "Indicator narrative", "type": "generated", "source": "indicator_narrative"}], reply.model)
    if stage == "investment_recommendations":
        _needs(results, stage, "indicator_narrative", "plan_alignment", "swot_analysis")
        reply = client.generate(prompt.SYSTEM, prompt.recommendations(context, results["indicator_narrative"]["renderedOutput"], results["plan_alignment"]["renderedOutput"],
                                                                      results["swot_analysis"]["renderedOutput"], _web_summary(results)))
        return _result(stage, reply.text, {}, [{"label": "SWOT analysis", "type": "generated", "source": "swot_analysis"}], reply.model)
    raise ValueError("Unknown stage")


def run_stage(context: dict[str, Any], stage: str, mode: str, visitor: str) -> dict[str, Any]:
    scope = scope_of(context)
    results = load_cached(context)
    if mode != "regenerate" and stage in results:
        return results[stage]
    if mode == "load_cached":
        return failure(stage, "No cached result.")
    if constants.AI_GENERATION_DISABLED:
        return failure(stage, "AI generation is turned off on this site.")
    if stage not in DOCUMENT_STAGES and not client.configured():
        return failure(stage, "AI generation is not configured (mAI Gateway settings missing, or not running on Posit Connect).")
    if stage not in DOCUMENT_STAGES:
        if cache.runs_last_24h() >= constants.AI_DAILY_RUN_LIMIT or not visitor_limiter.hit(visitor):
            return failure(stage, "AI generation limit reached. Try again later.")
    started = time.time()
    where = f"{scope['countryCode']} {context['municipality']['name']} {scope['scoreId']} {scope['releaseKey']}"
    log.info("Brief stage %s started (%s, mode=%s)", stage, where, mode)
    try:
        result = _generate(stage, context, results)
    except Exception as exc:  # noqa: BLE001
        log.warning("Brief stage %s FAILED after %.1fs (%s): %s: %s", stage, time.time() - started, where, type(exc).__name__, exc)
        cache.record_run(scope, stage, "failed")
        return failure(stage, str(exc)[:400] or "This stage failed.")
    log.info("Brief stage %s %s in %.1fs (%s, model=%s, sources=%d)", stage, result["status"], time.time() - started, where,
             result["modelName"], len(result.get("sourceReferences") or []))
    if mode == "regenerate":
        result["cacheStatus"] = "regenerated"
    if not result.get("structuredOutput", {}).get("skipped") or result["modelName"] != "none":
        cache.save(scope, stage, result)
    cache.record_run(scope, stage, result["status"])
    return result


def markdown_export(context: dict[str, Any], results: dict[str, dict], area_line: str) -> str:
    labels = (("Component score analysis", "indicator_narrative"), ("Local/SNG plan context", "province_plan_context"), ("National plan context", "national_plan_context"),
              ("Plan alignment", "plan_alignment"), ("Web context", "web_context_search"), ("SWOT analysis", "swot_analysis"),
              ("Public investment recommendations", "investment_recommendations"))
    value = lambda v: "not recorded" if v in (None, "") else str(v)  # noqa: E731
    clean = lambda text: "\n\n".join(p for p in text.replace("\r\n", "\n").split("\n\n")).strip()  # noqa: E731
    lines = ["# AI Planning Brief", "", f"Country: {context['country']['name']}", f"Local unit: {context['municipality']['name']}, {area_line}",
             f"Score theme: {context['score']['label']}", f"Release: {context['releaseKey']}", f"Year: {context['year']}",
             f"Exported at: {datetime.now(timezone.utc).isoformat(timespec='seconds')}", "",
             "This export preserves AI run provenance so generated outputs can be traced back to cached stage records, prompts, model settings, and evidence fingerprints.", ""]
    for label, stage in labels:
        result = results.get(stage)
        if not result:
            lines += [f"## {label}", "", "Status: not generated", ""]
            continue
        lines += [f"## {label}", "", f"Stage: {stage}", f"Status: {result['status']}", f"Cache status: {value(result.get('cacheStatus'))}",
                  f"Prompt version: {value(result.get('promptVersion'))}", f"Model: {value(result.get('modelName'))}", f"Updated at: {value(result.get('updatedAt'))}"]
        if result.get("errorMessage"):
            lines += ["", "### Error", "", clean(result["errorMessage"])]
        if result.get("renderedOutput"):
            lines += ["", "### Output", "", clean(result["renderedOutput"])]
        if result.get("sourceReferences"):
            lines += ["", "### Sources", "", *[f"- {s['label']} - {s['source']}" for s in result["sourceReferences"]]]
        lines.append("")
    return "\n".join(lines)
