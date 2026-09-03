---
layout: post
title: "Lazy auto mode can halve Qwen3.8 prefill on Strix Halo"
seo_title: "Qwen3.8 Vulkan lazy-mode regression"
date: 2026-09-03 17:00:00 +0100
last_modified_at: 2026-09-03 17:00:00 +0100
permalink: /blog/2026/09/03/llamacpp-lazy-mode-auto-strix-halo-vulkan/
categories: [local-ai, performance, upstream]
tags: [qwen3.8, qwen4exp, llama-cpp, vulkan, lazy-loading, prefill, strix-halo]
author: Darren Soothill
editorial_standard: soothill-human-v1
editorial_review_status: approved
editorial_reviewer: Darren Soothill
editorial_reviewed_at: 2026-09-03
series: "Local LLMs on Strix Halo"
series_order: 26
description: "An exact Strix Halo report measures 216 versus 406 prompt tokens/s from one llama.cpp lazy-mode switch. New canaries need it made explicit."
---

> **Source record:** open llama.cpp [issue 28160](https://github.com/ggml-org/llama.cpp/issues/28160)
> reports a Vulkan Qwen3.8 Flash Next prefill regression after commit
> `257813839`. On Ryzen AI MAX+ 395, `--lazy-mode auto` produced 216 prompt
> tokens/s while `--lazy-mode off` produced 406. I have not repeated this A/B
> on the EVO-X3 production model.

This is a useful warning about defaults. The reported decode rate barely
changes; prompt processing almost halves. A short interactive test with a tiny
prompt could therefore look healthy while long-context work becomes painfully
slower.

The difference comes from one launch option, not a new quant or a broad backend
swap.

## The reported comparison

The issue uses Qwen3.8 Flash Next UD-IQ4_XS, full Vulkan offload and the same
Radeon 8060S/gfx1151 class as EVO-X3. Its `llama-bench` results are:

| Build and setting | pp512 | tg128 |
| --- | ---: | ---: |
| b10723-era build, lazy auto | **216 tokens/s** | 24.1 tokens/s |
| Same build, lazy off | **406 tokens/s** | 24.2 tokens/s |
| Before first-bad commit | 429 tokens/s | 25.6 tokens/s |

The author bisected the change to the update that allows automatic mode to map
large embedding tensors lazily. Reverting an unrelated GDN/LID change did not
alter the result. Another Strix Halo user confirmed the regression in the
issue.

The current maintainer explanation is also important: `auto` means “use lazy
reading when the embedding tensor is very large”, not “select the fastest
placement for this device”. It is a fit/convenience heuristic. On a unified-
memory iGPU, the trade-off can point in the opposite direction from a discrete
GPU that cannot otherwise fit the model.

## Why this does not rewrite my existing numbers

The qualified production route is a Nathan Vulkan 0.7.1 build from before the
reported first-bad change. It already uses an explicit CPU placement for the
per-layer token embedding and has measured long-prompt performance. The issue
does not invalidate those retained results.

It does change how I would test a current llama.cpp or packaged Lemonade
backend. “Default options” is no longer a sufficiently controlled arm. I would
record both:

```text
--lazy-mode auto
--lazy-mode off
```

The comparison needs actual long-prefill work, model-load time, GTT,
`MemAvailable`, page faults and output hashes. Turning lazy mode off can improve
placement but may also make a larger-than-memory model fail to load. Throughput
alone is not the complete result.

## A note on Lemonade 11.9

Lemonade 11.9 updates its packaged llama.cpp to b10723, the build family named
in the issue. My [11.9 production upgrade](/blog/2026/09/03/lemonade-119-evox3-upgrade/)
did not replace the custom Qwen inference binary, so the control-plane upgrade
did not silently introduce this regression. A stock-backend user should not
assume the same protection.

## Where I would stop claiming

This is one model quant, one prompt shape and one Vulkan software stack. It
does not prove that every iGPU or every architecture loses 47%. Lazy loading
may still be the only workable option when weights exceed available memory.

For an EVO-X3 model that already fits, my starting choice for a new b10723-or-
later canary would be explicit `--lazy-mode off`, followed by the measured A/B.
I would not allow an `auto` heuristic to remain an unrecorded benchmark
variable.

*Upstream state checked 3 September 2026. No local runtime option or production
service was changed for this review.*
