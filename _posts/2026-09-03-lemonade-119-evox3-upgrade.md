---
layout: post
title: "Lemonade 11.9 on EVO-X3: the control plane changed, inference did not"
seo_title: "Lemonade 11.9 EVO-X3 upgrade and benchmark"
date: 2026-09-03 17:00:00 +0100
last_modified_at: 2026-09-03 17:00:00 +0100
permalink: /blog/2026/09/03/lemonade-119-evox3-upgrade/
categories: [local-ai, benchmarks, engineering]
tags: [lemonade, qwen3.8, qwen4exp, strix-halo, upgrade, benchmarking, prompt-caching]
author: Darren Soothill
editorial_standard: soothill-human-v1
editorial_review_status: approved
editorial_reviewer: Darren Soothill
editorial_reviewed_at: 2026-09-03
series: "Local LLMs on Strix Halo"
series_order: 29
description: "I upgraded EVO-X3 from a patched Lemonade 11.8 daemon to official 11.9. Fixed prefill held, decode moved -1.93% and every route passed."
---

> **Test record:** I upgraded the EVO-X3 production control plane from a
> locally patched Lemonade 11.8.0 daemon to the official
> [Lemonade 11.9.0 release](https://github.com/lemonade-sdk/lemonade/releases/tag/v11.9.0).
> The model files, inference binaries, launch arguments, aliases and runtime
> state stayed fixed. Executable accuracy moved from 30/40 to 31/40, fixed
> prefill changed by -0.04%, fixed decode by -1.93% and streaming TTFT by
> -2.60%. I retained 11.9 in production.

This was deliberately not an inference-engine upgrade. Lemonade owns the API,
model registry, routing and lifecycle on this machine; custom backends still
do the token work. Keeping that boundary fixed made the question answerable:
does the new control plane preserve the service I already qualified?

It did. The interesting result is operational rather than dramatic. Official
11.9 absorbs the long-stream timeout behaviour I previously carried as a local
patch, restores the same routes and produces performance inside the recent
11.8 range.

The [paired benchmark data](/assets/data/lemonade-11.9-evox3-ab-2026-09-02.csv)
and [upgrade manifest](/assets/data/lemonade-11.9-evox3-manifest-2026-09-02.json)
contain the compact figures and identities.

## What 11.9 changes

The release's most useful change for this system is at commit
[`bb39eafc`](https://github.com/lemonade-sdk/lemonade/commit/bb39eafc22aa7e57fc7aeb8b7d384d70b44a4531):
streaming silence now follows the configurable `global_timeout` rather than a
fixed 120-second limit. A genuinely large Qwen prefill can be quiet for longer
than two minutes, so the old constant could kill a healthy request. Production
keeps its four-hour bound.

The [11.9 release notes](https://github.com/lemonade-sdk/lemonade/releases/tag/v11.9.0)
also record:

- corrected remote-origin handling and a new `allowed_origins` setting;
- recovery for cache and models misplaced by the 11.8 FHS migration;
- an experimental AMD HRX backend for gfx1100/gfx1151 Linux;
- llama.cpp b10723 with Qwen3-Next support;
- per-file typing for models in reserved extra-model directories.

I did not enable HRX or switch to packaged b10723. The latter is important
because b10723 is also the build family in the current
[Strix Halo lazy-loading regression](/blog/2026/09/03/llamacpp-lazy-mode-auto-strix-halo-vulkan/).
The custom dispatch boundary kept that unrelated inference change out of this
upgrade.

## The locked before-and-after run

Both arms used benchmark signature `16cf9033` and model fingerprint
`f425f930`. The test is a fixed 40-task HumanEval/MBPP subset at temperature
zero and seed one, with generated Python executed in a networkless container.
The Qwen profile remained 524,288 total context, two slots, 40 Vulkan GPU
layers, Q8 K/V and a 4 GiB host prompt cache.

| Metric | 11.8 before | 11.9 after | Change |
| --- | ---: | ---: | ---: |
| Executable tasks | 30/40 | **31/40** | +1 task |
| Task errors | 0 | 0 | unchanged |
| Fixed uncached prefill | 195.661 tokens/s | 195.579 tokens/s | **-0.04%** |
| Fixed decode | 18.931 tokens/s | 18.567 tokens/s | **-1.93%** |
| Median streaming TTFT | 0.2624 s | **0.2556 s** | **-2.60%** |
| Median task wall | **7.237 s** | 7.627 s | +5.39% |
| P95 task wall | **41.654 s** | 42.173 s | +1.25% |

Thirty-seven of forty extracted programs were byte-identical. Three changed,
and one of those changed its executable outcome from fail to pass. I do not
attribute that improvement to a smarter Lemonade release: the model and
sampler were fixed, but tiny runtime variation can still change an extracted
program at the edge of a decision.

The performance deltas also sit inside recent 11.8 history. Fixed decode had
ranged from 17.927 to 18.881 tokens/s and prefill from 189.580 to 197.334. On
that evidence, -1.93% is run noise rather than a material regression.

## Five routes, the same resolved targets

The capability sweep verified model selection and included switch costs where
applicable:

| Route | Target | 11.8 | 11.9 | Result |
| --- | --- | ---: | ---: | --- |
| `Jarvis` | Qwen3.5 4B, pinned NPU | 2.080 s | **1.818 s** | same marker |
| `llm` | Qwen3.8 Flash Next 125B | **0.846 s** | 1.908 s | same marker |
| `llm-reasoning` | Ornith 1.5 35B | 17.587 s | **15.878 s** | same marker |
| `deepseek-code` | DeepSeek Coder V2 | 47.596 s | **42.249 s** | same marker |
| `deepseek-flash` | DeepSeek V4 Flash | 76.847 s | **53.724 s** | same marker |

I would not read five independent speed claims from this table. It includes
cold model selection, storage state and cache effects. The fixed repeated
probes above are the controlled performance comparison; this table proves that
the routes still resolve, launch and answer.

## One restart race was worth keeping

During the first production restart, the Qwen wrapper's memory preflight
rejected an early concurrent warmer attempt. Lemonade evicted, retried and
reached the correct residency. Both benchmark and capability suites then
passed.

I changed the retained deployment script so it restores the pinned NPU helper
first and starts the Qwen warmer second. That makes a future replay
deterministic without weakening the memory guard.

The final service reports the official 11.9 binary, thirteen unchanged model
IDs, six unchanged aliases and byte-identical state JSON. LAN and Tailscale
listeners return version 11.9.0. No failed user unit or matching AMD GPU fault
was recorded. The unpinned Qwen model and pinned NPU helper are both healthy.

## Where I would stop claiming

This test qualifies Lemonade as the control plane around my existing backends.
It does not benchmark HRX, packaged b10723, a new model or the release on a
default installation. The route timings are operational smokes, not clean
engine comparisons.

The decision is still clear: retain official Lemonade 11.9. It removes one
local patch, preserves the measured service and leaves a complete 11.8 rollback
available. That is a worthwhile upgrade even without a tokens-per-second
headline.

*Tested 2 September 2026 on GMKtec EVO-X3, Ryzen AI MAX+ 395 / Radeon 8060S,
128 GiB unified memory. Lemonade 11.9.0 artifact SHA-256
`a18beaf7…eb204d`; installed `lemond` SHA-256 `0a164f82…bcb118`.*
