#!/usr/bin/env python3
"""Validate core SEO and indexing invariants in a built Jekyll site."""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

SITE = Path(sys.argv[1] if len(sys.argv) > 1 else "_site")
CANONICAL_HOST = "www.soothill.io"
FORBIDDEN_PATHS = {"/SETUP-COMPLETE/", "/HOWTO-ADD-POSTS/", "/TODO/", "/blog/categories/"}
OWNERSHIP_FILE = re.compile(r"^/google[0-9a-f]+\.html$")
POST_PATH = re.compile(r"^/blog/\d{4}/\d{2}/\d{2}/")
COLLECTION_PATHS = {"/storage/", "/series/strix-halo/"}
SITEMAP_URL = f"https://{CANONICAL_HOST}/sitemap.xml"


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.description = ""
        self.canonical = ""
        self.robots = ""
        self.og_url = ""
        self.missing_alt = 0
        self.h1_count = 0
        self.ids: list[str] = []
        self.links: list[str] = []
        self.images: list[dict[str, str | None]] = []
        self.favicons: list[str] = []
        self.json_ld: list[str] = []
        self._in_title = False
        self._in_json_ld = False
        self._json_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        element_id = values.get("id")
        if element_id:
            self.ids.append(element_id)
        if tag == "a" and values.get("href"):
            self.links.append(values["href"] or "")
        if tag == "h1":
            self.h1_count += 1
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = (values.get("name") or "").lower()
            prop = (values.get("property") or "").lower()
            if name == "description":
                self.description = values.get("content") or ""
            elif name == "robots":
                self.robots = values.get("content") or ""
            elif prop == "og:url":
                self.og_url = values.get("content") or ""
        elif tag == "link":
            rels = set((values.get("rel") or "").lower().split())
            if "canonical" in rels:
                self.canonical = values.get("href") or ""
            if {"icon", "shortcut", "apple-touch-icon"} & rels and values.get("href"):
                self.favicons.append(values["href"] or "")
        elif tag == "img":
            self.images.append(values)
            if "alt" not in values:
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


def schema_types(item: dict[str, object]) -> set[str]:
    value = item.get("@type")
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {entry for entry in value if isinstance(entry, str)}
    return set()


