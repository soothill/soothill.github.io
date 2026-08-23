---
layout: post
title: "Vulkan 0.6.4 on Strix Halo: the coding models moved"
seo_title: "Vulkan 0.6.4 vs ROCm 7.14 on Strix Halo"
date: 2026-08-19 12:45:00 +0100
last_modified_at: 2026-08-19 16:31:00 +0100
permalink: /blog/2026/08/19/vulkan-064-rocm-714-strix-halo/
categories: [local-ai, benchmarks, engineering]
tags: [vulkan, rocm, llama-cpp, strix-halo, qwen3-coder, qwen3-8, mtp, lemonade]
author: Darren Soothill
editorial_standard: soothill-human-v1
editorial_review_status: approved
editorial_reviewer: Darren Soothill
editorial_reviewed_at: 2026-08-19
series: "Local LLMs on Strix Halo"
series_order: 12
description: "I compared Vulkan 0.6.2 and 0.6.4 with ROCm 7.14 on Strix Halo. The new release improved prefill by up to 72%, while decode performance stayed unchanged."
---

> **Test record:** I compared the Strix Halo Vulkan v0.6.4 release with my
> ROCm 7.14 `llama.cpp` build on the same 128GB GMKtec EVO-X3. The same GGUF
> files, Q8_0 KV cache and common launch settings were used for Qwen3.8-27B,
> Qwen3-Coder-30B-A3B and Qwen3-Coder-Next 80B-A3B. Vulkan improved
> Qwen3-Coder-Next generation by **23.5% in the published matched cell** and
> improved Qwen3-Coder-30B generation at 32K depth by **127–128%**. Dense
> Qwen3.8 was mixed in the synthetic test, but its real MTP requests completed
> **17–19% sooner**. I then
> compared v0.6.4 directly with the current v0.6.2 Vulkan package. The new
> release added **3–10%** to ordinary prompt-processing cells and **72.3%** to
> one Qwen3-Coder-Next large-prefill shape, while decode was effectively
> unchanged. All 54 measured API responses across both comparisons passed the
> output checks. This was a focused benchmark, not the final production soak.

The [last time I compared Vulkan and ROCm on this machine](/blog/2026/08/03/llamacpp-vulkan-vs-rocm-strix-halo/),
the answer split in two: ROCm was better at prompt processing, while Vulkan
could be better at generation. That was useful, but it did not give me a simple
backend policy.

The new Vulkan 0.6.4 build gave me a reason to repeat the work. Its release
notes describe wave32 and shared-memory changes for quantised dense matrix
multiplication, a faster transposed-concat path and corrected bulk reads from
write-combined mappings. The publisher measured **5–19% faster prefill than
Vulkan 0.6.2**, with decode unchanged.

That gave me two questions rather than one. First, how much had v0.6.4 actually
added over the Vulkan package I had already qualified? Second, was the result
now strong enough to move a route away from ROCm 7.14? I tested both instead of
using the release comparison as a proxy for my deployment.

## The comparisons I ran

The ROCm baseline was `llama.cpp` build 10387 at commit `401060ab7`, using
ROCm 7.14.60850. The Vulkan candidate was build 10565 at commit `baf6360be`,
packaged with Mesa 26.3.0-devel RADV, libdrm 2.4.134 and shaderc 2026.3-dev.
The candidate archive matched its published SHA-256 digest before I used it.

For the release comparison, the current baseline was Vulkan v0.6.2: build
10352 at commit `baf0025de`. The stale v0.2 package had already been superseded,
so using it would have exaggerated the apparent improvement. Both release
archives matched their published digests and used the same bundled RADV and
shader-compiler generation.

