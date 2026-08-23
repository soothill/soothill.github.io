#!/usr/bin/env python3
"""Validate the Soothill editorial standard for every published blog post.

This is deliberately a guardrail rather than an AI-writing detector. It checks
facts the repository can prove, rejects a small number of formulaic patterns
and requires evidence, limitation and decision signals. Darren's final read is
still the authority on whether an article sounds like him.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path


EXPECTED_STANDARD = "soothill-human-v1"
EXPECTED_AUTHOR = "Darren Soothill"
REQUIRED_FIELDS = (
    "layout",
    "title",
    "date",
    "last_modified_at",
    "categories",
    "tags",
    "author",
    "description",
    "editorial_standard",
    "editorial_review_status",
    "editorial_reviewer",
    "editorial_reviewed_at",
)

# These are narrow, high-confidence signals. Broader language judgements belong
# in the human review because technical prose contains product names, quotations
# and upstream terminology that should not be silently rewritten.
US_SPELLINGS = {
    "analyze": "analyse",
    "analyzed": "analysed",
    "analyzing": "analysing",
    "authorization": "authorisation",
    "authorize": "authorise",
    "authorized": "authorised",
    "behavior": "behaviour",
    "behaviors": "behaviours",
    "catalog": "catalogue",
    "center": "centre",
    "centers": "centres",
    "color": "colour",
    "colors": "colours",
    "customize": "customise",
    "customized": "customised",
    "customizing": "customising",
    "favor": "favour",
    "favorite": "favourite",
    "modeling": "modelling",
    "optimization": "optimisation",
    "optimized": "optimised",
    "optimizing": "optimising",
    "organize": "organise",
    "organized": "organised",
    "organizing": "organising",
    "recognize": "recognise",
    "recognized": "recognised",
    "recognizing": "recognising",
    "utilization": "utilisation",
}

BLOCKED_PATTERNS = {
    r"\bin today['’]s fast[- ]paced world\b": "generic scene-setting",
    r"\bgame[- ]changing\b": "unsupported marketing language",
    r"\bcutting[- ]edge\b": "unsupported marketing language",
    r"\bever[- ]evolving\b": "generic marketing language",
    r"\bseamless(?:ly)?\b": "generic marketing language",
    r"\bunlock(?:ing|ed|s)? (?:the )?(?:power|potential|possibilities)\b": (
        "generic marketing language"
    ),
    r"\bwhether you (?:are|re)\b": "formulaic audience construction",
}

EVIDENCE_SIGNAL = re.compile(
    r"\b(test(?:ed|ing|s)?|measur(?:e|ed|ement|ements|ing)|observ(?:e|ed|ation|ations)|"
    r"record(?:ed|ing|s)?|compar(?:e|ed|ison|isons|ing)|verif(?:y|ied|ication)|"
    r"benchmark(?:ed|ing|s)?|result(?:s)?|failure(?:s)?|failed)\b",
    re.IGNORECASE,
)
LIMIT_SIGNAL = re.compile(
    r"\b(does not prove|did not prove|cannot rule out|not tested|untested|not measured|"
    r"not evidence|limit(?:s|ation|ations)?|caveat(?:s)?|boundary|under (?:the )?test(?:ed)? "
    r"(?:settings|conditions)|in this (?:run|test)|on this machine|rather than (?:a|an) "
    r"(?:general|universal|eternal)|outside (?:the|its) (?:scope|official)|remains? unknown|"
    r"still needs? (?:work|testing)|depends on (?:the )?workload)\b",
    re.IGNORECASE,
)
DECISION_SIGNAL = re.compile(
    r"\b(I (?:kept|rejected|changed|would use|would run|would keep|would leave|would not "
    r"approve|still do not know)|current (?:choice|default|policy)|starting choice|"
    r"recommend(?:ation|ed)?|should|must|"
    r"decision|trade-off|consequence|operat(?:e|ed|ing)|deploy(?:ed|ment)|next (?:test|step))\b",
    re.IGNORECASE,
)


def scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def split_post(path: Path) -> tuple[dict[str, str], str, int]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing opening YAML front-matter delimiter")

    try:
        closing = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration as exc:
        raise ValueError("missing closing YAML front-matter delimiter") from exc

    fields: dict[str, str] = {}
    for line in lines[1:closing]:
        if line.startswith((" ", "\t")) or not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if match:
            fields[match.group(1)] = scalar(match.group(2))

    return fields, "\n".join(lines[closing + 1 :]), closing + 2


def prose_only(body: str) -> str:
    """Remove material that should not be Anglicised or style-scanned."""

    preserve_lines = lambda match: "\n" * match.group(0).count("\n")
    prose = re.sub(r"```.*?```", preserve_lines, body, flags=re.DOTALL)
    prose = re.sub(r"~~~.*?~~~", preserve_lines, prose, flags=re.DOTALL)
    prose = re.sub(r"`[^`\n]+`", " ", prose)
    prose = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", prose)
    prose = re.sub(r"https?://\S+", " ", prose)
    prose = re.sub(r"<!--.*?-->", " ", prose, flags=re.DOTALL)
    return prose


def parse_date(value: str) -> date:
    cleaned = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(cleaned).date()
    except ValueError:
        return date.fromisoformat(cleaned)


def line_number(text: str, offset: int, body_start: int) -> int:
    return body_start + text.count("\n", 0, offset)


def validate_post(path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        fields, body, body_start = split_post(path)
    except ValueError as exc:
        return [str(exc)], warnings

    for field in REQUIRED_FIELDS:
        if not fields.get(field):
            errors.append(f"missing required front-matter field: {field}")

    if fields.get("layout") and fields["layout"] != "post":
        errors.append("layout must be 'post'")
    if fields.get("author") and fields["author"] != EXPECTED_AUTHOR:
        errors.append(f"author must be {EXPECTED_AUTHOR!r}")
    if fields.get("editorial_standard") and fields["editorial_standard"] != EXPECTED_STANDARD:
        errors.append(f"editorial_standard must be {EXPECTED_STANDARD!r}")
    if fields.get("editorial_review_status") and fields["editorial_review_status"] != "approved":
        errors.append("editorial_review_status must be 'approved' before publication")
    if fields.get("editorial_reviewer") and fields["editorial_reviewer"] != EXPECTED_AUTHOR:
        errors.append(f"editorial_reviewer must be {EXPECTED_AUTHOR!r}")

    description = fields.get("description", "")
    if description and not 50 <= len(description) <= 165:
        errors.append(f"description must contain 50-165 characters (found {len(description)})")

    try:
        published = parse_date(fields.get("date", ""))
        modified = parse_date(fields.get("last_modified_at", ""))
        reviewed = parse_date(fields.get("editorial_reviewed_at", ""))
        if modified < published:
            errors.append("last_modified_at is earlier than date")
        if reviewed > date.today():
            errors.append("editorial_reviewed_at is in the future")
    except ValueError:
        if all(fields.get(key) for key in ("date", "last_modified_at", "editorial_reviewed_at")):
            errors.append("date, last_modified_at or editorial_reviewed_at is invalid")

    prose = prose_only(body)
    if re.search(r"(?m)^#\s+", prose):
        errors.append("article body must not contain an H1; the post layout supplies it")
    if body.count("```") % 2:
        errors.append("unbalanced triple-backtick code fence")
    if len(re.findall(r"\b[\w’'-]+\b", body)) < 250:
        errors.append("article body is too short for a field note (fewer than 250 words)")

    for word, replacement in US_SPELLINGS.items():
        for match in re.finditer(rf"\b{re.escape(word)}\b", prose, re.IGNORECASE):
            errors.append(
                f"line {line_number(prose, match.start(), body_start)}: use UK English "
                f"{replacement!r} instead of {match.group(0)!r}"
            )

    for pattern, reason in BLOCKED_PATTERNS.items():
        for match in re.finditer(pattern, prose, re.IGNORECASE):
            errors.append(
                f"line {line_number(prose, match.start(), body_start)}: {reason}: "
                f"{match.group(0)!r}"
            )

    if not EVIDENCE_SIGNAL.search(prose):
        errors.append("no testing, measurement, observation or failure signal found")
    if not LIMIT_SIGNAL.search(prose):
        errors.append("no clear evidence boundary or limitation signal found")
    if not DECISION_SIGNAL.search(prose):
        errors.append("no decision, recommendation or operational consequence signal found")
    if not re.search(r"\[[^\]]+\]\(https?://", body):
        warnings.append("no external source link found; confirm that the article is fully self-sourced")
    if re.search(r"(?im)^##\s+(Introduction|Overview|Conclusion|Summary)\s*$", body):
        warnings.append("generic section heading found; confirm that a more descriptive heading would not help")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("posts", nargs="?", type=Path, default=Path("_posts"))
    args = parser.parse_args()

    paths = sorted(args.posts.glob("*.md")) if args.posts.is_dir() else [args.posts]
    if not paths:
        print(f"No Markdown posts found at {args.posts}", file=sys.stderr)
        return 2

    error_count = 0
    warning_count = 0
    for path in paths:
        errors, warnings = validate_post(path)
        for message in errors:
            print(f"ERROR {path}: {message}")
        for message in warnings:
            print(f"WARNING {path}: {message}")
        error_count += len(errors)
        warning_count += len(warnings)

    if error_count:
        print(
            f"Editorial validation failed: {error_count} error(s), "
            f"{warning_count} warning(s) across {len(paths)} post(s).",
            file=sys.stderr,
        )
        return 1

    print(
        f"Editorial validation passed for {len(paths)} post(s) "
        f"with {warning_count} warning(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
