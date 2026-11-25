"""Parse the stages' plain-text output into sections, bullets and citations."""

from __future__ import annotations

import re
from typing import Any

SOURCES = re.compile(r"\s*\[\s*sources?\s*:\s*([^\]]*)\]\s*\.?\s*$", re.I)
MARKER = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s*")


def _strip_md(text: str) -> str:
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"__(.*?)__", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"^#+\s*", "", text, flags=re.M)
    return re.sub(r"\[(?!sources?\s*:)(.*?)\]\((.*?)\)", r"\1", text, flags=re.I)


def _one_line(text: str) -> str:
    return re.sub(r"\s+", " ", _strip_md(text)).strip()


def split_citation(line: str) -> dict[str, Any]:
    cleaned = _one_line(line)
    match = SOURCES.search(cleaned)
    if not match:
        return {"text": cleaned, "sources": []}
    sources = [s.strip() for s in re.split(r"[;,]", match.group(1)) if s.strip()]
    return {"text": cleaned[: match.start()].strip(), "sources": sources}


def _heading_key(line: str) -> str:
    return _one_line(re.sub(r"[:：]\s*$", "", MARKER.sub("", line))).lower()


def _bullet(line: str) -> dict[str, Any] | None:
    cited = split_citation(re.sub(r"^\[?citation\]?[:-]?", "", MARKER.sub("", line), flags=re.I))
    lowered = cited["text"].lower()
    if not cited["text"] or re.fullmatch(r"-+", cited["text"]) or lowered in ("n/a", "none", "not applicable"):
        return None
    return cited


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.replace("\r", "").split("\n") if line.strip()]


def _sections(text: str, headings: dict[str, list[str]], fallback: str | None = None) -> tuple[dict[str, list], bool]:
    sections: dict[str, list] = {key: [] for key in headings}
    current, saw = fallback, False
    for line in _lines(text):
        key = _heading_key(line)
        matched = next((name for name, prefixes in headings.items() if any(key.startswith(p) for p in prefixes)), None)
        if matched and len(key) < 80:
            current, saw = matched, True
            remainder = _bullet(line.split(":", 1)[1]) if ":" in line else None
            if remainder:
                sections[matched].append(remainder)
            continue
        item = _bullet(line)
        if current and item:
            sections[current].append(item)
    return sections, saw


def swot(text: str) -> dict[str, list]:
    return _sections(text, {"strengths": ["strengths"], "weaknesses": ["weaknesses"], "opportunities": ["opportunities"], "threats": ["threats"], "missing": ["missing information"]})[0]


def paragraphs(text: str) -> list[dict[str, Any]]:
    blocks = re.split(r"\n\s*\n|\n(?=\s*(?:[-*•]|\d+[.)])\s)", text.replace("\r", ""))
    return [b for b in (_bullet(block) for block in blocks) if b]


def alignment(text: str) -> dict[str, list]:
    sections, saw = _sections(text, {
        "summary": ["alignment summary"],
        "strengths": ["strongest areas of alignment", "strongest alignment"],
        "gaps": ["most important gaps or tensions", "gaps or tensions", "gaps", "tensions"],
        "implications": ["implications"],
    }, "summary")
    if not saw:
        sections["summary"] = paragraphs(text)
    return sections


def web_context(text: str) -> dict[str, list]:
    return _sections(text, {"takeaways": ["key takeaways"], "signals": ["policy signals"], "risks": ["implementation risks"], "local": ["why this matters locally"]})[0]


FIELD = re.compile(r"^(project description|data-based justification|plan-based justification|implementation risks|implementation actions)\s*:\s*(.*)$", re.I)


def recommendations(text: str) -> list[dict[str, Any]]:
    lines = [_strip_md(line).strip() for line in _lines(text)]
    result: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    field: str | None = None
    for index, line in enumerate(lines):
        numbered = re.match(r"^(\d+)[.)]\s+(.+)$", line)
        following = lines[index + 1] if index + 1 < len(lines) else ""
        if numbered and re.match(r"^project description\s*:", following, re.I):
            current = {"rank": int(numbered.group(1)), "title": _one_line(numbered.group(2)), "description": "", "data": [], "plan": [], "risks": [], "actions": []}
            result.append(current)
            field = None
            continue
        if current is None:
            continue
        match = FIELD.match(line)
        if match:
            name = match.group(1).lower()
            field = "description" if name.startswith("project") else "data" if name.startswith("data") else "plan" if name.startswith("plan") else "risks" if name.endswith("risks") else "actions"
            if match.group(2):
                line = match.group(2)
            else:
                continue
        if field == "description":
            current["description"] = f"{current['description']} {_one_line(line)}".strip()
        elif field == "actions":
            item = _bullet(line)
            if item:
                current["actions"].append(item["text"])
        elif field:
            item = _bullet(line)
            if item:
                current[field].append(item)
    return result


def narrative(text: str) -> list[dict[str, Any]]:
    blocks = []
    for line in _lines(text):
        if re.match(r"^\s*(?:[-*•]|\d+[.)])\s+", line):
            item = _bullet(line)
            if item:
                blocks.append({"kind": "bullet", "item": item})
            continue
        plain = _one_line(line)
        if len(plain) <= 90 and not re.search(r"[.!?\]]$", plain):
            blocks.append({"kind": "heading", "text": plain.rstrip(":")})
        else:
            blocks.append({"kind": "paragraph", "item": split_citation(line)})
    return blocks


def build_sources(results: dict[str, dict], data_label: str) -> list[dict[str, Any]]:
    def links(stage: str) -> list[dict[str, str]]:
        result = results.get(stage)
        if not result or result.get("status") != "completed":
            return []
        return [{"label": ref["label"], "url": ref["source"] if re.match(r"^https?://", ref.get("source", ""), re.I) else ""}
                for ref in result.get("sourceReferences", []) if ref.get("type") in ("document", "web_search")]

    candidates = [
        {"id": "data", "label": data_label, "links": []},
        {"id": "local", "label": "Local plan", "links": links("province_plan_context")},
        {"id": "national", "label": "National plan", "links": links("national_plan_context")},
        {"id": "web", "label": "Web search results", "links": links("web_context_search")},
    ]
    kept = [c for c in candidates if c["id"] == "data" or c["links"]]
    return [{**c, "number": i + 1} for i, c in enumerate(kept)]


def source_for_label(label: str) -> str | None:
    text = label.lower()
    if "web" in text:
        return "web"
    if re.search(r"national|ndp|sixteenth plan", text):
        return "national"
    if re.search(r"local|sng|provincial|district plan|municipal plan|idp|integrated development plan", text):
        return "local"
    if re.search(r"indicator|narrative|score|pil|data", text):
        return "data"
    return None


def citation_numbers(labels: list[str], sources: list[dict[str, Any]], stage: str | None = None) -> list[int]:
    by_id = {s["id"]: s["number"] for s in sources}
    fixed = "data" if stage == "indicator_narrative" else "web" if stage == "web_context_search" else None
    ids = ([fixed] if labels else []) if fixed else [source_for_label(label) for label in labels]
    return sorted({by_id[i] for i in ids if i and i in by_id})
