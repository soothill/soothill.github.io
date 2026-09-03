---
layout: post
title: "Qwen3.8 MTP can mix users' answers across slots"
seo_title: "Qwen3.8 MTP cross-slot content leak"
date: 2026-09-03 17:00:00 +0100
last_modified_at: 2026-09-03 17:00:00 +0100
permalink: /blog/2026/09/03/qwen38-mtp-parallel-cross-slot-contamination/
categories: [local-ai, engineering, upstream]
tags: [qwen3.8, qwen4exp, llama-cpp, mtp, speculative-decoding, concurrency, strix-halo]
author: Darren Soothill
editorial_standard: soothill-human-v1
editorial_review_status: approved
editorial_reviewer: Darren Soothill
editorial_reviewed_at: 2026-09-03
series: "Local LLMs on Strix Halo"
series_order: 24
description: "A gfx1151 report shows Qwen3.8 draft-MTP content crossing between concurrent slots. That is a correctness blocker for my dual-slot service."
---

> **Incident record:** open llama.cpp [issue 28286](https://github.com/ggml-org/llama.cpp/issues/28286)
> reports Qwen3.8 Flash Next MTP responses drifting into another concurrent
> request when `--parallel` is greater than one. The report is from the same
> Ryzen AI MAX+ 395/gfx1151 class as EVO-X3, on a downstream ROCm branch. I
> have not reproduced it on my production Vulkan binary because production
> does not run MTP.

This is a more serious failure than a crash. The output remains readable and
plausible while including material that belongs to another request.

In one reported run, a quicksort completion moved into Roman-history prose. A
CAP-theorem answer acquired fragments of a different sorting function. There
was no garbage-token signature to make the fault obvious to a user or a simple
UTF-8 health check.

For a shared service, that is both a correctness and isolation failure.

## The reproducer is uncomfortably close to production

The reporter used Qwen3.8 Flash Next UD-Q3_K_XL with a Q8_0 MTP sidecar on
Strix Halo, Q8 K/V, Flash Attention and four concurrent slots. Four distinct
greedy prompts were submitted at once. The fault repeated with GPU graph
capture disabled, which weakens the first explanation that this was merely a
HIP graph-capture problem.

It did not reproduce at `--parallel 1`. A deliberately simple ROCKET-versus-
BANANA control also stayed isolated across several rounds. Complex prompts
were needed to make the drift visible, which helps explain how a short marker
smoke could miss it.

The production EVO-X3 service differs in three important ways: it uses Vulkan,
UD-Q4_K_XL and two slots rather than ROCm, Q3_K_XL and four. Those differences
mean the report does not prove that my route would fail. They do not make it
safe to assume that two slots avoid a bug triggered by more than one.

## Why normal correctness tests are too weak

An exact `OK` request checks one output in isolation. Even two simultaneous
requests with low-entropy markers may pass, as the issue's repetitive control
did. A useful qualification needs prompts whose content cannot plausibly
overlap:

- unrelated code completions with unique function and variable names;
- prose from different historical and technical domains;
- four or more repeated rounds at temperature zero;
- response-to-request binding checked from each HTTP result, not list order;
- token-level scans for phrases originating in every other prompt.

I would also force draft rejection at different lengths and run the ABCCBA
state sequence in both slots. The suspected area is shared or incorrectly
keyed state in the draft/verify path, so a single clean batch is not enough.

## The operational decision is already made

The live model intentionally exposes two 262K slots. Dropping to one slot would
remove a production capability in exchange for an MTP gain that has not been
measured on this machine. Enabling MTP without dropping to one would accept an
open content-isolation risk.

I would do neither. Production stays on the non-speculative two-slot Q8 route.
The new [Unsloth MTP files](/blog/2026/09/03/qwen38-mtp-sidecars-qwen4exp/)
remain single-slot canary material until upstream fixes the issue and the exact
mixed-content test passes locally.

## Where I would stop claiming

Issue 28286 is one downstream-branch report, not a universal result for every
backend or model. Its suspected root cause has not yet been proved and no
upstream fix is attached at the time of writing.

It is nevertheless sufficient to block my deployment. Isolation failures do
not need a second production incident before they become material.

*Upstream state checked 3 September 2026. The existing production route has no
MTP sidecar and was not changed for this review.*
