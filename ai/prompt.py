"""Prompts for the planning-brief stages.

Accuracy comes from three rules: every figure the model may state is computed here and printed
once (it copies, never calculates); plan excerpts are numbered passages chosen for the score
theme, so each claim cites a passage that can be checked; and every bullet carries a citation
tag that ai/parse.py maps to the brief's numbered sources. Section headings and the
recommendation template are read by ai/parse.py: change them together. Any change to a prompt
needs a new AI_PROMPT_VERSION so cached briefs are regenerated.
"""

from __future__ import annotations

from typing import Any

from . import documents

POSITION_BAND = 5.0  # points from a reference average before a score counts as above / below it
TREND_BAND = 3.0  # points of change over the release years before a trend counts as improving / declining
PLAN_PASSAGES = 12

# Word stems that mark a plan passage as relevant to a score theme (matched at word starts).
THEME_TERMS: dict[str, list[str]] = {
    "prosperity": ["econom", "income", "employ", "job", "livelihood", "poverty", "enterprise", "business", "industr", "market", "trade", "invest",
                   "tourism", "tourist", "agricultur", "farm", "crop", "irrigat", "electrif", "electric", "energy", "urban", "built-up", "settlement",
                   "growth", "revenue", "productiv", "value chain"],
    "infrastructure": ["infrastructure", "road", "transport", "bridge", "connectivity", "internet", "broadband", "mobile", "digital", "telecom", "ict",
                       "fibre", "fiber", "network", "hospital", "health", "clinic", "school", "education", "access", "facilit", "service delivery"],
    "livability": ["environment", "climate", "emission", "carbon", "greenhouse", "air quality", "pollution", "pm2", "forest", "deforest", "flood",
                   "heat", "disaster", "resilien", "hazard", "risk reduction", "adaptation", "mitigation", "waste", "sanitation", "green", "biodiversity"],
}

SYSTEM = """You are a senior subnational development analyst. You write planning briefs for public-sector planners and investment officers who will act on them, so every statement must be accurate, specific and traceable to the evidence supplied.

EVIDENCE RULES (these override every other instruction)
1. Use only the evidence in the user message: the PIL score evidence, the numbered plan passages, earlier stage outputs, and the web context. Do not add facts from your own knowledge about the place, its projects, budgets, population, institutions or history.
2. Copy every number exactly as printed in the evidence, with its year. Never calculate, round, average, estimate or extrapolate a new figure. To compare, use the differences already printed.
3. Attribute plan content only to the numbered passage that contains it. Do not claim a plan says, targets or funds something unless a cited passage states it.
4. The plan excerpts are a selection, not the whole plan. When something is not in them, write that it was "not found in the supplied excerpts", never that the plan lacks it.
5. When evidence is thin, missing or contradictory, say so in one plain sentence instead of filling the gap. Do not hedge statements the evidence fully supports.
6. Use place, plan and programme names exactly as written in the evidence.

HOW TO READ PIL SCORES
- Every score is on a 0-100 scale and is relative: the unit is compared with the other local units of the same country in the same release. A higher score always means stronger relative performance, including for risk and emission components, where a higher score means a relatively better (lower-risk, lower-emission) position.
- There are exactly three score themes: Prosperity Score, Infrastructure Score and Livability Score. Each is built directly from its component scores. Do not invent dimensions, sub-themes, weights or causes.
- A score shows relative position, not absolute conditions or causes. Say what the scores show; do not assert why unless a cited passage explains it.
- "Above", "below" and "in line with" an average, and "improving", "declining" and "stable" trends, are pre-computed in the evidence. Use those labels as given.

OUTPUT RULES
- English only. Plain text with the exact section headings requested, each heading alone on its line with no colon. No markdown: no #, **, _, tables, code blocks or links in markdown form.
- Bullets start with "- ". No empty, placeholder, duplicate or filler bullets, and no introductions or closing remarks outside the requested sections.
- End every bullet (and every paragraph, where paragraphs are requested) with its citations in exactly this form: [Sources: label; label]. Allowed labels: PIL scores, Local/SNG plan P<n>, National plan P<n>, Web context. Name the passage numbers you used (for example: [Sources: PIL scores; Local/SNG plan P4; National plan P12]). Cite only evidence you actually used.
- Be concise and concrete: name the component, the figure and the year rather than describing them vaguely."""


def _n(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}"


def _diff(value: float | None, reference: float | None) -> float | None:
    """Difference of the printed (1-decimal) figures, so a reader re-doing the subtraction gets the same number."""
    if value is None or reference is None:
        return None
    return round(round(value, 1) - round(reference, 1), 1) + 0.0  # + 0.0 turns -0.0 into 0.0


