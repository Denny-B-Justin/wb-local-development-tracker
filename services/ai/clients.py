"""Outbound HTTP for the brief: the LLM, Exa search, and plan-document downloads (SSRF-guarded)."""

from __future__ import annotations

import io
import ipaddress
import re
import socket
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

import constants

USER_AGENT = "LDT-AI/2.0 (+wb-local-development-tracker)"


def generate(system: str, prompt: str) -> tuple[str, str]:
    if not constants.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    response = requests.post(
        f"{constants.OPENAI_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {constants.OPENAI_API_KEY}", "Content-Type": "application/json", "User-Agent": USER_AGENT},
        json={"model": constants.OPENAI_MODEL, "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]},
        timeout=constants.AI_HTTP_TIMEOUT_SECONDS,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"AI request failed ({response.status_code}).")
    payload = response.json()
    text = "\n\n".join(
        (choice.get("message") or {}).get("content") or "" for choice in payload.get("choices", [])
    ).strip()
    if not text:
        raise RuntimeError("The AI service returned an empty response.")
    return text, payload.get("model") or constants.OPENAI_MODEL


def exa_search(query: str, limit: int = 6) -> list[dict[str, Any]]:
    if not constants.EXA_API_KEY:
        return []
    response = requests.post(
        "https://api.exa.ai/search",
        headers={"x-api-key": constants.EXA_API_KEY, "Content-Type": "application/json", "User-Agent": USER_AGENT},
        json={"query": query[:500], "numResults": limit, "type": "auto", "contents": {"text": {"maxCharacters": 4000}}},
        timeout=constants.AI_HTTP_TIMEOUT_SECONDS,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Web search failed ({response.status_code}).")
    hits = []
    for item in response.json().get("results", []):
        url = item.get("url") or ""
        if url.startswith(("https://", "http://")):
            hits.append({"title": (item.get("title") or url)[:300], "url": url, "text": item.get("text") or "",
                         "publishedDate": item.get("publishedDate"), "score": item.get("score")})
    return hits


def _public_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_multicast or address.is_unspecified:
            return False
    return True


def fetch_document(url: str, max_redirects: int = 5) -> tuple[bytes, str, str]:
    """Download a plan document over http(s) from a public host, with a size cap."""
    current = url
    for _ in range(max_redirects + 1):
        parsed = urlparse(current)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or not _public_host(parsed.hostname):
            raise RuntimeError("The plan link is not a public web address.")
        response = requests.get(current, headers={"User-Agent": USER_AGENT, "Accept": "application/pdf,text/html;q=0.8,*/*;q=0.5"},
                                timeout=constants.AI_HTTP_TIMEOUT_SECONDS, stream=True, allow_redirects=False)
        if response.is_redirect:
            current = urljoin(current, response.headers.get("Location", ""))
            continue
        if response.status_code >= 400:
            raise RuntimeError(f"The plan document could not be downloaded ({response.status_code}).")
        buffer = io.BytesIO()
        for chunk in response.iter_content(65536):
            buffer.write(chunk)
            if buffer.tell() > constants.AI_DOCUMENT_MAX_BYTES:
                raise RuntimeError("The plan document is too large to process.")
        return buffer.getvalue(), response.headers.get("Content-Type", "").lower(), current
    raise RuntimeError("Too many redirects for the plan link.")


def extract_text(data: bytes, content_type: str) -> str:
    if data[:5] == b"%PDF-" or "pdf" in content_type:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages[:400])
    text = data.decode("utf-8", errors="ignore")
    text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", text, flags=re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()


def passages(text: str) -> list[dict[str, Any]]:
    blocks = [b.strip() for b in re.split(r"\n{2,}", text) if len(b.strip()) > 80]
    if not blocks:
        words = text.split()
        blocks = [" ".join(words[i:i + 180]) for i in range(0, len(words), 180)]
    return [{"id": f"passage-{i + 1}", "title": None, "text": block[:4000]} for i, block in enumerate(blocks[:80])]
