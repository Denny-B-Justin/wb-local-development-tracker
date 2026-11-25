"""Plan documents: SSRF-guarded download, text extraction, passages, and passage selection for a prompt."""

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
STORED_PASSAGES = 80


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


def passages(text: str, limit: int | None = STORED_PASSAGES) -> list[dict[str, Any]]:
    blocks = [b.strip() for b in re.split(r"\n{2,}", text) if len(b.strip()) > 80]
    if not blocks:
        words = text.split()
        blocks = [" ".join(words[i:i + 180]) for i in range(0, len(words), 180)]
    return [{"id": f"passage-{i + 1}", "title": None, "text": block[:4000]} for i, block in enumerate(blocks[:limit])]


def select(document: dict[str, Any], terms: list[str], limit: int = 12) -> list[tuple[int, str]]:
    """The ``limit`` passages most about ``terms``, in document order, as (1-based number, text).

    Reads the whole extracted text when it is stored, so relevant passages deep in a long plan
    are found, not just its opening pages. Numbers are stable, so citations can name them.
    """
    blocks = passages(document["extractedText"], None) if document.get("extractedText") else document.get("passages", [])
    if not blocks:
        return []
    stems = sorted({re.escape(t.lower()) for t in terms if t.strip()}, key=len, reverse=True)
    pattern = re.compile(r"\b(?:" + "|".join(stems) + r")", re.I) if stems else None
    hits = [len(pattern.findall(b["text"])) if pattern else 0 for b in blocks]
    ranked = sorted(range(len(blocks)), key=lambda i: (-hits[i], i))[:limit]
    # No passage mentions the theme: fall back to the opening passages rather than random ones.
    keep = sorted(i for i in ranked if hits[i]) or list(range(min(limit, len(blocks))))
    return [(i + 1, blocks[i]["text"]) for i in keep]
