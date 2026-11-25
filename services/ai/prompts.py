"""Prompts for the planning-brief stages (ported verbatim; cached briefs depend on them)."""

from __future__ import annotations

from typing import Any


def _series(series: list[dict[str, Any]], unit_label: str) -> str:
    blocks = []
    for item in series:
        latest = item["points"][-1] if item["points"] else {}
        year = latest.get("year", "n/a")
        value = lambda key: "n/a" if latest.get(key) is None else latest.get(key)  # noqa: E731
        blocks.append("\n".join([
            f"Score component: {item['label']}",
            f"Description: {item.get('description') or 'No description available.'}",
            f"Latest {unit_label.lower()} score ({year}): {value('municipalityValue')}",
            f"Latest higher-admin average score ({year}): {value('provinceAverage')}",
            f"Latest national average score ({year}): {value('nationalAverage')}",
        ]))
    return "\n\n".join(blocks)


def _excerpt(document: dict[str, Any]) -> str:
    return "\n\n".join(f"Passage {i + 1}: {p['text']}" for i, p in enumerate(document.get("passages", [])[:10]))


def _web(summary: str | None) -> str:
    return summary.strip() if summary and summary.strip() else "No optional external web context was provided."


def _header(context: dict[str, Any]) -> list[str]:
    return [
        f"Country: {context['country']['name']}",
        f"{context['localPlanUnitLabel']}: {context['localPlanUnitName']}",
        f"Selected unit: {context['municipality']['name']}, {context['municipality']['province']}",
        f"Selected score: {context['score']['label']}",
    ]


SYSTEM = " ".join([
    "You are assisting public-sector planners with subnational development analysis.",
    "Work only in English.",
    "The only score themes are Prosperity Score, Infrastructure Score, and Livability Score.",
    "Indicators contribute directly to scores. Do not refer to dimensions or intermediate themes.",
    "Write clearly for policy and investment decision makers.",
    "Be evidence-based and explicit when a conclusion is limited by weak evidence.",
    "Return plain text with explicit section headings.",
    "Do not use markdown emphasis such as **bold** or _italics_.",
    "Do not emit empty bullets, placeholder bullets, or filler text.",
    "Cite evidence in-line at the end of each bullet using the format [Sources: ...].",
])


def indicator_narrative(context: dict[str, Any]) -> str:
    return "\n".join([
        f"Country: {context['country']['name']}",
        f"{context['localPlanUnitLabel']}: {context['localPlanUnitName']}",
        f"Selected unit: {context['municipality']['name']}, {context['municipality']['province']}",
        f"Selected score: {context['score']['label']}",
        "",
        "Indicator evidence:",
        _series(context["indicatorSeries"], context["localPlanUnitLabel"]),
        "",
        "Write a concise local development narrative focused only on the selected score.",
        "Explain which indicators appear to strengthen the selected unit, which weaken it, and what that suggests about local development conditions.",
        "Do not use any local/SNG plan or national plan context in this stage.",
    ])


def plan_alignment(province_doc: dict, national_doc: dict, context: dict, web_summary: str | None) -> str:
    return "\n".join([
        *_header(context), "",
        "Local/SNG plan excerpts:", _excerpt(province_doc), "",
        "National plan excerpts:", _excerpt(national_doc), "",
        "Optional external web context:", _web(web_summary), "",
        "Task: assess whether the local/SNG plan is aligned with the national plan for the selected unit and score theme.",
        "",
        "Return plain text only. Use exactly these section headings in this exact order:",
        "Alignment summary",
        "Strongest areas of alignment",
        "Most important gaps or tensions",
        "Implications for local planning",
        "",
        "Formatting rules:",
        "- Under each heading, write 4 to 6 bullet points.",
        "- Keep each bullet concise: one sentence, or at most two short sentences.",
        "- Every bullet must end with in-line citations in this exact format: [Sources: Local/SNG plan; National plan] or [Sources: Local/SNG plan; National plan; Web context].",
        "- Do not use markdown emphasis, tables, or numbering.",
        "- Do not repeat the heading names inside the bullets.",
        "- Make implications operational for local planning, budgeting, or sequencing.",
    ])


