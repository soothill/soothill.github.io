---
layout: post
title: "A one-line Vulkan fix may unlock Q8 K/V prefill, but 125B still needs proving"
seo_title: "llama.cpp PR 28190 Vulkan Q8 KV prefill fix"
date: 2026-09-03 17:00:00 +0100
last_modified_at: 2026-09-03 17:00:00 +0100
permalink: /blog/2026/09/03/llamacpp-vulkan-q8-kv-fa-dequant-pr28190/
categories: [local-ai, performance, upstream]
tags: [qwen3.8, qwen4exp, llama-cpp, vulkan, q8-kv, flash-attention, strix-halo]
author: Darren Soothill
editorial_standard: soothill-human-v1
editorial_review_status: approved
editorial_reviewer: Darren Soothill
editorial_reviewed_at: 2026-09-03
series: "Local LLMs on Strix Halo"
series_order: 27
description: "Merged PR 28190 makes Vulkan's Flash Attention dequant path engage before the KV cache is full. It is promising, not yet a 125B result."
---

> **Merge record:** llama.cpp [PR 28190](https://github.com/ggml-org/llama.cpp/pull/28190)
> merged on 3 September 2026 as
> [`c7bda030`](https://github.com/ggml-org/llama.cpp/commit/c7bda030e7faee594dbe7550185e857351ad405d).
> It changes one Vulkan layout condition so the Flash Attention Q8 K/V dequant
> path can engage before the cache is completely full. The PR reports 29%
> faster prefill on a 30B MoE model. I have not tested it on EVO-X3's 125B
> service.

The most interesting performance fixes are sometimes the ones that reveal an
optimised path was never running. PR 28190 does exactly that for quantised K/V
Flash Attention on Vulkan.

The dequant shader already existed. A layout guard rejected normal cache views
until `n_kv` happened to equal the full configured cache size. `llama-bench`
could therefore exercise the fast path with a full artificial cache while a
real server filling that cache gradually stayed on the slower route.

## What the one line changes

The original guard required the fourth-dimension stride to match a tightly
packed view. A normal single-stream cache view keeps the stride of the complete
backing buffer, even when only part of it contains tokens. The new condition
accepts that view when its fourth dimension contains one stream, while
retaining the old stride check for multi-stream layouts.

That narrow condition matters. The shader is a copy/dequant operation with no
internal layout validation. Relaxing the test too far could turn a performance
fix into garbled output. The final patch is one addition and one deletion,
reviewed and merged rather than an experimental environment switch.

## Two upstream measurements, two different scopes

The originating [issue 28135](https://github.com/ggml-org/llama.cpp/issues/28135)
measured Qwen3.8 27B on an RX 9070 with a 21.5K prompt:

| State | Reported prefill | Decode | Retrieval |
| --- | ---: | --- | --- |
| Fast path missed | 65 tokens/s | unchanged | exact |
| Candidate guard | **119 tokens/s** | unchanged | exact |

That is an 83% prefill increase. The pull request itself reports a more modest
29% server-prefill improvement on a 30B MoE model with Q8_0 K/V and byte-
identical output.

Neither number belongs to Qwen3.8 Flash Next 125B on Radeon 8060S. Different
models, GPUs, prompt depths and surrounding commits make that extrapolation
unsafe. What transfers is the mechanism: the live EVO-X3 route uses Vulkan,
Flash Attention and Q8_0 K/V, so the corrected path is directly relevant.

## The canary I would run

I would backport only merge `c7bda030` onto the qualified Nathan 0.7.1 base,
then use an A/B sequence that proves the shader actually engages:

- fixed 4K, 32K, 64K and 128K uncached prefills;
- one and two occupied slots;
- Q8_0 K/V in both arms, with identical context and batch sizes;
- deterministic output hashes and long-context retrieval;
- cache reuse, ABCCBA restoration and twenty cache cycles;
- GTT, available memory, page faults and clean unload/reload.

The two-slot row is essential. The patch deliberately distinguishes a single-
stream view from other layouts, while the production server has two slots.
Only local trace or performance evidence can show when the optimised path is
taken in that shape.

## Where I would stop claiming

This merge is the strongest new performance lead in the current Qwen3.8
upstream set. It is not yet a material EVO-X3 improvement because no 125B
measurement exists and the production binary does not contain it.

I would prioritise the narrow canary, but I would not combine it immediately
with MTP, QSA gather or a broad mainline update. One line is easy to attribute;
four simultaneous changes are not.

*Upstream state checked after the merge on 3 September 2026. Production
remained on its qualified Vulkan 0.7.1 binary.*
