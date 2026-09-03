---
layout: post
title: "A Qwen3.8 prompt-cache slot can loop forever"
seo_title: "Qwen3.8 prompt-cache livelock"
date: 2026-09-03 17:00:00 +0100
last_modified_at: 2026-09-03 17:00:00 +0100
permalink: /blog/2026/09/03/qwen38-prompt-cache-livelock-two-slot/
categories: [local-ai, engineering, upstream]
tags: [qwen3.8, qwen4exp, llama-cpp, prompt-caching, concurrency, vulkan, strix-halo]
author: Darren Soothill
editorial_standard: soothill-human-v1
editorial_review_status: approved
editorial_reviewer: Darren Soothill
editorial_reviewed_at: 2026-09-03
series: "Local LLMs on Strix Halo"
series_order: 25
description: "Issue 28280 records a Qwen3.8 prompt-cache checkpoint livelock on Strix Halo. Health alone can miss it, so slot progress needs watching."
---

> **Incident record:** open llama.cpp [issue 28280](https://github.com/ggml-org/llama.cpp/issues/28280)
> records a Qwen3.8 Flash Next slot repeatedly erasing the same prompt-cache
> checkpoint without advancing. It was observed on a Windows Vulkan build with
> Ryzen AI MAX+ 395, two slots and Q8 K/V. My Linux/RADV production route has
> not reproduced this exact incident.

The dangerous part of this failure is that the server is not entirely dead.
One slot remains able to answer while the other loops on the same checkpoint,
holds its request and never becomes available again.

A process-level health probe can therefore say “alive”. A short request routed
to the other slot can even say “correct”. Neither proves that the service still
has the concurrency capacity it advertises.

## What the stuck slot looked like

The upstream report used llama.cpp b10731, Qwen3.8 Flash Next, two parallel
slots, prompt caching and a large repeated conversational prefix. Most turns
completed in 5–10 seconds. Roughly one in ten failed to return during the
reported session.

Thirteen minutes after the client disconnected, `/slots` still showed the
affected slot processing an 11,128-token prompt. Only 167 tokens had been
processed. The server log repeated one operation at roughly 600 ms intervals:

```text
erasing old context checkpoint
pos_min = 11127, pos_max = 11127, n_tokens = 11128
```

The checkpoint was created and erased at the final prompt position without
forward progress. Unloading the model was the only action reported to free it.

The failure appeared on two different quants, two load modes and two context
allocations. That does not locate the root cause, but it makes “bad quant file”
or one lazy-loading choice a weak explanation.

## Why it belongs in the EVO-X3 gate

My production route also combines a hybrid Qwen4Exp model, two slots, prompt
caching, Q8 K/V and long repeated prefixes. The operating system and Vulkan
driver differ, and the qualified binary is older than b10731. This is not
evidence that the current service is already livelocking.

It is evidence that a future upstream canary needs a better availability test:

- pin a long conversation to one slot and reuse almost all of its prefix;
- cancel selected clients while checkpoint creation is active;
- poll per-slot processed-token counts, not only `/health`;
- fail if a busy slot makes no progress across a bounded interval;
- prove that the watchdog can unload, clean memory and restore the default
  model without losing the healthy slot's completed output.

The existing 14,400-second Lemonade timeout protects legitimate long prefills.
It would be the wrong detector here: waiting four hours for a counter that has
stopped at 167 is not resilience.

## The production consequence

I would keep the current known-good runtime and add slot-progress telemetry to
the next server qualification. I would not promote b10731 or a descendant on
the strength of aggregate throughput while this reproducer is absent.

There is also no reason to disable prompt caching pre-emptively on the
qualified build. The current service passed ABCCBA restoration and repeated
cache cycles; removing that feature would impose a known latency cost to avoid
an unobserved fault in a different build.

## Where I would stop claiming

The report is Windows/proprietary-Vulkan evidence, not a Linux/RADV result. It
does not prove that all two-slot Qwen3.8 servers livelock or that checkpointing
alone is the cause.

It does show that whole-process health is an incomplete availability signal.
For this service, “both slots continue to advance” is now part of correctness.

*Upstream state checked 3 September 2026. No production process, cache setting
or model was changed for this source review.*
