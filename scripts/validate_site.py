#!/usr/bin/env python3
"""Validate core SEO and indexing invariants in a built Jekyll site."""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

SITE = Path(sys.argv[1] if len(sys.argv) > 1 else "_site")
CANONICAL_HOST = "www.soothill.io"
FORBIDDEN_PATHS = {"/SETUP-COMPLETE/", "/HOWTO-ADD-POSTS/", "/TODO/", "/blog/categories/"}
OWNERSHIP_FILE = re.compile(r"^/google[0-9a-f]+\.html$")


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.description = ""
        self.canonical = ""
        self.robots = ""
        self.missing_alt = 0
        self.json_ld: list[str] = []
        self._in_title = False
        self._in_json_ld = False
        self._json_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = (values.get("name") or "").lower()
            if name == "description":
                self.description = values.get("content") or ""
            elif name == "robots":
                self.robots = values.get("content") or ""
        elif tag == "link" and (values.get("rel") or "").lower() == "canonical":
            self.canonical = values.get("href") or ""
        elif tag == "img" and "alt" not in values:
            self.missing_alt += 1
        elif tag == "script" and (values.get("type") or "").lower() == "application/ld+json":
            self._in_json_ld = True
            self._json_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "script" and self._in_json_ld:
            self.json_ld.append("".join(self._json_parts).strip())
            self._in_json_ld = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        if self._in_json_ld:
            self._json_parts.append(data)


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    titles: dict[str, list[str]] = defaultdict(list)
    descriptions: dict[str, list[str]] = defaultdict(list)
    pages: dict[str, PageParser] = {}

    if not SITE.exists():
        print(f"Build directory does not exist: {SITE}", file=sys.stderr)
        return 2

    for html_file in SITE.rglob("*.html"):
        parser = PageParser()
        parser.feed(html_file.read_text(encoding="utf-8", errors="replace"))
        relative = "/" + html_file.relative_to(SITE).as_posix()
        if relative.endswith("/index.html"):
            relative = relative[: -len("index.html")]
        pages[relative] = parser

        # Search-engine ownership files intentionally contain only a verification token.
        if OWNERSHIP_FILE.match(relative):
            continue

        if relative != "/404.html" and "noindex" not in parser.robots.lower():
            if not parser.title.strip():
                errors.append(f"Missing title: {relative}")
            else:
                titles[parser.title.strip()].append(relative)
            if not parser.description.strip():
                errors.append(f"Missing description: {relative}")
            else:
                descriptions[parser.description.strip()].append(relative)
            if not parser.canonical:
                errors.append(f"Missing canonical: {relative}")
            else:
                parsed = urlparse(parser.canonical)
                if parsed.scheme != "https" or parsed.netloc != CANONICAL_HOST:
                    errors.append(f"Non-canonical host/scheme on {relative}: {parser.canonical}")
        if parser.missing_alt:
            errors.append(f"Images missing alt on {relative}: {parser.missing_alt}")
        for payload in parser.json_ld:
            try:
                json.loads(payload)
            except json.JSONDecodeError as exc:
                errors.append(f"Invalid JSON-LD on {relative}: {exc}")

    for title, paths in titles.items():
        if len(paths) > 1:
            errors.append(f"Duplicate title {title!r}: {', '.join(paths)}")
    for description, paths in descriptions.items():
        if len(paths) > 1:
            warnings.append(f"Duplicate description on {', '.join(paths)}")

    sitemap = SITE / "sitemap.xml"
    if not sitemap.exists():
        errors.append("Missing sitemap.xml")
    else:
        root = ET.parse(sitemap).getroot()
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [node.text or "" for node in root.findall("sm:url/sm:loc", namespace)]
        if len(urls) != len(set(urls)):
            errors.append("Duplicate URLs in sitemap")
        for url in urls:
            parsed = urlparse(url)
            if parsed.scheme != "https" or parsed.netloc != CANONICAL_HOST:
                errors.append(f"Invalid sitemap host/scheme: {url}")
            if parsed.path in FORBIDDEN_PATHS:
                errors.append(f"Forbidden URL in sitemap: {url}")
            page = pages.get(parsed.path)
            if page is None:
                errors.append(f"Sitemap URL has no built HTML page: {url}")
            elif page.canonical != url:
                errors.append(f"Canonical mismatch for {url}: {page.canonical}")

    for forbidden in FORBIDDEN_PATHS:
        if forbidden in pages:
            errors.append(f"Internal/redirect page is still built: {forbidden}")

    for warning in warnings:
        print(f"WARNING: {warning}")

    if errors:
        print("SEO validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"Validated {len(pages)} HTML pages and sitemap successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