def _position(diff: float | None) -> str:
    if diff is None:
        return "no comparison available"
    return "above" if diff >= POSITION_BAND else "below" if diff <= -POSITION_BAND else "in line with"


def _trend(points: list[dict[str, Any]]) -> str:
    known = [p for p in points if p.get("municipalityValue") is not None]
    if len(known) < 2:
        return "Trend: not available (one year of data)."
    first, last = known[0], known[-1]
    change = _diff(last["municipalityValue"], first["municipalityValue"])
    label = "improving" if change >= TREND_BAND else "declining" if change <= -TREND_BAND else "stable"
    return f"Trend {first['year']} to {last['year']}: {change:+.1f} points ({label})."


def _score_block(title: str, points: list[dict[str, Any]], context: dict[str, Any], description: str | None = None, rank: dict | None = None) -> str:
    area = context["areaLevelLabel"].lower()
    lines = [title]
    if description:
        lines.append(f"  Measures: {description}")
    latest = next((p for p in reversed(points) if p.get("municipalityValue") is not None), None)
    if latest is None:
        return "\n".join([*lines, "  No score for this unit in the release."])
    to_area, to_nation = _diff(latest["municipalityValue"], latest["provinceAverage"]), _diff(latest["municipalityValue"], latest["nationalAverage"])
    rank_text = f" | national rank {rank['rank']} of {rank['of']} (1 = highest)" if rank else ""
    lines += [
        f"  Latest year {latest['year']}: unit {_n(latest['municipalityValue'])} | {area} average {_n(latest['provinceAverage'])} | national average {_n(latest['nationalAverage'])}{rank_text}",
        f"  Versus {area} average: {'n/a' if to_area is None else f'{to_area:+.1f}'} points ({_position(to_area)} the {area} average)",
        f"  Versus national average: {'n/a' if to_nation is None else f'{to_nation:+.1f}'} points ({_position(to_nation)} the national average)",
        f"  {_trend(points)}",
        "  By year (unit / " + area + " average / national average): " + "; ".join(
            f"{p['year']}: {_n(p['municipalityValue'])} / {_n(p['provinceAverage'])} / {_n(p['nationalAverage'])}" for p in points),
    ]
    return "\n".join(lines)


def score_evidence(context: dict[str, Any]) -> str:
    """The PIL evidence block shared by every stage (cite as "PIL scores")."""
    unit = context["municipality"]
    blocks = [
        f"PIL SCORE EVIDENCE (cite as: PIL scores)",
        f"Unit: {unit['name']} ({context['unitLabel']}), {unit['province']} {context['areaLevelLabel']}, {context['country']['name']}. Release {context['releaseKey']}.",
        f"Scores are 0-100 and relative to the {context['themeRank']['of'] if context.get('themeRank') else 'other'} scored local units of {context['country']['name']}. "
        f"'Above' / 'below' mean at least {POSITION_BAND:.0f} points from the average; trends count as improving or declining at {TREND_BAND:.0f} points of change or more.",
        "",
        _score_block(f"Theme score: {context['score']['label']}", context["themeSeries"], context, rank=context.get("themeRank")),
    ]
    for item in context["indicatorSeries"]:
        blocks += ["", _score_block(f"Component: {item['label']}", item["points"], context, item.get("description"))]
    return "\n".join(blocks)


def _header(context: dict[str, Any]) -> str:
    unit = context["municipality"]
    return "\n".join([
        f"Country: {context['country']['name']}",
        f"Selected unit: {unit['name']} ({context['unitLabel']}), {unit['province']} {context['areaLevelLabel']}",
        f"Local/SNG plan level: {context['localPlanUnitLabel']} of {context['localPlanUnitName']}",
        f"Selected score theme: {context['score']['label']}",
    ])


def _terms(context: dict[str, Any]) -> list[str]:
    theme = context["score"]["id"].removesuffix("_score")
    unit = context["municipality"]
    return [*THEME_TERMS.get(theme, []), unit["name"], unit["province"], context["localPlanUnitName"]]


def plan_excerpts(document: dict[str, Any], label: str, context: dict[str, Any]) -> str:
    chosen = documents.select(document, _terms(context), PLAN_PASSAGES)
    title = document.get("title") or label
    if not chosen:
        return f"{label.upper()}: {title}\nNo readable passages were extracted."
    head = f"{label.upper()}: {title} ({len(chosen)} passages selected for the {context['score']['label']} theme; cite as {label} P<n>)"
    return "\n\n".join([head, *[f"{label} P{number}: {text}" for number, text in chosen]])


