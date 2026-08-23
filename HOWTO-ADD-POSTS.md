# Publishing a Soot / Silicon field note

This is the required workflow for creating or materially updating a blog post.
It applies the approved Soothill editorial standard alongside the site's build,
metadata and accessibility checks.

The objective is not to satisfy an AI detector. The article must preserve
Darren Soothill's evidence, reasoning and judgement without inventing facts,
experience, failures or certainty.

## The publication gate

A post is ready only when all four conditions are true:

1. The source record supports every important claim.
2. The article passes the evidence and voice review below.
3. Darren has approved the factual conclusions and final wording.
4. The editorial, site and link validators pass.

Do not publish a draft with `editorial_review_status: pending`. The editorial
validator intentionally rejects it.

## 1. Start with the source record

Before drafting, record:

- the question, assumption or claim being tested;
- why its answer could change a product, operating or technical decision;
- the hardware, software, model, firmware and source revisions involved;
- launch settings, workload, controls, repeats and acceptance conditions;
- raw measurements, logs, retained data and primary sources;
- failures, unexpected results and changes made during the investigation;
- Darren's interpretation and the decision that followed;
- what was not tested and where the conclusion stops.

An external specification, release note, benchmark screenshot or community
answer is an input. It is not Darren's conclusion until the article says what
was independently checked and what could not be checked.

When AI assists with drafting or editing, give it this source record. Instruct
it to flag missing evidence rather than fill gaps. Check every anecdote,
measurement, quotation and first-person statement against the source record.

## 2. Create the post

Copy `_templates/blog-post.md` to `_posts` using this filename convention:

```text
_posts/YYYY-MM-DD-specific-post-slug.md
```

Replace every placeholder. Do not leave the template's headings in place
unless they are genuinely the clearest headings for that investigation.

The post layout supplies the page's H1. Begin article sections with `##` and
use `###` only beneath an existing `##` section.

### Required front matter

```yaml
---
layout: post
title: "State the useful result or question"
seo_title: "Short search title"
date: 2026-08-17 10:00:00 +0100
last_modified_at: 2026-08-17 10:00:00 +0100
categories: [local-ai, benchmarks]
tags: [specific-technology, workload, platform]
author: Darren Soothill
editorial_standard: soothill-human-v1
editorial_review_status: pending
editorial_reviewer: Darren Soothill
editorial_reviewed_at: 2026-08-17
description: "Describe the tested subject, method and useful result in 50 to 165 characters."
---
```

Use a full time and UK offset when the publication time is known. Use an ISO
date without a fabricated time for older material whose time was not recorded.
Change `last_modified_at` only for a meaningful published update, not for an
unpublished drafting edit.

For an ongoing series, also add its name and next reading-order number:

```yaml
series: "Local LLMs on Strix Halo"
series_order: 11
```

Set `editorial_review_status: approved` only after Darren completes the final
review. Record that review's real date in `editorial_reviewed_at`.

## 3. Write around the investigation

The article should answer these questions, but it should not repeat them as a
fixed set of headings:

- What was I trying to find out?
- Why did the answer matter?
- What did I test, observe or change?
- What failed or contradicted the first result?
- What does the result mean for a real decision?
- What does it not prove?
- What would I use, reject, repeat or test next?

Start with the useful question, failure or result. Background belongs after the
reader knows why it matters.

Use the structure the evidence requires: prose for reasoning, a table for a
comparison, code for exact commands, and a figure when it makes a relationship
clearer. Do not force every explanation into three bullets or give every
section the same length.

### The four voice requirements

Question and test claims. Treat vendor and community material as claims until
the relevant part is reproduced or clearly labelled as untested.

Measure before asserting. Name the environment, workload and relevant control.
Keep the evidence boundary close to the result it qualifies.

Be candidly decisive. Say `I kept`, `I rejected`, `I would use` or `I still do
not know` when that is Darren's real decision.

Be technically plain-spoken. Use the correct term, then connect it to the
product or operational consequence.

### Language rules