def swot(context: dict, narrative: str, province_doc: dict, national_doc: dict, web_summary: str | None) -> str:
    return "\n".join([
        *_header(context), "",
        "Indicator narrative:", narrative, "",
        "Local/SNG plan excerpts:", _excerpt(province_doc), "",
        "National plan excerpts:", _excerpt(national_doc), "",
        "Optional external web context:", _web(web_summary), "",
        "Task: create a SWOT analysis for this selected unit focused on the selected score.",
        "",
        "Return plain text only. Use exactly these section headings in this exact order:",
        "Strengths", "Weaknesses", "Opportunities", "Threats", "Missing information",
        "",
        "Formatting rules:",
        "- For Strengths, Weaknesses, Opportunities, and Threats, write exactly 3 bullet points each.",
        "- For Missing information, write 0 to 2 bullet points only if a meaningful evidence gap exists.",
        "- Every bullet must end with in-line citations in this exact format: [Sources: Indicator narrative; Local/SNG plan] or a similar evidence combination.",
        "- Do not use markdown emphasis, placeholder bullets, or empty bullets.",
        "- Strengths and Weaknesses must be grounded primarily in the indicator narrative.",
        "- Opportunities and Threats must connect indicator evidence to local/SNG and national planning context.",
        "- Make each bullet decision-relevant for public investment planning rather than generic commentary.",
    ])


def recommendations(context: dict, narrative: str, alignment: str, swot_text: str, web_summary: str | None) -> str:
    return "\n".join([
        *_header(context), "",
        "Indicator narrative:", narrative, "",
        "Local/SNG vs national alignment:", alignment, "",
        "SWOT analysis:", swot_text, "",
        "Optional external web context:", _web(web_summary), "",
        "Task: generate public project investment recommendations.",
        "",
        "Return plain text only as a ranked list of exactly 3 recommendations.",
        "Use this exact template for each recommendation:",
        "",
        "1. Recommendation title",
        "Project Description:",
        "A short paragraph.",
        "Data-Based Justification:",
        "- Bullet 1 [Sources: ...]",
        "- Bullet 2 [Sources: ...]",
        "Plan-Based Justification:",
        "- Bullet 1 [Sources: ...]",
        "- Bullet 2 [Sources: ...]",
        "Implementation Risks:",
        "- Bullet 1 [Sources: ...]",
        "- Bullet 2 [Sources: ...]",
        "Implementation Actions:",
        "1. Action one",
        "2. Action two",
        "3. Action three",
        "",
        "Rules:",
        "- Recommendations must be concrete public investment proposals, not abstract policy ideas.",
        "- Recommendations must be ranked from highest to lowest priority.",
        "- Project descriptions must mention the selected unit and selected score theme where useful.",
        "- Data-Based Justification must draw from the indicator narrative.",
        "- Plan-Based Justification must connect to the local/SNG plan, national plan, and optional web context when relevant.",
        "- Implementation Risks must be specific and operational.",
        "- Do not use markdown emphasis or tables.",
    ])


def web_summary(context: dict, hits: list[dict[str, Any]]) -> str:
    text = "\n\n".join("\n".join([
        f"Hit {i + 1}: {hit['title']}",
        f"URL: {hit['url']}",
        f"Published: {hit.get('publishedDate') or 'unknown'}",
        f"Search score: {hit.get('score') if hit.get('score') is not None else 'unknown'}",
        f"Excerpt: {(hit.get('text') or '')[:2500]}",
    ]) for i, hit in enumerate(hits))
    return "\n".join([
        *_header(context), "",
        "External web search results:", text, "",
        "Summarize the most decision-relevant external context for local planning.",
        "Use a short structured format with the headings: Key takeaways, Policy signals, Implementation risks, and Why this matters locally.",
        "Do not fabricate details not present in the search results.",
    ])


def web_query(context: dict) -> str:
    return " ".join([
        f'"{context["localPlanUnitName"]}" "{context["country"]["name"]}" local development plan',
        f'"{context["municipality"]["name"]}" "{context["localPlanUnitLabel"]}"',
        f'"{context["score"]["label"]}"',
        "public investment priorities",
    ])
