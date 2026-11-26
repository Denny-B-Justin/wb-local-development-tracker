"""Plan documents: SSRF-guarded download, text extraction, passages, and passage selection for a prompt."""

from __future__ import annotations

import io
import ipaddress
import logging
import re
import socket
import time
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

import constants

log = logging.getLogger(__name__)

USER_AGENT = "LDT-AI/2.0 (+wb-local-development-tracker)"
# DNS64 networks answer IPv4-only hosts with this IPv6 prefix plus the real IPv4 address in the last 32 bits.
NAT64_PREFIX = ipaddress.ip_network("64:ff9b::/96")
STORED_PASSAGES = 80
MAX_PDF_PAGES = 400


def show_url(url: str) -> str:
    """The URL for logs: scheme, host and path only, never the query string (it may carry a token)."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.hostname or ''}{parsed.path}"


def _public_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        log.warning("Plan fetch: cannot resolve host %s (%s)", host, exc)
        return False
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if address.version == 6 and address in NAT64_PREFIX:
            address = ipaddress.IPv4Address(int(address) & 0xFFFFFFFF)
        elif address.version == 6 and address.ipv4_mapped:
            address = address.ipv4_mapped
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_multicast or address.is_unspecified:
            log.warning("Plan fetch: host %s resolves to non-public address %s; blocked", host, address)
            return False
    return True


def fetch_document(url: str, max_redirects: int = 5) -> tuple[bytes, str, str]:
    """Download a plan document over http(s) from a public host, with a size cap."""
    current = url
    started = time.time()
    log.info("Plan fetch started: %s", show_url(url))
    for hop in range(max_redirects + 1):
        parsed = urlparse(current)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or not _public_host(parsed.hostname):
            log.warning("Plan fetch BLOCKED: %s is not a public http(s) address", show_url(current))
            raise RuntimeError("The plan link is not a public web address.")
        try:
            response = requests.get(current, headers={"User-Agent": USER_AGENT, "Accept": "application/pdf,text/html;q=0.8,*/*;q=0.5"},
                                    timeout=constants.AI_HTTP_TIMEOUT_SECONDS, stream=True, allow_redirects=False)
        except requests.RequestException as exc:
            log.warning("Plan fetch FAILED after %.1fs: %s | %s: %s (timeout %ds)", time.time() - started, show_url(current),
                        type(exc).__name__, exc, constants.AI_HTTP_TIMEOUT_SECONDS)
            raise
        if response.is_redirect:
            target = urljoin(current, response.headers.get("Location", ""))
            log.info("Plan fetch redirect %d (HTTP %d): %s -> %s", hop + 1, response.status_code, show_url(current), show_url(target))
            current = target
            continue
        content_type = response.headers.get("Content-Type", "").lower()
        if response.status_code >= 400:
            log.warning("Plan fetch FAILED after %.1fs: %s | HTTP %d %s (content-type %s)", time.time() - started, show_url(current),
                        response.status_code, response.reason, content_type or "none")
            raise RuntimeError(f"The plan document could not be downloaded ({response.status_code}).")
        buffer = io.BytesIO()
        for chunk in response.iter_content(65536):
            buffer.write(chunk)
            if buffer.tell() > constants.AI_DOCUMENT_MAX_BYTES:
                log.warning("Plan fetch ABORTED: %s is larger than the %.0f MB limit (AI_DOCUMENT_MAX_BYTES)", show_url(current),
                            constants.AI_DOCUMENT_MAX_BYTES / 1048576)
                raise RuntimeError("The plan document is too large to process.")
        log.info("Plan fetch OK in %.1fs: %s | HTTP %d, %s, %.1f KB, %d redirect(s)", time.time() - started, show_url(current),
                 response.status_code, content_type or "no content-type", buffer.tell() / 1024, hop)
        return buffer.getvalue(), content_type, current
    log.warning("Plan fetch FAILED: more than %d redirects starting from %s", max_redirects, show_url(url))
    raise RuntimeError("Too many redirects for the plan link.")


def extract_text(data: bytes, content_type: str) -> str:
    started = time.time()
    if data[:5] == b"%PDF-" or "pdf" in content_type:
        from pypdf import PdfReader

        try:
            reader = PdfReader(io.BytesIO(data))
            encrypted = reader.is_encrypted
            pages = reader.pages[:MAX_PDF_PAGES]
            texts = [page.extract_text() or "" for page in pages]
        except Exception as exc:  # noqa: BLE001
            log.warning("Plan text extraction FAILED: the PDF could not be read (%s: %s)", type(exc).__name__, exc)
            raise
        text = "\n\n".join(texts)
        empty = sum(1 for t in texts if not t.strip())
        log.info("Plan text extracted in %.1fs: PDF, %d of %d pages read, %d pages without text, %d characters%s", time.time() - started,
                 len(pages), len(reader.pages), empty, len(text.strip()), ", encrypted" if encrypted else "")
        if pages and empty == len(pages):
            log.warning("Plan text extraction: no page has a text layer; the PDF is probably scanned images (needs OCR)")
        return text
    raw = data.decode("utf-8", errors="ignore")
    text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", raw, flags=re.I)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()
    if "html" in content_type or raw.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
        log.warning("Plan text extraction: the link returned an HTML page, not a PDF (%d characters of page text); "
                    "the plan link may point at a landing page instead of the document", len(text))
    else:
        log.info("Plan text extracted: %s, %d characters", content_type or "unknown content-type", len(text))
    return text


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
