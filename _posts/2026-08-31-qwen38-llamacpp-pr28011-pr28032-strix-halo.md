---
layout: post
title: "Two llama.cpp Qwen fixes on Strix Halo: no free speed-up"
seo_title: "llama.cpp PR 28011 and 28032 on Qwen3.8 Strix Halo"
date: 2026-08-31 16:15:00 +0100
last_modified_at: 2026-08-31 16:15:00 +0100
permalink: /blog/2026/08/31/qwen38-llamacpp-pr28011-pr28032-strix-halo/
categories: [local-ai, benchmarks, engineering]
tags: [qwen3.8, qwen4exp, llama-cpp, vulkan, strix-halo, lemonade, prompt-caching, gpu-recovery]
author: Darren Soothill
editorial_standard: soothill-human-v1
editorial_review_status: approved
editorial_reviewer: Darren Soothill
editorial_reviewed_at: 2026-08-31
series: "Local LLMs on Strix Halo"
series_order: 20
description: "I backported two merged llama.cpp Qwen fixes into the qualified Strix Halo runtime. One was 3–5% slower; the other lost the Vulkan device during model load."
---

> **Test record:** I backported two merged llama.cpp changes into the qualified
> Qwen3.8 Flash Next Vulkan 0.7.1 runtime on my 128 GB Ryzen AI MAX+ 395
> workstation. PR 28011 passed correctness, 20 prompt-cache cycles and two-slot
> isolation, but the useful lanes were 3.5–5.0% slower. PR 28032 passed all 453
> focused Vulkan TOP_K tests, then lost the device while loading the full
> 103.7 GiB production model. I promoted neither candidate and restored the
> existing dual-slot Q8 service.

The attractive version of this test was simple: take two small upstream fixes,
measure an easy improvement and move the production service forward. That is
not what happened.

