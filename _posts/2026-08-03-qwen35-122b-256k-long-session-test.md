---
layout: post
title: "The long-session test: 122B at a 256K context"
seo_title: "Qwen3.5 122B at 256K: a 101-minute soak"
date: 2026-08-03 12:00:00 +0100
last_modified_at: 2026-08-03 18:00:00 +0100
permalink: /blog/2026/08/03/qwen35-122b-256k-long-session-test/
categories: [local-ai, benchmarks, reliability]
tags: [qwen3-5, long-context, soak-test, memory, lemonade, strix-halo]
author: Darren Soothill
series: "Local LLMs on Strix Halo"
series_order: 5
description: "A 101-minute, 165-request soak of Qwen3.5 122B at a nearly full 256K context, including throughput, memory, thermals and request-retention fixes."
---

> **Test record:** Qwen3.5-122B-A10B `UD-Q4_K_XL` ran through an optimised `llama.cpp` ROCm backend for 6,088 seconds. The slot was 262,144 tokens, the measured prompt reached 260,812 tokens and the test completed 165 cached requests with zero misses.

Peak numbers qualify a machine for a screenshot. Long sessions qualify it for work.

The [model-size sweep](/blog/2026/08/03/finding-the-useful-quant-strix-halo/) showed that a 77GB 122B mixture-of-experts model fits on the EVO-X3 and generates at a useful rate. It did not show whether that rate survives a nearly full context, whether shared-memory allocation creeps upwards, whether the service retains giant request bodies or whether 100 minutes of heat reveals a driver failure.

Those are product questions. A local model intended for codebases, research corpora or long working sessions must be trustworthy after the novelty of the first response has worn off. I therefore treated endurance as an acceptance test with explicit pass and fail gates, not as an anecdote about leaving a terminal open overnight.

## The workload

The soak used:

| Item | Configuration |
| --- | --- |
| Model | Qwen3.5-122B-A10B `UD-Q4_K_XL` |
| Backend | Optimised `llama.cpp`, ROCm 7.14 development build, `gfx1151` |
| Lifecycle layer | Patched Lemonade service |
| Runtime slot | 262,144 tokens |
| Actual full prompt | 260,812 tokens — 99.49% of the slot |
| K/V cache | `q8_0` for both K and V |
| Parallel slots | 1 |
| Batch / micro-batch | 8,192 / 2,048 |
| Duration | 6,088 seconds — 1h 41m 28s |
| Requests | 165, all served from the expected cache state |

The prompt was deliberately close to the limit but did not cross it. A test that silently truncates its input has not validated long context; it has validated the truncation policy. The server metrics and request results were therefore checked together.

The sequence mixed three kinds of work:

1. full-context prompt evaluation and generation;
2. repeated generation against cached portions of the context;
3. periodic full-context probes to expose performance drift.

That shape separates the expensive first evaluation from the common case of continuing to work inside an existing session. It also exercises the lifecycle service repeatedly instead of measuring only the backend process.

## Performance did not decay

| Measurement | First observation | Final observation | Change |
| --- | ---: | ---: | ---: |
| Full-context prompt processing | 119.7369 tok/s | 119.7270 tok/s | **-0.0082%** |
| Full-context generation | 13.3457 tok/s | 13.2998 tok/s | **-0.34%** |
| Cached quarter-context generation | 13.3477 tok/s | 13.3506 tok/s | **+0.0218%** |

Those deltas are operationally flat. The full-context prefill result changed by less than one hundredth of one percent. Generation at the end remained within 0.34% of the start, while the cached-quarter rate finished fractionally higher.

The absolute generation rate is lower than the short kernel benchmark because this is a served, nearly full-context workload with a large K/V cache. That difference is expected and is why both measurements belong in the product record. A 21 tok/s microbenchmark and a 13.3 tok/s full-context session answer different questions.

At roughly 13.3 generated tokens per second, a 500-token answer takes about 38 seconds after prompt work. That is useful for deliberate analysis, not instant UI copy. Long-context capability has an experience cost, and the interface should show progress rather than pretending that the request is a short chat turn.

## Memory reached a plateau

Shared memory makes Strix Halo unusually capable, but it also makes sloppy accounting easy. CPU RSS, AMDGPU GTT, available system memory and swap all need to be observed. One counter cannot describe the whole allocation.

| Memory signal | Observed result |
| --- | ---: |
| Backend maximum RSS | 81.0GiB |
| Early quarter-to-quarter backend increase | 713.5MiB |
| Backend second-half slope | +5.2MiB/hour |
| Lemonade increase across full run | +34.9MiB |
| Lemonade change in final 36 minutes | +12KiB |
| Minimum system memory available | 29.4GiB |
| Swap increase | 44.1MiB |
| AMDGPU GTT increase across full run | 34.2MiB |

The early RSS movement reflects the backend warming and filling its working set. The second half is the more useful leak signal: +5.2MiB per hour against an 81GiB process is small, and it is accompanied by only a 34.2MiB full-run GTT increase. Lemonade's final 36-minute change was 12KiB, effectively flat.

I would not extrapolate 101 minutes into a claim of indefinite stability. I would call it a passed soak with a sufficiently flat final slope to justify a longer overnight gate. The distinction matters: the test supports the next decision without claiming evidence it did not collect.

