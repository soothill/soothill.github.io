#!/usr/bin/env python3
"""Collect read-only GA4 and Search Console data for soothill.io.

The script uses Google Application Default Credentials created with:

    gcloud auth application-default login

No access token or OAuth client secret is written to the report files.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


DEFAULT_PROPERTY_ID = "507414105"
DEFAULT_SEARCH_CONSOLE_SITE = "sc-domain:soothill.io"
DEFAULT_QUOTA_PROJECT = "storageperf"
DEFAULT_DAYS = 90


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect GA4 and Search Console data for soothill.io."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        help=f"Number of days to collect (default: {DEFAULT_DAYS}).",
    )
    parser.add_argument(
        "--end-date",
        type=date.fromisoformat,
        default=date.today() - timedelta(days=1),
        help="Last date to collect in YYYY-MM-DD form (default: yesterday).",
    )
    parser.add_argument(
        "--property-id",
        default=DEFAULT_PROPERTY_ID,
        help=f"GA4 property ID (default: {DEFAULT_PROPERTY_ID}).",
    )
    parser.add_argument(
        "--search-console-site",
        default=DEFAULT_SEARCH_CONSOLE_SITE,
        help=f"Search Console property (default: {DEFAULT_SEARCH_CONSOLE_SITE}).",
    )
    parser.add_argument(
        "--quota-project",
        default=DEFAULT_QUOTA_PROJECT,
        help=f"Google Cloud quota project (default: {DEFAULT_QUOTA_PROJECT}).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/analytics"),
        help="Directory for the JSON data and Markdown report.",
    )
    args = parser.parse_args()
    if args.days < 1:
        parser.error("--days must be at least 1")
    return args


def get_access_token() -> str:
    try:
        result = subprocess.run(
            ["gcloud", "auth", "application-default", "print-access-token"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("gcloud is not installed or is not on PATH") from exc
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or "unable to refresh the Google credential"
        raise RuntimeError(message) from exc

    token = result.stdout.strip()
    if not token:
        raise RuntimeError("Google returned an empty access token")
    return token


def google_request(
    url: str,
    token: str,
    quota_project: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    for attempt in range(4):
        request = Request(
            url,
            data=data,
            method="GET" if payload is None else "POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-Goog-User-Project": quota_project,
            },
        )
        try:
            with urlopen(request, timeout=60) as response:
                return json.load(response)
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code in {429, 500, 502, 503, 504} and attempt < 3:
                time.sleep(2**attempt)
                continue
            try:
                detail = json.loads(body).get("error", {}).get("message", body)
            except json.JSONDecodeError:
                detail = body
            raise RuntimeError(
                f"Google API returned HTTP {exc.code}: {detail}"
            ) from exc
        except (URLError, TimeoutError, ConnectionResetError) as exc:
            if attempt < 3:
                time.sleep(2**attempt)
                continue
            reason = getattr(exc, "reason", exc)
            raise RuntimeError(f"Could not reach the Google API: {reason}") from exc

    raise RuntimeError("Google API request failed after four attempts")


def number(value: str | None) -> int | float:
    if not value:
        return 0
    try:
        parsed = float(value)
    except ValueError:
        return 0
    return int(parsed) if parsed.is_integer() else parsed


def parse_ga4_rows(response: dict[str, Any]) -> list[dict[str, Any]]:
    dimensions = [item["name"] for item in response.get("dimensionHeaders", [])]
    metrics = [item["name"] for item in response.get("metricHeaders", [])]
    parsed: list[dict[str, Any]] = []

    for row in response.get("rows", []):
        item: dict[str, Any] = {}
        dimension_values = row.get("dimensionValues", [])
        metric_values = row.get("metricValues", [])
        for index, name in enumerate(dimensions):
            item[name] = dimension_values[index].get("value", "")
        for index, name in enumerate(metrics):
            item[name] = number(metric_values[index].get("value"))
        parsed.append(item)
    return parsed


def ga4_report(
    token: str,
    quota_project: str,
    property_id: str,
    start_date: date,
    end_date: date,
    dimensions: list[str],
    metrics: list[str],
    *,
    limit: int = 10_000,
    order_metric: str | None = None,
) -> list[dict[str, Any]]:
    payload: dict[str, Any] = {
        "dateRanges": [
            {"startDate": start_date.isoformat(), "endDate": end_date.isoformat()}
        ],
        "dimensions": [{"name": item} for item in dimensions],
        "metrics": [{"name": item} for item in metrics],
        "limit": str(limit),
        "keepEmptyRows": False,
    }
    if order_metric:
        payload["orderBys"] = [
            {"metric": {"metricName": order_metric}, "desc": True}
        ]

    response = google_request(
        f"https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport",
        token,
        quota_project,
        payload,
    )
    return parse_ga4_rows(response)


def parse_search_console_rows(
    response: dict[str, Any], dimensions: list[str]
) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    for row in response.get("rows", []):
        item: dict[str, Any] = {}
        keys = row.get("keys", [])
        for index, dimension in enumerate(dimensions):
            item[dimension] = keys[index] if index < len(keys) else ""
        for metric in ("clicks", "impressions", "ctr", "position"):
            item[metric] = number(str(row.get(metric, 0)))
        parsed.append(item)
    return parsed


def search_console_report(
    token: str,
    quota_project: str,
    site: str,
    start_date: date,
    end_date: date,
    dimensions: list[str],
    *,
    row_limit: int = 25_000,
) -> list[dict[str, Any]]:
    payload = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "dimensions": dimensions,
        "rowLimit": row_limit,
        "dataState": "final",
        "type": "web",
    }
    encoded_site = quote(site, safe="")
    response = google_request(
        f"https://www.googleapis.com/webmasters/v3/sites/{encoded_site}/searchAnalytics/query",
        token,
        quota_project,
        payload,
    )
    return parse_search_console_rows(response, dimensions)


def collect(args: argparse.Namespace) -> dict[str, Any]:
    start_date = args.end_date - timedelta(days=args.days - 1)
    token = get_access_token()

    ga4_summary = ga4_report(
        token,
        args.quota_project,
        args.property_id,
        start_date,
        args.end_date,
        [],
        [
            "activeUsers",
            "newUsers",
            "sessions",
            "engagedSessions",
            "engagementRate",
            "screenPageViews",
            "userEngagementDuration",
            "averageSessionDuration",
        ],
    )
    ga4_daily = ga4_report(
        token,
        args.quota_project,
        args.property_id,
        start_date,
        args.end_date,
        ["date"],
        ["activeUsers", "sessions", "screenPageViews", "engagedSessions"],
    )
    for row in ga4_daily:
        raw_date = str(row.get("date", ""))
        if len(raw_date) == 8:
            row["date"] = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
    ga4_daily.sort(key=lambda row: str(row.get("date", "")))

    ga4_top_pages = ga4_report(
        token,
        args.quota_project,
        args.property_id,
        start_date,
        args.end_date,
        ["pagePath"],
        ["screenPageViews", "activeUsers", "userEngagementDuration"],
        limit=50,
        order_metric="screenPageViews",
    )
    ga4_landing_pages = ga4_report(
        token,
        args.quota_project,
        args.property_id,
        start_date,
        args.end_date,
        ["landingPagePlusQueryString"],
        ["sessions", "engagedSessions", "activeUsers"],
        limit=50,
        order_metric="sessions",
    )
    ga4_acquisition = ga4_report(
        token,
        args.quota_project,
        args.property_id,
        start_date,
        args.end_date,
        ["sessionDefaultChannelGroup", "sessionSourceMedium"],
        ["sessions", "engagedSessions", "activeUsers"],
        limit=50,
        order_metric="sessions",
    )
    ga4_devices = ga4_report(
        token,
        args.quota_project,
        args.property_id,
        start_date,
        args.end_date,
        ["deviceCategory"],
        ["activeUsers", "sessions", "screenPageViews"],
        order_metric="activeUsers",
    )
    ga4_countries = ga4_report(
        token,
        args.quota_project,
        args.property_id,
        start_date,
        args.end_date,
        ["country"],
        ["activeUsers", "sessions"],
        limit=50,
        order_metric="activeUsers",
    )

    search_summary = search_console_report(
        token,
        args.quota_project,
        args.search_console_site,
        start_date,
        args.end_date,
        [],
        row_limit=1,
    )
    search_daily = search_console_report(
        token,
        args.quota_project,
        args.search_console_site,
        start_date,
        args.end_date,
        ["date"],
    )
    search_daily.sort(key=lambda row: str(row.get("date", "")))
    search_top_pages = search_console_report(
        token,
        args.quota_project,
        args.search_console_site,
        start_date,
        args.end_date,
        ["page"],
        row_limit=1_000,
    )
    search_top_queries = search_console_report(
        token,
        args.quota_project,
        args.search_console_site,
        start_date,
        args.end_date,
        ["query"],
        row_limit=1_000,
    )

    return {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": args.end_date.isoformat(),
            "days": args.days,
        },
        "configuration": {
            "ga4_property_id": args.property_id,
            "search_console_site": args.search_console_site,
            "quota_project": args.quota_project,
        },
        "google_analytics": {
            "summary": ga4_summary[0] if ga4_summary else {},
            "daily": ga4_daily,
            "top_pages": ga4_top_pages,
            "landing_pages": ga4_landing_pages,
            "acquisition": ga4_acquisition,
            "devices": ga4_devices,
            "countries": ga4_countries,
        },
        "search_console": {
            "summary": search_summary[0] if search_summary else {},
            "daily": search_daily,
            "top_pages": search_top_pages,
            "top_queries": search_top_queries,
        },
    }


def markdown_escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def integer(value: Any) -> str:
    return f"{int(float(value or 0)):,}"


def decimal(value: Any, places: int = 2) -> str:
    return f"{float(value or 0):,.{places}f}"


def percentage(value: Any) -> str:
    return f"{float(value or 0) * 100:.1f}%"


def duration(value: Any) -> str:
    total_seconds = int(round(float(value or 0)))
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:d}:{seconds:02d}"


def table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    if not rows:
        return ["_No data returned for this period._"]
    output = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    output.extend(
        "| " + " | ".join(markdown_escape(value) for value in row) + " |"
        for row in rows
    )
    return output


def render_markdown(data: dict[str, Any]) -> str:
    period = data["period"]
    ga4 = data["google_analytics"]
    search = data["search_console"]
    ga4_summary = ga4["summary"]
    search_summary = search["summary"]

    lines = [
        "# soothill.io analytics report",
        "",
        f"Collected: {data['collected_at']}",
        f"Period: {period['start_date']} to {period['end_date']} ({period['days']} days)",
        "",
        "> This is a local working report. It is excluded from Git and must not be published without review.",
        "",
        "## Google Analytics overview",
        "",
    ]
    lines.extend(
        table(
            ["Metric", "Value"],
            [
                ["Active users", integer(ga4_summary.get("activeUsers"))],
                ["New users", integer(ga4_summary.get("newUsers"))],
                ["Sessions", integer(ga4_summary.get("sessions"))],
                ["Engaged sessions", integer(ga4_summary.get("engagedSessions"))],
                ["Engagement rate", percentage(ga4_summary.get("engagementRate"))],
                ["Page views", integer(ga4_summary.get("screenPageViews"))],
                [
                    "Average session duration",
                    duration(ga4_summary.get("averageSessionDuration")),
                ],
                [
                    "Total engagement time",
                    duration(ga4_summary.get("userEngagementDuration")),
                ],
            ],
        )
    )

    lines.extend(["", "## Most-viewed pages", ""])
    lines.extend(
        table(
            ["Page", "Views", "Users", "Engagement time"],
            [
                [
                    row.get("pagePath", ""),
                    integer(row.get("screenPageViews")),
                    integer(row.get("activeUsers")),
                    duration(row.get("userEngagementDuration")),
                ]
                for row in ga4["top_pages"][:20]
            ],
        )
    )

    lines.extend(["", "## Landing pages", ""])
    lines.extend(
        table(
            ["Landing page", "Sessions", "Engaged sessions", "Users"],
            [
                [
                    row.get("landingPagePlusQueryString", ""),
                    integer(row.get("sessions")),
                    integer(row.get("engagedSessions")),
                    integer(row.get("activeUsers")),
                ]
                for row in ga4["landing_pages"][:20]
            ],
        )
    )

    lines.extend(["", "## Acquisition", ""])
    lines.extend(
        table(
            ["Channel", "Source / medium", "Sessions", "Engaged sessions", "Users"],
            [
                [
                    row.get("sessionDefaultChannelGroup", ""),
                    row.get("sessionSourceMedium", ""),
                    integer(row.get("sessions")),
                    integer(row.get("engagedSessions")),
                    integer(row.get("activeUsers")),
                ]
                for row in ga4["acquisition"][:20]
            ],
        )
    )

    lines.extend(["", "## Search Console overview", ""])
    lines.extend(
        table(
            ["Metric", "Value"],
            [
                ["Clicks", integer(search_summary.get("clicks"))],
                ["Impressions", integer(search_summary.get("impressions"))],
                ["Click-through rate", percentage(search_summary.get("ctr"))],
                ["Average position", decimal(search_summary.get("position"))],
            ],
        )
    )

    lines.extend(["", "## Search pages", ""])
    lines.extend(
        table(
            ["Page", "Clicks", "Impressions", "CTR", "Position"],
            [
                [
                    row.get("page", ""),
                    integer(row.get("clicks")),
                    integer(row.get("impressions")),
                    percentage(row.get("ctr")),
                    decimal(row.get("position")),
                ]
                for row in search["top_pages"][:20]
            ],
        )
    )

    lines.extend(["", "## Search queries", ""])
    lines.extend(
        table(
            ["Query", "Clicks", "Impressions", "CTR", "Position"],
            [
                [
                    row.get("query", ""),
                    integer(row.get("clicks")),
                    integer(row.get("impressions")),
                    percentage(row.get("ctr")),
                    decimal(row.get("position")),
                ]
                for row in search["top_queries"][:20]
            ],
        )
    )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Search Console data normally trails the current date by several days.",
            "- GA4 and Search Console measure different things, so their totals should not be expected to match.",
            "- Search Console protects some low-volume queries, so visible query clicks may not add up to the overview total.",
            "- The accompanying JSON file contains the full collected rows, including daily, device and country breakdowns.",
            "",
        ]
    )
    return "\n".join(lines)


def update_history(data: dict[str, Any], history_path: Path) -> None:
    ga4 = data["google_analytics"]["summary"]
    search = data["search_console"]["summary"]
    row = {
        "snapshot_date": data["period"]["end_date"],
        "period_start": data["period"]["start_date"],
        "period_end": data["period"]["end_date"],
        "period_days": data["period"]["days"],
        "active_users": ga4.get("activeUsers", 0),
        "new_users": ga4.get("newUsers", 0),
        "sessions": ga4.get("sessions", 0),
        "engaged_sessions": ga4.get("engagedSessions", 0),
        "engagement_rate": ga4.get("engagementRate", 0),
        "page_views": ga4.get("screenPageViews", 0),
        "average_session_duration": ga4.get("averageSessionDuration", 0),
        "search_clicks": search.get("clicks", 0),
        "search_impressions": search.get("impressions", 0),
        "search_ctr": search.get("ctr", 0),
        "search_position": search.get("position", 0),
    }
    fieldnames = list(row)
    rows_by_date: dict[str, dict[str, Any]] = {}
    if history_path.exists():
        with history_path.open(newline="", encoding="utf-8") as source:
            for existing in csv.DictReader(source):
                if existing.get("snapshot_date"):
                    rows_by_date[existing["snapshot_date"]] = existing
    rows_by_date[str(row["snapshot_date"])] = row

    with history_path.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_by_date[key] for key in sorted(rows_by_date))


def write_reports(data: dict[str, Any], output_dir: Path) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().date().isoformat()
    json_path = output_dir / f"soothill-analytics-{stamp}.json"
    markdown_path = output_dir / f"soothill-analytics-{stamp}.md"
    history_path = output_dir / "soothill-analytics-history.csv"
    json_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(data), encoding="utf-8")
    update_history(data, history_path)
    return json_path, markdown_path, history_path


def main() -> int:
    args = parse_args()
    try:
        data = collect(args)
        json_path, markdown_path, history_path = write_reports(data, args.output_dir)
    except RuntimeError as exc:
        print(f"Analytics collection failed: {exc}", file=sys.stderr)
        return 1

    print(f"JSON data: {json_path}")
    print(f"Markdown report: {markdown_path}")
    print(f"History data: {history_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