Both changes are sensible in their own scope. [PR
28011](https://github.com/ggml-org/llama.cpp/pull/28011) stops a KV-cell lookup
once it has found the sequences actually present in the cell. [PR
28032](https://github.com/ggml-org/llama.cpp/pull/28032) adds a Vulkan radix
path for large TOP_K operations and fuses the gather, F16 mask and TOP_K work
used by Qwen4-style QSA. The first should reduce wasted CPU scanning. The
second removes several GPU dispatches from a graph that matters to this model.

Neither produced a deployable local gain.

## The short answer

| Candidate | Functional result | Performance result | Decision |
| --- | --- | --- | --- |
| PR 28011, KV sequence scan | Exact output, cache and concurrency passed | 3.5–5.0% slower in the useful lanes | Reject |
| PR 28032, Vulkan large TOP_K / QSA fusion | 453/453 backend tests passed; full model load device-lost | No served measurement | Reject |
| Both patches together | Built only | Deliberately not run after PR 28032 failed | Do not layer failures |

My materiality rule was set before the run: more than 5% median improvement in
a targeted lane, repeated in both long samples, with no correctness, cache,
concurrency, memory, kernel or recovery regression. A newer merge commit was
not itself a result.

The [compact comparison
data](/assets/data/qwen38-pr28011-pr28032-canary-2026-08-31.csv) contains the
unrounded figures. The [qualification
manifest](/assets/data/qwen38-pr28011-pr28032-manifest-2026-08-31.json) records
the source, patch and binary hashes, including the failed candidate.

## Keeping the existing runtime fixed

The production base remained the Nathan Vulkan v0.7.1 Qwen4Exp source at
llama.cpp commit `39817c47`, reported as build 10637. I built three separate
canaries from that source: PR 28011 alone, PR 28032 alone and the combination.
This avoided comparing a broad upstream update with the known service.

The PR 28011 diff applied directly. The PR 28032 diff required one context
hunk at fuzz 2 against the older source, but I did not rewrite its logic. This
is therefore a narrow backport experiment, not a claim about a current
upstream-main binary.

Every served arm used the same model and production shape:

```text
model                  Qwen3.8-Flash-Next-UD-Q4_K_XL
model size             103.688 GiB, four shards
total context          524,288 tokens
parallel slots         2
context per slot       262,144 tokens
GPU-offloaded layers   40
batch / micro-batch    512 / 128
K/V cache              Q8_0 / Q8_0
host prompt cache      4 GiB
prompt caching         enabled
idle-slot caching      disabled
model loading          mmap
speculative decoding   disabled
```

The per-layer token-embedding tensor remained CPU-backed. The model name,
quantisation, driver package, sampling settings and public Lemonade route did
not change.

## The small KV scan change was consistently slower

PR 28011 changes only nine source lines. Instead of scanning the complete
maximum sequence table for every KV cell, it stops after finding the number of
sequences that the cell says it contains. I expected the benefit, if visible,
to appear around repeated cache lookup and two-client work rather than GPU
decode.

The direction was the opposite:

| Served test | Qualified production | PR 28011 canary | Change |
| --- | ---: | ---: | ---: |
| 9,025-class cold prefill | 121.29 tokens/s | 116.87 tokens/s | **−3.6%** |
| 35,908-class cold prefill | 109.92 tokens/s | 105.84 tokens/s | **−3.7%** |
| Median decode, four samples | 18.38 tokens/s | 17.73 tokens/s | **−3.5%** |
| Two uncached requests, aggregate | 18.79 tokens/s | 17.94 tokens/s | **−4.5%** |
| Two cached requests, aggregate | 25.92 tokens/s | 24.62 tokens/s | **−5.0%** |

The two long prefill rows are medians of two independent probes. Both
candidate repeats were slower than their corresponding baseline repeat. The
candidate labels added 13 prompt tokens, less than 0.2% in these rows; the
throughput metric already normalises by processed tokens, so that does not
explain a 3–4% gap.

The short rows were noisier. The first 635-token canary request paid a large
cold-start cost and pulled its two-sample median down by 17.7%. I have kept
that result in the data rather than presenting it as a steady-state
regression. Even the warmed short repeat was still slower, but the long and
concurrent results are the useful basis for the decision.

Functionally, PR 28011 was sound in this test. Both deterministic probe sets
returned every marker. The ABCCBA-style cache test completed 20 cycles, with
same-slot, RAM-restored, divergent-suffix and return-after-divergence hits. The
simultaneous pair returned both independent markers uncached and cached. Peak
GTT was 70.90 GiB and the 18 GiB memory guard did not fire.

That is a correctness pass and a performance rejection.

## The TOP_K patch passed its tests and failed the model load

PR 28032 is the more interesting optimisation for Qwen3.8 Flash Next. Its
radix path covers large values of `k`, and the QSA graph fusion is intended to
replace several intermediate operations with one Vulkan dispatch.

Before loading the model, I ran the complete Vulkan TOP_K backend selection.
All 453 tests passed. That included the new large-k shapes, multi-row cases and
ties. The candidate binary then began loading the same four model shards from
the same clean-memory gate used by the working PR 28011 canary.

It never reached ready state. RADV reported:

```text
radv/amdgpu: Not enough memory for command submission.
ggml_vulkan: device lost on Vulkan0
vk::Queue::submit: ErrorDeviceLost
```

The last resource samples before failure still showed 48.78 GiB of available
system memory and 71.38 GiB of GTT. Those counters do not prove that a suitable
command-submission allocation was available, and they do not identify the
root cause. They do show why I will not reduce this to “the 128 GB machine ran
out of RAM”.

There is no PR 28032 throughput number. Publishing zero tokens per second
would imply a slow benchmark; the candidate failed availability before it
served a request. The narrow conclusion is that this backport, driver and full
production allocation did not qualify. It is not evidence that the merged
upstream patch fails on every Vulkan device or with a smaller Qwen profile.

## Recovery became part of the result

The failed process left AMD VM cleanup errors in the kernel log, including
`Couldn't update BO_VA (-12)` and an `amdgpu_vm_pt_free` oops. The first
automatic production reload then hit the same device-loss residue. One dead
`llama-server` task remained visible in `Z/X` state even after the control
plane stopped; it had no file descriptors and GTT had returned to 32 MiB, but
the production wrapper correctly refused any process with that name.

I did not remove the wrapper's persistent safety check. I restarted the
Lemonade owner, verified that no live inference process remained and used a
temporary, non-persistent path shim for one recovery launch. It ignored only
tasks already in kernel-dead `Z/X` state and continued to reject any live
`llama-server`. Once the qualified production model reached ready state, I
removed the shim and restored the normal service environment before loading
the NPU helper.

The final health state again reports the preferred Qwen service unpinned, with
524,288 total context, two slots, 40 GPU layers, Q8 K/V, the 4 GiB prompt cache
and `auto_evict=false`. The residency warmer and guard timer are enabled. A
fresh request returned exactly `RECOVERY-OK`.

The kernel-dead task will remain visible until the workstation next reboots.
It holds no model or GPU memory, and the live production service is healthy,
but it is still a recovery scar worth recording.

## Why I stopped before the combined binary

I had already built the combined PR 28011 plus PR 28032 canary. Running it
after the PR 28032-only device loss would not answer the original question. It
would layer a known slower change onto a candidate that had already failed the
availability gate, while exposing production to another full GPU recovery.

I preserved the combined binary hash and stopped. That is the difference
between building a candidate and qualifying it.

## Where I would stop claiming

This test does not show that PR 28011 is universally slower. A server with many
sequences per KV cell, a different slot count or a workload dominated by the
changed lookup may still benefit. It shows that the patch did not improve this
Qwen3.8 dual-slot service and regressed every measured performance lane.

Likewise, the PR 28032 failure belongs to this exact backport, Vulkan userspace
bundle, AMD driver state, 103.7 GiB model and 524K/two-slot allocation. A clean
upstream-main build, a smaller context or a different GPU may behave
differently. I would retest only after a relevant upstream or driver change,
and I would begin with a fresh host state rather than treating this failed load
as a performance sample.

For the general Qwen route on `evox3`, the decision is uncomplicated: keep the
qualified Vulkan 0.7.1/Q8 production profile. Neither of these two upstream
changes delivered a material, safe improvement.

*Benchmark and recovery record: 31 August 2026. GMKtec EVO-X3; AMD Ryzen AI
MAX+ 395 / Radeon 8060S; 128 GB unified memory; Lemonade 11.8.0; Qwen3.8 Flash
Next UD-Q4_K_XL; qualified llama.cpp build 10637 at `39817c47`; Vulkan v0.7.1
userspace bundle. Exact commits, patches, binaries and recovery notes are in
the [qualification
manifest](/assets/data/qwen38-pr28011-pr28032-manifest-2026-08-31.json).*