def _web(summary: str | None) -> str:
    if summary and summary.strip():
        return "WEB CONTEXT (cite as: Web context)\n" + summary.strip()
    return "WEB CONTEXT\nNone was gathered for this brief. Do not cite Web context."


def indicator_narrative(context: dict[str, Any]) -> str:
    unit = context["municipality"]["name"]
    return "\n".join([
        _header(context), "",
        score_evidence(context), "",
        f"TASK: Write the score narrative for {unit} on the {context['score']['label']}, using only the PIL score evidence above. Do not use plans or outside knowledge.",
        "",
        "Use exactly these section headings, in this order:",
        "Overview",
        "Strengths",
        "Weaknesses",
        "Trends to watch",
        "What this suggests for local development",
        "Data limitations",
        "",
        "Section rules:",
        f"- Overview: one paragraph of 2 to 3 sentences. State the latest {context['score']['label']} with its year, its national rank, and its position against the {context['areaLevelLabel'].lower()} and national averages, then the trend. End with [Sources: PIL scores].",
        "- Strengths: one bullet per component that is above the national average in the latest year, strongest first, at most 4. Give the unit's score, the national average and the difference. If none, write one bullet saying no component is above the national average.",
        "- Weaknesses: one bullet per component that is below the national average in the latest year, weakest first, at most 4. Same figures as Strengths. If none, write one bullet saying no component is below the national average.",
        "- Trends to watch: 1 to 3 bullets on components whose trend is improving or declining, with the change in points and the years. If every trend is stable or unavailable, write one bullet saying so.",
        "- What this suggests for local development: 2 to 3 bullets that interpret the pattern for planners (for example where the unit lags its own area, or a strength to build on). Interpret only what the scores show; do not name causes.",
        "- Data limitations: 0 to 2 bullets, only for real gaps such as missing years or components without a score. Omit the heading if there are none.",
        "- Every bullet ends with [Sources: PIL scores].",
    ])


def web_search(context: dict[str, Any]) -> str:
    unit = context["municipality"]
    components = ", ".join(item["label"].removesuffix(" Score") for item in context["indicatorSeries"])
    return "\n".join([
        _header(context), "",
        f"TASK: Use the web search tool to find recent, verifiable information that matters for public investment planning in {unit['name']}, "
        f"{unit['province']} {context['areaLevelLabel']}, {context['country']['name']}, on the {context['score']['label']} theme ({components}).",
        "",
        "How to search:",
        f"- Search for the unit first. If you find little that is specific to {unit['name']}, widen to {unit['province']}, then to {context['country']['name']}, and say in each bullet which level the finding is about.",
        f"- Look for: the {context['localPlanUnitLabel'].lower()} and national development plans and budgets, approved or planned public projects, programmes of development partners, sector policies, and recent events (disasters, major investments, service disruptions) relevant to the theme.",
        "- Prefer, in order: official government sources; multilateral development banks and UN agencies; established national or international news media. Avoid blogs, forums, social media and undated pages.",
        "- Prefer sources published in the last three years, and give the year of each finding.",
        "",
        "Accuracy rules:",
        "- State only facts that appear in pages you opened, with the page cited. Copy figures, dates and names exactly. Never fill gaps from memory.",
        "- If sources disagree, give both and say they disagree.",
        "- If you find nothing relevant at any level, reply with exactly NO RELEVANT RESULTS and nothing else.",
        "",
        "Output: plain text with exactly these headings, in this order, each followed by 2 to 4 bullets:",
        "Key takeaways",
        "Policy signals",
        "Implementation risks",
        "Why this matters locally",
        "",
        "Bullet rules: one or two sentences each; put any link before the citation tag; end every bullet with [Sources: Web context].",
    ])


def plan_alignment(province_doc: dict, national_doc: dict, context: dict, web_summary: str | None) -> str:
    theme = context["score"]["label"]
    return "\n".join([
        _header(context), "",
        plan_excerpts(province_doc, "Local/SNG plan", context), "",
        plan_excerpts(national_doc, "National plan", context), "",
        _web(web_summary), "",
        f"TASK: Assess how well the local/SNG plan for {context['localPlanUnitName']} aligns with the national plan on the {theme} theme, "
        f"as it affects {context['municipality']['name']}.",
        "",
        "Alignment means the two plans share objectives, targets, programmes, sector priorities or sequencing. A gap is a national priority with no matching local commitment in the excerpts, "
        "or a local priority that conflicts with national direction. A tension is where both plans address the same issue in incompatible ways.",
        "",
        "Use exactly these section headings, in this order:",
        "Alignment summary",
        "Strongest areas of alignment",
        "Most important gaps or tensions",
        "Implications for local planning",
        "",
        "Section rules:",
        "- Alignment summary: 2 to 3 bullets giving the overall judgement (strong, partial or weak alignment) and the main reason.",
        "- Strongest areas of alignment: 3 to 5 bullets. Each names the shared priority and cites at least one Local/SNG plan passage and one National plan passage that both state it.",
        "- Most important gaps or tensions: 3 to 5 bullets, most important first. Cite the passage that states the priority and say the matching commitment was not found in the supplied excerpts.",
        "- Implications for local planning: 3 to 5 bullets with operational consequences for planning, budgeting or sequencing in the unit.",
        "- Use the web context only to confirm or update a point, and cite it when you do.",
        f"- Stay on the {theme} theme; ignore unrelated plan content.",
        "- Each bullet is one sentence, or at most two short sentences, ending with its citation tag.",
    ])