The 44.1MiB swap movement is also recorded rather than hidden. It is small relative to the host and did not correlate with throughput loss, but a production monitor should alert on sustained swap-in or swap-out. Model capacity should not depend on paging active inference data through NVMe.

## Heat and the driver

The maximum recorded temperature was **86°C**. The watchdog reported zero failures and the service completed every scheduled request.

The kernel log did contain an `amdgpu_amdkfd_restore_userptr_worker` warning. It did not coincide with a request error, performance step-down or rising memory slope. I therefore record it as a warning, not turn it into an outage after the fact.

For a production qualification I would keep the rule explicit:

- one driver warning with no correlated symptom creates an investigation item;
- a GPU reset, request corruption, cache miss, process restart or persistent throughput drop fails the run;
- repeated warnings across runs raise the severity even if this run completed.

Reliability work becomes much easier when failure criteria exist before the log is read.

## The hidden long-session problem was in the API process

The backend was not the only memory risk. Large OpenAI-compatible requests can contain several megabytes of prompt text. A long-lived Python API process may return those objects to its allocator without returning the underlying pages to the operating system. Repeating large requests can therefore leave resident memory far above the useful live set even when there is no Python object leak.

I addressed that behaviour in [Lemonade pull request #2873](https://github.com/lemonade-sdk/lemonade/pull/2873). The change applies a glibc allocation threshold for large request bodies, while respecting an operator's existing `MALLOC_MMAP_THRESHOLD_` or `GLIBC_TUNABLES` override. It is deliberately an operator-visible policy, not a hidden fight with the allocator.

The synthetic sequential stress test sent 170 requests with 3MiB bodies at concurrency one:

| API configuration | Retained RSS after stress | No-op request rate |
| --- | ---: | ---: |
| Baseline | 1,046,656KiB | 446.37 req/s |
| Combined allocator fix | 22,144KiB | 364.18 req/s |

That is a **97.88% reduction in retained RSS**. The no-op throughput cost is real because the synthetic backend does almost no work, making allocation overhead a large part of the request. It is a useful worst case, not a prediction of model-serving performance.

At concurrency 32 with 8,192 requests, the same fix reduced retained RSS from 1,053,516KiB to 30,364KiB. No-op throughput moved from 2,377 to 1,383 requests per second. Again, the deliberately empty backend magnifies the trade-off.

The real-backend tests settle whether that trade-off matters for the product:

| Backend workload | Baseline median wall time | Patched median wall time | Change |
| --- | ---: | ---: | ---: |
| ROCm, 16K prompt + 4,096 generated | 13.6116s | 13.1942s | **-3.07%** |
| Vulkan, 16K prompt + 1,024 generated | 3.3533s | 3.3695s | **+0.49%** |

ROCm prompt throughput was essentially neutral and generation increased slightly in that run. Vulkan generation changed by -0.70%. These are small run-to-run movements, not evidence that an allocator setting makes inference faster. They show that the substantial memory-retention improvement does not impose a material cost once real model work dominates the request.

The upstream pull request was still open and awaiting its external review workflow when this article was prepared. The soak used the patched build; readers using an unpatched release should not assume the same lifecycle-process memory result.

## The acceptance gates

I defined the test as a pass only if all of the following held:

- the prompt reached the intended near-256K token count without silent truncation;
- all 165 requests used the expected cache state;
- prompt and generation throughput remained within a small drift band;
- backend and lifecycle memory slopes flattened after warm-up;
- the host retained meaningful free memory and avoided active swap dependence;
- no GPU reset, model reload, backend restart or corrupted response occurred;
- temperature remained within the machine's controllable operating range;
- cleanup and restoration returned the service to its known everyday model.

The run passed those gates. The one operational caveat was restoration: the working Lemonade daemon is currently an isolated process rather than the active packaged systemd service. The model was restored successfully, but reboot persistence still needs to be made declarative.

## What 101 minutes proves

It proves that this EVO-X3 can keep a 122B four-bit model and a nearly full 256K context resident, serve 165 requests for more than 100 minutes and finish at essentially the same throughput with which it started. It also shows that the lifecycle layer can remain flat when large request-body allocation is handled intentionally.

It does not prove every 256K prompt is useful, that an overnight run will certainly pass or that the recorded driver warning can be ignored forever. Long context is valuable only when the model retrieves and reasons over it correctly; this soak validates the serving system, not semantic recall.

The product lesson is that endurance is a stack property. Model kernels, K/V cache, the Linux memory model, the HTTP process, allocator policy, thermals and recovery all contribute to whether a long session feels dependable.

With those layers measured, the final article can make a concrete recommendation: [the local LLM stack worth keeping](/blog/2026/08/03/local-llm-stack-worth-keeping/).

*Sources checked 3 August 2026: [Lemonade pull request #2873](https://github.com/lemonade-sdk/lemonade/pull/2873), the official [glibc tunables documentation](https://sourceware.org/glibc/manual/latest/html_node/Tunables.html) and [malloc tunable parameters](https://sourceware.org/glibc/manual/latest/html_node/Malloc-Tunable-Parameters.html). All performance, memory and thermal figures come from the retained 6,088-second EVO-X3 soak and associated request-memory benchmarks.*