def find_schema(items: list[dict[str, object]], schema_type: str) -> dict[str, object] | None:
    return next((item for item in items if schema_type in schema_types(item)), None)


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def built_path_for_url(url: str, source_path: str = "/") -> Path | None:
    target = urlparse(urljoin(f"https://{CANONICAL_HOST}{source_path}", url))
    if target.netloc and target.netloc != CANONICAL_HOST:
        return None
    path = unquote(target.path)
    relative = path.lstrip("/")
    if not relative or path.endswith("/"):
        relative += "index.html"
    return SITE / relative


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    titles: dict[str, list[str]] = defaultdict(list)
    descriptions: dict[str, list[str]] = defaultdict(list)
    pages: dict[str, PageParser] = {}
    schemas: dict[str, list[dict[str, object]]] = defaultdict(list)
    indexable_paths: set[str] = set()

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
            indexable_paths.add(relative)
            if not parser.title.strip():
                errors.append(f"Missing title: {relative}")
            else:
                titles[parser.title.strip()].append(relative)
                if len(parser.title.strip()) > 65:
                    warnings.append(f"Long title ({len(parser.title.strip())} chars): {relative}")
            if not parser.description.strip():
                errors.append(f"Missing description: {relative}")
            else:
                descriptions[parser.description.strip()].append(relative)
                if len(parser.description.strip()) > 165:
                    warnings.append(
                        f"Long description ({len(parser.description.strip())} chars): {relative}"
                    )
            if not parser.canonical:
                errors.append(f"Missing canonical: {relative}")
            else:
                parsed = urlparse(parser.canonical)
                if parsed.scheme != "https" or parsed.netloc != CANONICAL_HOST:
                    errors.append(f"Non-canonical host/scheme on {relative}: {parser.canonical}")
                if parsed.query or parsed.fragment:
                    errors.append(f"Canonical contains query or fragment on {relative}")
                if parsed.path != relative:
                    errors.append(
                        f"Self-canonical mismatch on {relative}: {parser.canonical}"
                    )
                if parser.og_url != parser.canonical:
                    errors.append(f"Open Graph URL mismatch on {relative}: {parser.og_url}")
            if parser.h1_count != 1:
                errors.append(f"Expected one H1 on {relative}, found {parser.h1_count}")
            if "max-image-preview:large" not in parser.robots.lower():
                errors.append(f"Missing large image preview permission: {relative}")
        if parser.missing_alt:
            errors.append(f"Images missing alt on {relative}: {parser.missing_alt}")
        for image in parser.images:
            if not image.get("width") or not image.get("height"):
                errors.append(f"Image missing intrinsic dimensions on {relative}: {image.get('src')}")
            if image.get("src"):
                image_file = built_path_for_url(image["src"] or "", relative)
                if image_file is not None and not image_file.exists():
                    errors.append(f"Missing local image on {relative}: {image.get('src')}")
        for payload in parser.json_ld:
            try:
                parsed_payload = json.loads(payload)
                if isinstance(parsed_payload, dict):
                    schemas[relative].append(parsed_payload)
                elif isinstance(parsed_payload, list):
                    schemas[relative].extend(
                        item for item in parsed_payload if isinstance(item, dict)
                    )
            except json.JSONDecodeError as exc:
                errors.append(f"Invalid JSON-LD on {relative}: {exc}")
        for element_id, count in Counter(parser.ids).items():
            if count > 1:
                errors.append(f"Duplicate id {element_id!r} on {relative}: {count} occurrences")

    for title, paths in titles.items():
        if len(paths) > 1:
            errors.append(f"Duplicate title {title!r}: {', '.join(paths)}")
    for description, paths in descriptions.items():
        if len(paths) > 1:
            warnings.append(f"Duplicate description on {', '.join(paths)}")

    for path in sorted(indexable_paths):
        person = find_schema(schemas[path], "Person")
        if person is None or not all(person.get(key) for key in ("name", "url", "sameAs")):
            errors.append(f"Incomplete Person structured data: {path}")

        if path == "/":
            website = find_schema(schemas[path], "WebSite")
            if website is None or not all(
                website.get(key) for key in ("name", "alternateName", "url")
            ):
                errors.append("Incomplete WebSite structured data on home page")
            elif CANONICAL_HOST not in website.get("alternateName", []):
                errors.append("WebSite alternateName has no canonical hostname fallback")

        if path == "/about/":
            profile = find_schema(schemas[path], "ProfilePage")
            entity = profile.get("mainEntity") if profile else None
            if not isinstance(entity, dict) or "Person" not in schema_types(entity) or not all(
                entity.get(key) for key in ("name", "url")
            ):
                errors.append("Incomplete ProfilePage structured data on /about/")

        if path in COLLECTION_PATHS and find_schema(schemas[path], "CollectionPage") is None:
            errors.append(f"Missing CollectionPage structured data: {path}")

        if POST_PATH.match(path):
            article = find_schema(schemas[path], "BlogPosting")
            if article is None:
                errors.append(f"Missing Google-supported BlogPosting structured data: {path}")
            else:
                for key in (
                    "headline",
                    "description",
                    "datePublished",
                    "dateModified",
                    "mainEntityOfPage",
                    "image",
                    "author",
                ):
                    if not article.get(key):
                        errors.append(f"BlogPosting missing {key}: {path}")
                author = article.get("author")
                if not isinstance(author, dict) or "Person" not in schema_types(author) or not all(
                    author.get(key) for key in ("name", "url")
                ):
                    errors.append(f"Incomplete BlogPosting author: {path}")
                try:
                    published = parse_datetime(str(article.get("datePublished", "")))
                    modified = parse_datetime(str(article.get("dateModified", "")))
                    if modified < published:
                        errors.append(f"BlogPosting modified before publication: {path}")
                except ValueError:
                    errors.append(f"Invalid BlogPosting publication date: {path}")
                main_entity = article.get("mainEntityOfPage")
                if not isinstance(main_entity, dict) or main_entity.get("@id") != pages[path].canonical:
                    errors.append(f"BlogPosting mainEntityOfPage mismatch: {path}")

            breadcrumb = find_schema(schemas[path], "BreadcrumbList")
            items = breadcrumb.get("itemListElement") if breadcrumb else None
            if not isinstance(items, list) or not items:
                errors.append(f"Missing breadcrumb items: {path}")
            else:
                positions = [item.get("position") for item in items if isinstance(item, dict)]
                if positions != list(range(1, len(items) + 1)):
                    errors.append(f"Invalid breadcrumb positions: {path}")
                final = items[-1] if isinstance(items[-1], dict) else {}
                if final.get("item") != pages[path].canonical:
                    errors.append(f"Breadcrumb canonical mismatch: {path}")

    sitemap_paths: set[str] = set()
    sitemap = SITE / "sitemap.xml"
    if not sitemap.exists():
        errors.append("Missing sitemap.xml")
    else:
        root = ET.parse(sitemap).getroot()
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        url_nodes = root.findall("sm:url", namespace)
        urls = [(node.findtext("sm:loc", default="", namespaces=namespace)) for node in url_nodes]
        sitemap_paths = {urlparse(url).path for url in urls}
        if len(urls) != len(set(urls)):
            errors.append("Duplicate URLs in sitemap")
        for node, url in zip(url_nodes, urls):
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
            elif "noindex" in page.robots.lower():
                errors.append(f"Noindex URL present in sitemap: {url}")

            lastmod = node.findtext("sm:lastmod", default="", namespaces=namespace)
            if lastmod:
                try:
                    modified = parse_datetime(lastmod)
                    if modified > datetime.now(timezone.utc):
                        errors.append(f"Future lastmod in sitemap: {url}")
                    article = find_schema(schemas.get(parsed.path, []), "BlogPosting")
                    if article and article.get("dateModified"):
                        article_modified = parse_datetime(str(article["dateModified"]))
                        if modified != article_modified:
                            errors.append(f"Sitemap/article dateModified mismatch: {url}")
                except ValueError:
                    errors.append(f"Invalid sitemap lastmod for {url}: {lastmod}")

    for path in sorted(indexable_paths - sitemap_paths):
        errors.append(f"Indexable canonical page missing from sitemap: {path}")

    inbound: dict[str, set[str]] = defaultdict(set)
    for source_path, page in pages.items():
        source_url = f"https://{CANONICAL_HOST}{source_path}"
        for href in page.links:
            target = urlparse(urljoin(source_url, href))
            if target.scheme not in {"http", "https"} or target.netloc != CANONICAL_HOST:
                continue

            target_path = target.path or "/"
            if target.fragment:
                fragment = unquote(target.fragment)
                target_page = pages.get(target_path)
                if target_page is not None and fragment not in target_page.ids:
                    errors.append(
                        f"Missing fragment #{fragment} from {source_path} to {target_path}"
                    )

            if target_path in sitemap_paths and target_path != source_path:
                inbound[target_path].add(source_path)
            target_page = pages.get(target_path)
            if (
                target_page is not None
                and "noindex" in target_page.robots.lower()
                and "noindex" not in page.robots.lower()
            ):
                errors.append(f"Indexable page links to noindex page: {source_path} -> {target_path}")

    for path in sorted(sitemap_paths):
        if path != "/" and not inbound[path]:
            errors.append(f"Sitemap-only orphan page: {path}")

    for forbidden in FORBIDDEN_PATHS:
        if forbidden in pages:
            errors.append(f"Internal/redirect page is still built: {forbidden}")

    home = pages.get("/")
    if home is None or not home.favicons:
        errors.append("Home page has no favicon declaration")
    else:
        for favicon in home.favicons:
            favicon_file = built_path_for_url(favicon)
            if favicon_file is not None and not favicon_file.exists():
                errors.append(f"Missing favicon asset: {favicon}")

    robots_file = SITE / "robots.txt"
    if not robots_file.exists():
        errors.append("Missing robots.txt")
    else:
        robots_text = robots_file.read_text(encoding="utf-8")
        if not re.search(r"(?im)^User-agent:\s*\*$", robots_text):
            errors.append("robots.txt has no default user-agent group")
        if f"Sitemap: {SITEMAP_URL}" not in robots_text:
            errors.append("robots.txt has no canonical sitemap declaration")
        if re.search(r"(?im)^Disallow:\s*/\s*$", robots_text):
            errors.append("robots.txt blocks the entire site")

    manifest_file = SITE / "manifest.json"
    if not manifest_file.exists():
        errors.append("Missing web manifest")
    else:
        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            for icon in manifest.get("icons", []):
                icon_file = built_path_for_url(icon.get("src", ""))
                if icon_file is not None and not icon_file.exists():
                    errors.append(f"Missing manifest icon: {icon.get('src')}")
        except json.JSONDecodeError as exc:
            errors.append(f"Invalid web manifest: {exc}")

    feed_file = SITE / "feed.xml"
    if not feed_file.exists():
        errors.append("Missing Atom feed")
    else:
        try:
            ET.parse(feed_file)
        except ET.ParseError as exc:
            errors.append(f"Invalid Atom feed: {exc}")

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
