#!/usr/bin/env python3
"""Check visitor-facing external links in a built Jekyll site."""

from __future__ import annotations

import concurrent.futures
import ssl
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

SITE = Path(sys.argv[1] if len(sys.argv) > 1 else "_site")
CANONICAL_HOSTS = {"www.soothill.io", "soothill.io"}
USER_AGENT = "Mozilla/5.0 (compatible; SootHillLinkMonitor/1.0; +https://www.soothill.io/)"
RESTRICTED_STATUSES = {401, 403, 429, 451, 999}
RETRYABLE_STATUSES = {408, 425, 429, 500, 502, 503, 504}
TRANSIENT_ERROR_MARKERS = ("timed out", "timeout", "connection reset")
MAX_ATTEMPTS = 2


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "a" and values.get("href"):
            self.links.append(values["href"] or "")
        elif tag == "iframe" and values.get("src"):
            self.links.append(values["src"] or "")


@dataclass(frozen=True)
class ProbeResult:
    url: str
    status: int
    final_url: str
    error: str = ""


def request_once(url: str, method: str) -> ProbeResult:
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "User-Agent": USER_AGENT,
    }
    request = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=8, context=ssl.create_default_context()) as response:
            if method == "GET":
                response.read(1)
            return ProbeResult(url, response.status, response.geturl())
    except urllib.error.HTTPError as exc:
        return ProbeResult(url, exc.code, exc.geturl(), str(exc))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return ProbeResult(url, 0, url, str(exc))


def probe(url: str) -> ProbeResult:
    last = ProbeResult(url, 0, url, "No request attempted")
    for attempt in range(MAX_ATTEMPTS):
        head = request_once(url, "HEAD")
        if 200 <= head.status < 400:
            return head

        get = request_once(url, "GET")
        if 200 <= get.status < 400:
            return get
        last = get

        if get.status in {404, 410}:
            return get
        if get.status not in RETRYABLE_STATUSES and get.status != 0:
            return get
        if attempt + 1 < MAX_ATTEMPTS:
            time.sleep(1.5 * (attempt + 1))
    return last


def page_url(html_file: Path) -> str:
    relative = "/" + html_file.relative_to(SITE).as_posix()
    if relative.endswith("/index.html"):
        relative = relative[: -len("index.html")]
    return f"https://www.soothill.io{relative}"


def main() -> int:
    if not SITE.exists():
        print(f"Build directory does not exist: {SITE}", file=sys.stderr)
        return 2

    sources: dict[str, set[str]] = defaultdict(set)
    for html_file in SITE.rglob("*.html"):
        parser = LinkParser()
        parser.feed(html_file.read_text(encoding="utf-8", errors="replace"))
        source = page_url(html_file)
        for raw_link in parser.links:
            absolute, _fragment = urldefrag(urljoin(source, raw_link))
            parsed = urlparse(absolute)
            if parsed.scheme not in {"http", "https"} or parsed.netloc in CANONICAL_HOSTS:
                continue
            sources[absolute].add(urlparse(source).path)

    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(probe, sorted(sources)))

    failures: list[ProbeResult] = []
    restricted: list[ProbeResult] = []
    for result in results:
        if 200 <= result.status < 400:
            continue
        transient_network_error = result.status == 0 and any(
            marker in result.error.lower() for marker in TRANSIENT_ERROR_MARKERS
        )
        if result.status in RESTRICTED_STATUSES or transient_network_error:
            restricted.append(result)
        else:
            failures.append(result)

    for result in restricted:
        print(
            f"WARNING: external check was inconclusive ({result.status or result.error}) for {result.url} "
            f"(linked from {', '.join(sorted(sources[result.url]))})"
        )

    if failures:
        print("External link validation failed:", file=sys.stderr)
        for result in failures:
            detail = f"; {result.error}" if result.error else ""
            print(
                f"- {result.status or 'network error'} {result.url} "
                f"(linked from {', '.join(sorted(sources[result.url]))}){detail}",
                file=sys.stderr,
            )
        return 1

    print(
        f"Validated {len(results)} external links successfully "
        f"({len(restricted)} inconclusive warnings)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
