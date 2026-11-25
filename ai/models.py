"""Models the brief may run on.

The brief needs web search by default and will need file search for uploaded documents,
so it runs on one OpenAI-family model through the mAI ``openai/responses`` endpoint.
Tool support per model (mAI Factory):

    gpt-6-luna         functions, web search, file search    <- default
    gpt-5.6-luna       functions, web search
    gemini-3.8-flash   functions, Google Search              (Interactions API: not wired)
    gemini-3.7-flash   functions, Google Search              (Interactions API: not wired)
    claude-haiku-5-5   functions, bash, text editor, memory, computer use (no web search: not wired)

Only the models below are accepted for MAI_MODEL; anything else leaves generation unconfigured.
"""

from __future__ import annotations

from dataclasses import dataclass

import constants


@dataclass(frozen=True)
class Model:
    id: str
    label: str
    tools: frozenset[str]


MODELS = {m.id: m for m in (
    Model("gpt-6-luna", "GPT-6 Luna", frozenset({"functions", "web_search", "file_search"})),
    Model("gpt-5.6-luna", "GPT-5.6 Luna", frozenset({"functions", "web_search"})),
)}
DEFAULT = "gpt-6-luna"


def selected() -> Model | None:
    return MODELS.get(constants.MAI_MODEL)


def supports(tool: str) -> bool:
    model = selected()
    return bool(model and tool in model.tools)
