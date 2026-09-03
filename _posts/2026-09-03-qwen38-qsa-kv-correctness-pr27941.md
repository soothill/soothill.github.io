---
layout: post
title: "The Qwen3.8 correctness merge I would carry before chasing speed"
seo_title: "llama.cpp PR 27941 Qwen3.8 correctness fixes"
date: 2026-09-03 17:00:00 +0100
last_modified_at: 2026-09-03 17:00:00 +0100
permalink: /blog/2026/09/03/qwen38-qsa-kv-correctness-pr27941/
categories: [local-ai, engineering, upstream]
tags: [qwen3.8, qwen4exp, llama-cpp, qsa, kv-cache, prompt-caching, strix-halo]
author: Darren Soothill
editorial_standard: soothill-human-v1
editorial_review_status: approved
editorial_reviewer: Darren Soothill
editorial_reviewed_at: 2026-09-03
series: "Local LLMs on Strix Halo"
series_order: 21
description: "PR 27941 fixes five Qwen3.8 state and QSA correctness faults. I would carry it into the next EVO-X3 canary, but not promote it untested."
---

> **Source record:** llama.cpp [PR 27941](https://github.com/ggml-org/llama.cpp/pull/27941)
> merged on 1 September 2026 as commit
> [`36b10154`](https://github.com/ggml-org/llama.cpp/commit/36b10154383b60eb15baac2c7a40d2a5f784faa7).
> It changes sequence-copy state, unified-KV indexing, M-RoPE image grouping,
> malformed-metadata handling and a long-context CUDA launch limit. I have not
> yet built this merge into the qualified EVO-X3 Vulkan runtime.

This is the sort of upstream change I want before another round of performance
tuning. PR 27941 does not promise a faster headline benchmark. It removes five
ways in which Qwen3.8 Flash Next could select or preserve the wrong state.

That matters more than a small tokens-per-second gain. A plausible answer from
the wrong sequence is much harder to catch than a crash.

## What actually merged

The first two fixes concern identity. A copied sequence could retain stale
indexer keys because the update path did not build the destination index
context. Separately, pooled QSA blocks were keyed by position rather than by
both sequence set and index bucket. The latter assumption works for one
sequence; it is unsafe once a unified KV cache contains more than one.

The image case is different but has the same flavour. M-RoPE can give every
token in an image the same position. Grouping by position therefore collapsed
the image into one block slot, leaving almost all of its cells scored against a
pooled key to which they did not belong. The patch cuts blocks by rank order
instead.

Two defensive changes complete the merge. Malformed Qwen4Exp metadata now
throws an error at sites that previously asserted or silently accepted an
invalid value. The pooled-block CUDA launch is also split before it reaches the
65,535 `gridDim.y` limit at a 262,144-token KV depth.

The author reports exact perplexity before and after on UD-IQ1_S, so the fix
does not require replacement GGUF files. That is upstream evidence, not an
EVO-X3 result.

## Why it fits the next Strix Halo canary

The production service runs two 262K slots and relies on recurrent state and
prompt caching. Its current Nathan Vulkan 0.7.1 binary predates this merge.
Those similarities make the sequence and pooled-key fixes relevant, but they
do not prove that the live route has triggered any of the bugs.

I would carry commit `36b10154` into the next base update and repeat the gates
that have already caught real failures here:

- distinct simultaneous prompts, with markers checked for cross-slot leakage;
- ABCCBA state restoration and twenty prompt-cache cycles;
- system, tool and multi-message segmentation;
- the issue-26744 stale-KV reproducer with Flash Attention on and off;
- long-context retrieval and clean unload/reload.

The malformed-GGUF changes belong in a separate negative test. A clean model
load cannot demonstrate that invalid metadata fails safely.

## Where I would stop claiming

This merge is not evidence of a performance improvement, and it has not been
tested on my Radeon 8060S path. It also does not close the separate stale-KV,
prompt-checkpoint or draft-MTP concurrency reports.

My decision is narrower: PR 27941 is now a correctness prerequisite for a
future Qwen3.8 runtime, not a reason to replace the qualified production binary
on its own. I would rather spend the next canary budget proving these state
transitions than benchmark a newer build that still lacks them.

*Upstream state checked 3 September 2026. Local production remained on the
qualified Qwen3.8 Flash Next Vulkan 0.7.1 route; no model, binary or Lemonade
setting was changed for this source review.*