def swot(context: dict, narrative: str, province_doc: dict, national_doc: dict, web_summary: str | None) -> str:
    return "\n".join([
        _header(context), "",
        score_evidence(context), "",
        "SCORE NARRATIVE FROM THE PREVIOUS STAGE (its claims rest on the PIL scores; cite them as PIL scores)",
        narrative, "",
        plan_excerpts(province_doc, "Local/SNG plan", context), "",
        plan_excerpts(national_doc, "National plan", context), "",
        _web(web_summary), "",
        f"TASK: Write a SWOT analysis of {context['municipality']['name']} for the {context['score']['label']}, for use in public investment planning.",
        "",
        "Use exactly these section headings, in this order:",
        "Strengths",
        "Weaknesses",
        "Opportunities",
        "Threats",
        "Missing information",
        "",
        "Section rules:",
        "- Strengths and Weaknesses: exactly 3 bullets each, internal to the unit and grounded in the PIL score evidence. Name the component and give its latest score against the national average.",
        "- Opportunities: exactly 3 bullets. Each links a score gap or strength to a programme, priority or investment stated in a cited plan passage or the web context.",
        "- Threats: exactly 3 bullets. Each names an external risk stated in a cited plan passage or the web context (for example hazards, funding or capacity constraints) and the component it puts at risk.",
        "- Missing information: 0 to 2 bullets, only for evidence gaps that would change a decision. Omit the heading if there are none.",
        "- No bullet may repeat another. Every bullet must be specific to this unit and decision-relevant, not generic commentary.",
    ])


def recommendations(context: dict, narrative: str, alignment: str, swot_text: str, web_summary: str | None) -> str:
    return "\n".join([
        _header(context), "",
        score_evidence(context), "",
        "SCORE NARRATIVE (cite as PIL scores)", narrative, "",
        "PLAN ALIGNMENT (its citations name the plan passages; carry those passage numbers over)", alignment, "",
        "SWOT ANALYSIS", swot_text, "",
        _web(web_summary), "",
        f"TASK: Recommend the three public investment projects that would most improve the {context['score']['label']} of {context['municipality']['name']}.",
        "",
        "How to choose and rank:",
        "- Each project must target one or more components that are below the national or area average, or declining, in the PIL score evidence.",
        "- Rank by: size of the score gap it addresses, then strength of plan support (a cited plan priority beats none), then feasibility for local or subnational government.",
        "- Each project is a concrete public investment: a named type of asset or service in a stated place (for example upgrading a road segment to all-weather standard, or extending fibre to schools). Not a policy, study or awareness campaign.",
        "- Do not state costs, budgets, beneficiaries or timelines unless they appear in the evidence; if one is needed, put it under Implementation Actions as something to establish.",
        "",
        "Return exactly 3 recommendations, ranked highest priority first, each in exactly this template (keep the field names and order):",
        "",
        "1. Recommendation title",
        "Project Description:",
        "One short paragraph: what is built or delivered, where, and which components it targets.",
        "Data-Based Justification:",
        "- The component, its latest score and its gap to the average, copied from the evidence [Sources: PIL scores]",
        "- A second data point (trend or related component) [Sources: PIL scores]",
        "Plan-Based Justification:",
        "- The plan priority this delivers, with passage numbers [Sources: Local/SNG plan P<n>; National plan P<n>]",
        "- A second plan or web point, or a sentence saying plan support was not found in the supplied excerpts [Sources: ...]",
        "Implementation Risks:",
        "- A specific, operational risk to delivery [Sources: ...]",
        "- A second specific risk [Sources: ...]",
        "Implementation Actions:",
        "1. First concrete step, with who acts if the evidence says so",
        "2. Second step",
        "3. Third step",
        "",
        "Rules: titles are short and name the asset or service; numbered actions carry no citation tag; every bullet ends with its citation tag; no markdown or tables.",
    ])