- Use UK English in authored text, metadata, captions and alternative text.
- Preserve official names, code, command options, URLs, data fields and exact
  quotations even when they contain US spelling.
- Use `I` for Darren's work and judgement.
- Do not use a corporate `we` for this one-person publication.
- Use `you` only for a real instruction, warning or reader decision.
- Use sentence case for headings.
- Use `14 August 2026` in prose and ISO dates in metadata or technical records.
- Preserve the distinction between GB and GiB and record compact technical
  units consistently.
- Prefer full stops and commas. Use an em dash only when the interruption earns
  it.

Avoid marketing defaults such as `seamless`, `game-changing`, `cutting-edge`,
`ever-evolving` and claims about unlocking potential. Do not start with `In
today's fast-paced world` or a `whether you are X or Y` construction.

The approved detailed voice standard is maintained in the editorial project at
`../soothill-editorial/phase-3-provisional-voice-guide.md`.

## 4. Complete the human review

Darren must review the rendered article, not only the Markdown source.

### Evidence review

- The test environment is specific enough to understand the result.
- Measurements and retained data agree with the prose and tables.
- External claims are distinct from direct observations and interpretation.
- Failures, reversals and negative results have not been smoothed away.
- The article states where the evidence stops.
- The conclusion changes or informs a real decision.

### Voice review

- The opening says something useful immediately.
- A competitor could not publish the article unchanged.
- First-person statements belong to Darren and come from the source record.
- Paragraphs and sections do not repeat one uniform rhythm.
- Technical terms are either necessary or explained.
- Generic scene-setting, marketing language and repeated summaries are gone.
- The article sounds natural when Darren reads it aloud.

### Publication review

- Title, description, categories, tags and series metadata are correct.
- Publication and update dates are accurate.
- Source links, data downloads and internal links work.
- Informative images have accurate alternative text, captions where needed and
  intrinsic dimensions.
- The article works at desktop and mobile widths.

Use `.github/PULL_REQUEST_TEMPLATE/blog-post.md` to record this review in the
pull request. When opening the pull request manually, select it with:

```text
?template=blog-post.md
```

## 5. Validate locally

From the repository root, run:

```bash
python3 scripts/validate_editorial.py
bundle exec jekyll build --trace
python3 scripts/validate_site.py _site
python3 scripts/check_external_links.py _site
```

The editorial validator fails for:

- missing or unapproved editorial metadata;
- invalid publication, update or review dates;
- US spellings in authored prose covered by its high-confidence dictionary;
- a small set of formulaic marketing constructions;
- no visible signal of testing or measurement;
- no visible evidence boundary;
- no decision, recommendation or operational consequence;
- accidental body H1s, malformed code fences or a very short field note.

It ignores fenced code, inline code and link destinations when checking
spelling and formulaic wording. It may warn about a generic heading or the
absence of an external source; Darren decides whether the context justifies
that warning.

The validator is a guardrail, not an editor. Passing it does not replace the
source check, read-aloud review or Darren's approval.

## 6. Publish through review

Create a branch and a pull request. Do not publish a new article by committing
directly to `main`.

Before merge:

1. Complete the blog-post pull-request checklist.
2. Change `editorial_review_status` from `pending` to `approved` after Darren's
   review.
3. Confirm the Site quality workflow passes.
4. Perform the desktop and mobile browser review.
5. Obtain Darren's final approval.

After merge, confirm the production article, canonical URL, publication and
update dates, social metadata, source links and series/archive placement.

## Updating an existing article

Use the same source, voice and validation process for a material update.

- Preserve the original `date`.
- Set `last_modified_at` to the real update date and time.
- Update `editorial_reviewed_at` when Darren reviews the revised article.
- Explain changed findings in the body when the old conclusion materially
  changed.
- Do not erase a superseded result if it is needed to understand the reversal.
- Recheck links, structured metadata and the sitemap after building.

Typographical corrections that do not change meaning do not require a new
public update time, but the resulting article must still pass the validators.
