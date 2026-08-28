---
layout: post
title: "Qwen3.8 Flash Next: the Q8 cache made Vulkan 0.7.1 fit"
seo_title: "Qwen3.8 Vulkan 0.7.1 Q8 on AMD Strix Halo"
date: 2026-08-28 01:45:00 +0100
last_modified_at: 2026-08-28 01:45:00 +0100
permalink: /blog/2026/08/28/qwen38-vulkan-071-q8-dual-slot-production/
categories: [local-ai, benchmarks, engineering]
tags: [qwen3.8, qwen4exp, llama-cpp, vulkan, strix-halo, lemonade, prompt-caching, long-context]
author: Darren Soothill
editorial_standard: soothill-human-v1
editorial_review_status: approved
editorial_reviewer: Darren Soothill
editorial_reviewed_at: 2026-08-28
series: "Local LLMs on Strix Halo"
series_order: 19
description: "I moved Qwen3.8 Flash Next to a Q8 dual-slot Vulkan 0.7.1 profile, measured 5–8% gains and passed a 30-minute cached concurrency soak."
---

> **Test record:** I restarted the preferred 103.7 GiB Qwen3.8 Flash Next
> service on my 128 GB Ryzen AI MAX+ 395 workstation, kept its two 262K
> slots and explicit prompt cache, then qualified a Vulkan 0.7.1 userspace
> bundle with Q8 K/V storage. The production result improved cold prompt
> processing by 8.5% and cached two-request throughput by 5.1%. It completed
> a 30-minute mixed soak without a wrong answer, request leak, failed recovery
> or AMD GPU fault. The former fast profile was not used as a fallback.

I did not want this test rescued by another model. The question was narrower:
could the preferred Qwen3.8 Flash Next route restart with two slots, restore
cached prefixes correctly and remain the service behind Lemonade?

It can. The profile now running on `evox3` uses Q8 rather than F16 K/V storage
and a v0.7.1 Vulkan bundle. The gain is not spectacular, but it is broad: cold
prefill, repeated decode and simultaneous requests all moved in the right
direction. More importantly, the memory shape survived the soak that the F16
version could not start cleanly.

## What changed in the production profile