The model families came from the publisher repositories for
[Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B),
[Qwen3-Coder-30B-A3B-Instruct](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct)
and [Qwen3-Coder-Next](https://huggingface.co/Qwen/Qwen3-Coder-Next). The
backend comparisons held each GGUF file and quantisation constant, but the
published record does not contain the conversion repository, exact filename,
revision and SHA-256 digest for every file. That is enough to isolate the
backend change on this machine; it is not enough to reproduce the model
artefacts independently. A conversion-identical repeat needs a fresh manifest.

Both backends ran on the Radeon 8060S (`gfx1151`) with:

- the same model files and quantisation;
- all available layers offloaded;
- Flash Attention enabled;
- a 2,048-token batch;
- Q8_0 K and V caches;
- one server slot;
- the production-safe no-host loading mode for the matched test.

I left IOMMU enabled. Disabling it had already cost functionality on this
machine without producing enough performance to justify the trade, so I did
not smuggle that change into a backend comparison. I also made no thermal,
firmware or power-policy changes.

For the ROCm comparison, the main shallow matrix used three fresh launches per
backend in ABCCBA order, with three repetitions inside each launch. The 32K
and original Qwen3-Coder-Next runs used two launches per backend in ABBA order.

The release comparison added 30 fresh launches. Each model's shallow matrix
used the six-launch order `v0.6.2, v0.6.4, v0.6.4, v0.6.2, v0.6.2, v0.6.4`,
with three repetitions per cell. The 32K matrix used two launches per version
in ABBA order and two repetitions per cell. The tables report the median of
each launch's mean rather than the fastest run.

`pp` means prompt processing and `tg` means token generation. Both are measured
in tokens per second, so higher is better. Context depth is the number of
tokens already present before the measured operation.

## First: what v0.6.4 added over v0.6.2

The ordinary result agrees with the release notes: v0.6.4 is a prompt-processing
update. Dense Qwen3.8 gained **9–10%** on a shallow 2,048-token prompt and about
**3%** at 32K depth. Qwen3-Coder-30B gained **5–9%** on shallow prefill and
**1–2%** at 32K. Generation moved by less than 0.7% in every synthetic cell.

| Model and workload | Vulkan 0.6.2 | Vulkan 0.6.4 | v0.6.4 change |
| --- | ---: | ---: | ---: |
| Qwen3.8, pp2048, shallow, ubatch 256 | 292.64 | **319.49** | **+9.2%** |
| Qwen3.8, pp512 at 32K, ubatch 256 | 213.57 | **220.18** | **+3.1%** |
| Qwen3.8, tg128, shallow, ubatch 256 | 11.12 | 11.17 | +0.5% |
| Qwen3-Coder-30B, pp2048, shallow, ubatch 256 | 1,155.82 | **1,213.53** | **+5.0%** |
| Qwen3-Coder-30B, pp2048, shallow, ubatch 2048 | 1,448.58 | **1,575.02** | **+8.7%** |
| Qwen3-Coder-30B, tg128 at 32K, ubatch 256 | 50.08 | 50.28 | +0.4% |
| Qwen3-Coder-Next, pp2048, shallow, ubatch 256 | 665.43 | **683.59** | **+2.7%** |
| Qwen3-Coder-Next, pp2048, shallow, ubatch 2048 | 581.63 | **1,002.14** | **+72.3%** |
| Qwen3-Coder-Next, pp512 at 32K, ubatch 2048 | 537.10 | **550.20** | **+2.4%** |
| Qwen3-Coder-Next, tg128 at 32K, ubatch 256 | 48.45 | 48.61 | +0.3% |

The Qwen3-Coder-Next ubatch-2048 result is the exception and deserved a second
test. The three v0.6.2 launch means drifted from 751.64 to 581.63 and then
535.18 tokens per second, while the three v0.6.4 launches stayed close to
1,000. A separate ABBA confirmation with five repetitions per launch measured
591.19 against 1,034.60 tokens per second, a **75.0%** gain. I use the
counterbalanced main-matrix result of 72.3% in the table and treat it as a
shape-specific bottleneck removal, not a 72% speed-up for the whole model.

The same distinction held through the API. I ran two fresh servers per release
in ABBA order, with three measured requests for each code, prose and strict-JSON
case after warm-up.

| MTP workload | v0.6.2 prompt | v0.6.4 prompt | Prompt change | Generation change | Wall-time change |
| --- | ---: | ---: | ---: | ---: | ---: |
| 512-token code | 125.83 tok/s | **133.53 tok/s** | **+6.1%** | -1.0% | +0.7% |
| 512-token prose | 126.63 tok/s | **131.60 tok/s** | **+3.9%** | -0.8% | +0.7% |
| Strict JSON | 83.24 tok/s | **86.22 tok/s** | **+3.6%** | -1.2% | +0.9% |

The small negative decode and wall-time movements are not a useful regression
claim at this sample size. They say decode is unchanged, as the publisher
reported. These output-heavy requests spent most of their time generating, so
faster prompt processing did not shorten the complete request. Draft acceptance
and cached-token counts matched exactly between releases, and all 36 measured
responses passed.

The full [synthetic release comparison](/assets/data/strix-halo-vulkan-062-vulkan-064-2026-08-19.csv)
and [served MTP release comparison](/assets/data/strix-halo-vulkan-062-vulkan-064-mtp-2026-08-19.csv)
are available without the rounding used above.

This changes how I read the ROCm comparison. The large coding-model decode lead
is a Vulkan-stack advantage that was already present in v0.6.2. What v0.6.4
adds is better prompt processing and one substantial Qwen3-Coder-Next fix.

## Then: v0.6.4 against ROCm 7.14

| Model and workload | ROCm 7.14 | Vulkan 0.6.4 | Vulkan change |
| --- | ---: | ---: | ---: |
| Qwen3.8, pp2048, shallow, ubatch 256 | **366.87** | 318.96 | **-13.1%** |
| Qwen3.8, tg128, shallow, ubatch 256 | 11.04 | **11.17** | **+1.2%** |
| Qwen3.8, pp512 at 32K, ubatch 256 | 215.00 | **219.37** | **+2.0%** |
| Qwen3.8, tg128 at 32K, ubatch 256 | 9.56 | **10.54** | **+10.2%** |
| Qwen3-Coder-30B, pp2048, shallow, ubatch 256 | 863.73 | **1,212.98** | **+40.4%** |
| Qwen3-Coder-30B, tg128, shallow, ubatch 256 | 68.34 | **90.02** | **+31.7%** |
| Qwen3-Coder-30B, pp512 at 32K, ubatch 2048 | 363.45 | **442.15** | **+21.7%** |
| Qwen3-Coder-30B, tg128 at 32K, ubatch 2048 | 21.96 | **50.07** | **+128.0%** |
| Qwen3-Coder-Next, pp2048, shallow, ubatch 2048 | 699.12 | **997.95** | **+42.7%** |
| Qwen3-Coder-Next, tg128, shallow, ubatch 256 | 43.86 | **54.16** | **+23.5%** |

The [machine-readable result table](/assets/data/strix-halo-vulkan-064-rocm-714-2026-08-19.csv)
contains these figures and the served MTP measurements without the displayed
rounding.

## Qwen3-Coder-Next is the obvious first canary

In the two Qwen3-Coder-Next cells published in the ROCm comparison, Vulkan
improved prompt processing by **42.7%** and generation by **23.5%**. I have not
published the additional cells behind the earlier ranges, so I do not use them
to support the deployment decision here.

That is large enough to notice in a coding session and broad enough that it does
not depend on one carefully chosen cell. The follow-up release comparison also
filled a 32K context: v0.6.4 improved Coder-Next prefill by about 2.5% over
v0.6.2 there, while decode remained unchanged. I have not yet filled 64K or put
its tool calls through an extended soak. It is my first canary, not an automatic
production promotion.

## The 30B coder becomes much more interesting at depth

Qwen3-Coder-30B-A3B also favoured Vulkan for the normal interactive shapes. At
micro-batch 256, shallow prompt processing rose by about **40%** and generation
by about **32%**. At 32K depth, generation moved from roughly 22 to 50 tokens
per second. More than doubling decode at the point where a coding session has
accumulated useful history is the most consequential result in this test.

There was one exception I would keep visible in any deployment dashboard. For
a shallow 2,048-token prompt at micro-batch 2,048, ROCm reached 1,720.92
tokens per second against Vulkan's 1,587.06. Vulkan was **7.8% slower** for
that maximum-throughput prefill shape.

That does not reverse the route decision for an interactive coding model, but
it prevents the easier and less honest claim that Vulkan won everything.

## Dense Qwen3.8 needed a real request

The raw Qwen3.8 result was less flattering. ROCm remained **12–23% faster** for
shallow prompt ingestion, depending on micro-batch, and raw generation was
almost tied. A tuning sweep made micro-batch 256 the best prompt setting for
both backends. Letting Vulkan use automatic host-visible loading rather than
the matched no-host mode changed almost nothing.

At 32K depth Vulkan pulled narrowly ahead in prompt processing and reached a
10.2% generation lead. That still did not tell me what the production route
would feel like, because Qwen3.8 is served with its native MTP draft model.

I therefore ran the target and Q8_0 draft through the OpenAI-compatible API
with a 65,536-token server context, Q8_0 KV cache, prefix caching and one slot.
Each case ran three measured times after warm-up.

| Output workload | ROCm generation | Vulkan generation | ROCm wall time | Vulkan wall time |
| --- | ---: | ---: | ---: | ---: |
| 512-token code task | 21.82 tok/s | **26.60 tok/s** | 23.74s | **19.45s** |
| 512-token prose task | 16.05 tok/s | **19.18 tok/s** | 32.37s | **26.92s** |
| Strict JSON task | 24.39 tok/s | **30.00 tok/s** | 15.19s | **12.35s** |

Vulkan's uncached prompt phase was 6–10% slower, but generation was
**19–23% faster**, cutting the complete request time by **17–19%**. Draft
acceptance stayed close between the two backends, so the result was not created
by Vulkan receiving a much easier stream of draft tokens.

Prefix caching worked on both sides. The repeated code, prose and JSON requests
reported 62, 61 and 37 cached prompt tokens respectively. This matters because
a faster uncached demo would not compensate for a broken cache in the real
dispatcher.

## The output still had to be correct

All 18 API responses in the ROCm comparison and all 36 in the release
comparison passed their workload checks. The JSON responses parsed and
contained exactly the requested 12 records. I found no empty responses,
non-finite benchmark values, repeated-slash or question-mark corruption
signatures, backend errors or GPU faults in the retained logs.

The Vulkan release itself reports 33,055/33,055 backend-operation tests passing
and unchanged perplexity for its default-on matrix changes. That is useful
supporting evidence, but it is not a replacement for a deployment test. My API
run used one slot, so it does not qualify concurrent mixed-request isolation.

## What I would operate next

I would not replace ROCm globally. I would put Vulkan behind Lemonade on a
model-by-model basis, with no separately exposed inference port and with the
ROCm route left ready as the fallback.

My order is:

1. **Qwen3-Coder-Next first.** The 32K synthetic test now passes; add 64K,
   tool-call checks and a 30-minute single-slot soak. The measured performance
   case is already strong.
2. **Qwen3-Coder-30B-A3B second.** Optimise for the long-running coding session
   rather than the one shallow prefill shape where ROCm still wins.
3. **Qwen3.8 native MTP third.** Judge it by served completion time, where
   Vulkan won, while retaining ROCm for prompt-heavy non-speculative batch work.

The production gate is deliberately more boring than the benchmark: stable
memory, repeated cache hits, strict and malformed JSON, long outputs, restart
recovery and no response content crossing request boundaries. Each candidate
needs to pass that 30-minute soak before I change the default route.

Vulkan 0.6.4 has not made ROCm 7.14 obsolete. It has done something more useful:
it has made the coding MoE routes an evidence-backed deployment option. On this
machine, the right policy is now clearer than “keep both backends around”. Use
Vulkan where the model and request shape earn it, and keep ROCm for the cells it
still wins.

*Sources checked 19 August 2026: the [Strix Halo Vulkan v0.6.2
release](https://github.com/Nathanw1014/strix-halo-llamacpp/releases/tag/v0.6.2),
the [v0.6.4 release and its full validation
record](https://github.com/Nathanw1014/strix-halo-llamacpp/releases/tag/v0.6.4)
and the official [`llama.cpp` repository](https://github.com/ggml-org/llama.cpp),
plus the linked Qwen publisher repositories for model-family identification.
All Vulkan-release and ROCm comparison figures above come from retained
same-machine benchmark artefacts collected on 19 August 2026. The candidates
were installed side by side; the production Lemonade configuration was not
changed during either test.*
