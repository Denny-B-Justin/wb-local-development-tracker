"""The only place the app calls an LLM: the OpenAI Responses API through the Posit mAI Gateway.

mAI contract: base URL = MAI_BASE_URL (trailing "/"), the provider endpoint goes in the
``mai-endpoint`` query parameter (MAI_ENDPOINT), and the app identifies itself with
``X-Posit-App-Id`` = CONNECT_CONTENT_GUID, which Posit Connect sets. There is no API key:
``api_key="not-used"`` only satisfies the SDK. Requests from outside Posit Connect get 403.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

import constants

from . import models

log = logging.getLogger(__name__)

_STATUS_HINTS = {
    400: "mAI rejected the request; check MAI_ENDPOINT and that the app runs on Posit Connect",
    403: "mAI refused the request; the app must run on Posit Connect and use an allowed model",
    404: "mAI gateway not found; check MAI_BASE_URL, including its trailing /",
}


@dataclass(frozen=True)
class Completion:
    text: str
    model: str
    citations: list[dict[str, str]] = field(default_factory=list)


def configured() -> bool:
    return bool(constants.MAI_BASE_URL and constants.MAI_ENDPOINT and os.environ.get("CONNECT_CONTENT_GUID") and models.selected())


def _client():
    from openai import OpenAI

    return OpenAI(
        base_url=constants.MAI_BASE_URL,
        api_key="not-used",
        default_headers={"X-Posit-App-Id": os.environ["CONNECT_CONTENT_GUID"], "Content-Type": "application/json", "x-source-type": "interactive"},
        default_query={"mai-endpoint": constants.MAI_ENDPOINT},
        timeout=constants.AI_HTTP_TIMEOUT_SECONDS,
        max_retries=1,
    )


def _citations(response: Any) -> list[dict[str, str]]:
    """URL citations the model attached to its answer (web search results it actually used)."""
    seen: dict[str, dict[str, str]] = {}
    for item in getattr(response, "output", None) or []:
        if getattr(item, "type", None) != "message":
            continue
        for part in getattr(item, "content", None) or []:
            for note in getattr(part, "annotations", None) or []:
                url = getattr(note, "url", None) or ""
                if getattr(note, "type", None) == "url_citation" and url.startswith(("https://", "http://")) and url not in seen:
                    seen[url] = {"title": (getattr(note, "title", None) or url)[:300], "url": url}
    return list(seen.values())


def generate(system: str, prompt: str, web_search: bool = False) -> Completion:
    """One instruction + one input -> text. ``web_search`` lets the model search the web and cite URLs."""
    import openai

    model = models.selected()
    if not configured() or model is None:
        raise RuntimeError("AI generation is not configured (mAI Gateway settings missing, or not running on Posit Connect).")
    # Tool use through mAI is not covered by the mAI Developer Guide; verify on QA.
    tools = [{"type": "web_search"}] if web_search and "web_search" in model.tools else []
    try:
        response = _client().responses.create(model=model.id, instructions=system, input=prompt, **({"tools": tools} if tools else {}))
    except openai.APIStatusError as exc:
        log.warning("mAI request failed (%s): %s", exc.status_code, exc.message)
        raise RuntimeError(f"AI request failed ({exc.status_code}): {_STATUS_HINTS.get(exc.status_code, 'the AI service returned an error')}.") from exc
    except openai.APITimeoutError as exc:
        raise RuntimeError("The AI service timed out. Try again.") from exc
    except openai.APIConnectionError as exc:
        raise RuntimeError("The AI service could not be reached (network connection error).") from exc
    text = (getattr(response, "output_text", None) or "").strip()
    if not text:
        raise RuntimeError("The AI service returned an empty response.")
    return Completion(text, getattr(response, "model", None) or model.id, _citations(response))