This follows my earlier [ROCm-versus-Vulkan Qwen3.8
work](/blog/2026/08/27/qwen38-flash-next-rocm-vulkan-strix-halo/). The model is
still [Unsloth's four-shard
`Qwen3.8-Flash-Next-UD-Q4_K_XL`](https://huggingface.co/unsloth/Qwen3.8-Flash-Next-GGUF),
and the unusual 26.82 GiB per-layer token-embedding table still remains
CPU-backed. I did not change the model quantisation or increase the 40-layer
GPU offload.

The served profile is now:

```text
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

The executable reports llama.cpp build 10637 at commit `39817c47`; the
previous production path reported build 10707 at `250b61446`. Those build
numbers come from different source lines, so I am not treating the smaller
number as an upgrade by itself. The item under test was the complete compatible
runtime: the experimental [Qwen4Exp
implementation](https://github.com/ggml-org/llama.cpp/pull/27742), the v0.7.1
Vulkan userspace bundle and the Q8 cache configuration.

Q8 was not an optional afterthought. The first v0.7.1 run retained the F16 K/V
cache and failed with `Not enough memory for command submission`, followed by
a Vulkan device loss. The successful Q8 candidate peaked at 70.89 GiB of GTT,
compared with 77.31 GiB for a separate two-slot F16 control on the current
build. Minimum available system memory rose from 38.53 GiB to 46.12 GiB.

That 6.42 GiB reduction was the difference between a failed candidate and one
worth measuring.

## The new baseline

I compared the previous preferred service with the promoted profile on the
same machine. Both used two slots, 40 offloaded layers, the same model and the
same 4 GiB host prompt cache. The material difference was the runtime package
and K/V representation.

| Served test | Previous production | Vulkan 0.7.1 / Q8 | Change |
| --- | ---: | ---: | ---: |
| Cold 3,149-token prefill | 103.76 tokens/s | **112.56 tokens/s** | **+8.5%** |
| Median decode over 20 cache cycles | 15.32 tokens/s | **15.90 tokens/s** | **+3.8%** |
| Two uncached requests, aggregate | 16.86 tokens/s | **17.86 tokens/s** | **+6.0%** |
| Two cached requests, aggregate | 24.23 tokens/s | **25.45 tokens/s** | **+5.1%** |

The improvement also appeared in the small developer workload set. The three
repeats for each case all passed on the candidate:

| Workload | Previous prompt / generation | Vulkan 0.7.1 / Q8 prompt / generation |
| --- | ---: | ---: |
| Structured JSON | 51.95 / 16.97 tokens/s | **57.38 / 18.12 tokens/s** |
| Python code | 55.73 / 16.59 tokens/s | **61.03 / 17.61 tokens/s** |
| Prose | 47.97 / 16.39 tokens/s | **52.31 / 16.82 tokens/s** |

The old Python record failed its strict formatter because the answer included
Markdown fences. I corrected that validation before the new run, so the table
is a performance comparison, not evidence that the runtime alone repaired code
formatting.

The [production comparison
data](/assets/data/qwen38-vulkan071-production-comparison-2026-08-28.csv)
contains the unrounded measurements and test boundaries.

## Cache hits survived slot changes and divergent prompts

A quick identical repeat is not enough to qualify prompt caching. It can hide
a same-slot shortcut and says nothing about what happens after the other slot
has been used.

The production gate began with an uncached 3,149-token prompt. It took 28.609
seconds end to end. The immediate repeat restored 3,145 tokens and completed
in 0.697 seconds. After a different 3,388-token history had occupied the other
path, the first prefix restored from the bounded RAM cache and completed in
0.683 seconds.

I then changed only the suffix, returned to the original request and alternated
the two histories for another 20 cycles. Every answer was exact. Every cycle
restored at least 3,145 prompt tokens. The measured prompt-processing speed-up
was 148.9 times for the immediate hit and 159.3 times after RAM restoration;
those figures refer to prompt work, not total generation speed.

The simultaneous test sent two different exact-output requests through
Lemonade at the same time. Both began together, both returned their own marker
sequence and both received a cache hit on the repeated pair. That matters more
than a higher single-request number: the service is intended to accept two
independent clients without allowing one response to appear in the other.

Two slots do not create one 524K request. `/slots` reports two independent
262,144-token allocations.

## The half-hour run found one problem in the test, not the server

The extended run lasted 1,820.47 seconds. It completed ten structured-JSON
iterations, ten isolation iterations, ten cache pairs, ten cancellation and
recovery iterations, and three long prose requests. The long requests each
used 31,012 prompt tokens and generated 768 tokens.

| 31K run | Prompt processing | Generation | Wall time |
| --- | ---: | ---: | ---: |
| Cold | 77.36 tokens/s | 12.17 tokens/s | 463.92 s |
| Repeat 1 | 81.73 tokens/s | 12.29 tokens/s | 441.99 s |
| Repeat 2 | 81.73 tokens/s | 12.50 tokens/s | 440.93 s |

The raw soak runner initially labelled those three requests as failures because
it still contained a 17 tokens/s threshold written for a smaller speculative
ROCmFPX model. That was the wrong comparator for a 103.7 GiB non-speculative
model whose matched production baseline was 11.86 tokens/s. I did not edit the
raw result to make it green. I retained the three threshold failures, added a
separate adjudication and required every functional check plus a faster
same-model result. Median long-output generation was 12.29 tokens/s, 3.6%
above the matched baseline.

After the soak, the two-request check reached 19.00 aggregate tokens/s
uncached and 25.24 tokens/s cached, with both answers correct. Across 1,832
resource samples, available memory did not fall below 45.64 GiB and GTT did not
exceed 70.91 GiB. The kernel capture contained no matching AMD GPU reset, page
fault, device loss or SVM mapping failure.

The [soak summary](/assets/data/qwen38-vulkan071-soak-2026-08-28.csv) records
the raw threshold outcome alongside the production-specific adjudication. That
distinction is deliberate.

## The tempting alternatives did not make the default

I tested four nearby options before promoting this one.

First, `--tensor-read-lazy on` on the old build did not release useful memory.
Cold prefill fell from 103.76 to 95.03 tokens/s, while uncached and cached
two-request throughput also slipped. I rejected it.

Second, the newer EngramHalo Vulkan source at commit `930918c` worked with Q8.
Its ordinary decode was marginally faster, but prompt processing on the three
developer workloads was 8–10% behind the v0.7.1 package. It was not a broad
replacement.

Third, adding the Q8 MTP sidecar to that branch produced 26.78 tokens/s on
structured JSON and 45.36 tokens/s on Python code. Prose went the other way:
draft acceptance fell to 61.7%, and generation dropped to 14.44 tokens/s from
17.92 tokens/s without MTP. That is a useful specialist result, not a safe
general default.

Finally, the EngramHalo ROCm 7.14 build failed even as a one-slot Q8 profile.
The kernel repeatedly reported `SVM mapping failed, exceeds resident system
memory limit`, including with offload limited to 40 layers. The branch's
suggested workaround was to disable IOMMU. I had already tested that system
change: it delivered little performance and removed functionality I need, so I
did not weaken the host configuration to make this model start.

The [candidate decision
record](/assets/data/qwen38-vulkan071-candidates-2026-08-28.csv) keeps the
positive and negative results together.

## Moving it behind Lemonade

The production change is release `20260828-v13-qwen4exp-v071-q8`. Lemonade
11.8 remains the public service on port 13305; llama.cpp listens only on
`127.0.0.1:8001`. There is no separate port 18802 service.

The guarded launcher now refuses to start if another `llama-server` is
resident or if model memory has not cleared. While the model is running, it
records available memory and GTT once per second. It stops the backend if
available memory falls below 18 GiB, GTT exceeds 90 GiB or a new AMD GPU memory
fault appears.

The first deployment attempt proved the rollback rather than the model. My
production cache script omitted the `model` field accepted by direct
llama.cpp but required by Lemonade, so the router returned HTTP 400. The
deployment guard restored the previous preferred profile automatically. I
corrected the request, repeated the cutover and only marked the release passed
after the cache, concurrency, executable-identity and kernel checks completed.

`llm`, `llm-exact` and `Jarvis` now resolve to the new preferred profile. The
older fast profile remains registered under its explicit `llm-fast` name, but
it was not loaded during qualification or deployment and normal traffic does
not fall back to it.

## Where I would stop claiming

This test proves the two-slot allocation, cache behaviour, concurrent request
isolation and a 31K-plus-output workload for 30 minutes. It does not prove two
simultaneous near-262K prompts, a 24-hour memory trend or identical behaviour
under unrelated desktop memory pressure. Q8 K/V storage also changes cache
precision, so the exact-output and developer checks are evidence for these
workloads rather than a universal quality result.

For the general Qwen route, I would keep the v0.7.1/Q8 profile now in
production. It recovered enough memory to make the preferred dual-slot layout
reliable and added roughly 4–8% where it matters, without changing how clients
reach Lemonade. I would revisit the MTP branch only as an explicit
high-acceptance coding profile, after a longer mixed-output qualification.

*Benchmark and deployment record: 28 August 2026. GMKtec EVO-X3; AMD Ryzen AI
MAX+ 395 / Radeon 8060S; 128 GB unified memory; Lemonade 11.8.0; Qwen3.8 Flash
Next UD-Q4_K_XL; llama.cpp build 10637 at `39817c47`; Vulkan v0.7.1 userspace
bundle. See the [qualification
manifest](/assets/data/qwen38-vulkan071-production-manifest-2026-08-28.json)
for hashes, limits and retained-result locations.*
