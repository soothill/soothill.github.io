---
layout: post
title: "Vulkan 0.6.4 on Strix Halo: the coding models moved"
seo_title: "Vulkan 0.6.4 vs ROCm 7.14 on Strix Halo"
date: 2026-08-19 12:45:00 +0100
last_modified_at: 2026-08-19 12:45:00 +0100
permalink: /blog/2026/08/19/vulkan-064-rocm-714-strix-halo/
categories: [local-ai, benchmarks, engineering]
tags: [vulkan, rocm, llama-cpp, strix-halo, qwen3-coder, qwen3-8, mtp, lemonade]
author: Darren Soothill
series: "Local LLMs on Strix Halo"
series_order: 11
description: "I tested Vulkan 0.6.4 against ROCm 7.14 on three Qwen deployments. Coding MoEs gained up to 128% at 32K; dense Qwen remained workload-dependent in practice."
---

> **Test record:** I compared the Strix Halo Vulkan v0.6.4 release with my
> ROCm 7.14 `llama.cpp` build on the same 128GB GMKtec EVO-X3. The same GGUF
> files, Q8_0 KV cache and common launch settings were used for Qwen3.8-27B,
> Qwen3-Coder-30B-A3B and Qwen3-Coder-Next 80B-A3B. Vulkan improved
> Qwen3-Coder-Next generation by **22–23%** and improved Qwen3-Coder-30B
> generation at 32K depth by **127–128%**. Dense Qwen3.8 was mixed in the
> synthetic test, but its real MTP requests completed **17–19% sooner**. All
> 18 measured API responses passed the output checks. This was a focused
> benchmark, not the final production soak.

The [last time I compared Vulkan and ROCm on this machine](/blog/2026/08/03/llamacpp-vulkan-vs-rocm-strix-halo/),
the answer split in two: ROCm was better at prompt processing, while Vulkan
could be better at generation. That was useful, but it did not give me a simple
backend policy.

The new Vulkan 0.6.4 build gave me a reason to repeat the work. Its release
notes describe wave32 and shared-memory changes for quantised dense matrix
multiplication, a faster transposed-concat path and corrected bulk reads from
write-combined mappings. The publisher measured **5–19% faster prefill than
Vulkan 0.6.2**, with decode unchanged.

That is a sound release comparison. It is not the question I needed to answer.
My running alternative is ROCm 7.14, not Vulkan 0.6.2, and the models I care
about include coding mixtures of experts and native speculative decoding. I
wanted to know whether this build was now good enough to move an actual route.

## The comparison I ran

The ROCm baseline was `llama.cpp` build 10387 at commit `401060ab7`, using
ROCm 7.14.60850. The Vulkan candidate was build 10565 at commit `baf6360be`,
packaged with Mesa 26.3.0-devel RADV, libdrm 2.4.134 and shaderc 2026.3-dev.
The candidate archive matched its published SHA-256 digest before I used it.

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

For the main shallow matrix I used three fresh launches per backend in ABCCBA
order, with three repetitions inside each launch. The 32K-depth and
Qwen3-Coder-Next runs used two launches per backend in ABBA order, with two
repetitions inside each launch. The table reports the median of each launch's
mean rather than selecting the fastest run.

`pp` means prompt processing and `tg` means token generation. Both are measured
in tokens per second, so higher is better. Context depth is the number of
tokens already present before the measured operation.

## The result was model-specific again, but less ambiguous

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

Vulkan won every Qwen3-Coder-Next cell I tested. Across the two micro-batch
sizes, prompt processing improved by **37.7–42.7%** and generation improved by
**22.2–23.5%**.

That is large enough to notice in a coding session and broad enough that it does
not depend on one carefully chosen cell. This run only covered the shallow
performance matrix, however. I have not yet filled a 32K or 64K context for
this model on the candidate build, nor put its tool calls through an extended
soak. It is my first canary, not an automatic production promotion.

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

## I checked the output, not just the rate

All 18 measured API responses passed their workload checks. The JSON responses
parsed and contained exactly the requested 12 records. I found no empty
responses, non-finite benchmark values, repeated-slash or question-mark
corruption signatures, or backend errors in the retained logs.

The Vulkan release itself reports 33,055/33,055 backend-operation tests passing
and unchanged perplexity for its default-on matrix changes. That is useful
supporting evidence, but it is not a replacement for a deployment test. My API
run used one slot, so it does not qualify concurrent mixed-request isolation.

## What I would operate next

I would not replace ROCm globally. I would put Vulkan behind Lemonade on a
model-by-model basis, with no separately exposed inference port and with the
ROCm route left ready as the fallback.

My order is:

1. **Qwen3-Coder-Next first.** Add 32K and 64K context tests, tool-call checks
   and a 30-minute single-slot soak. The measured performance case is already
   strong.
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

*Sources checked 19 August 2026: the [Strix Halo Vulkan v0.6.4 release and its
full validation record](https://github.com/Nathanw1014/strix-halo-llamacpp/releases/tag/v0.6.4)
and the official [`llama.cpp` repository](https://github.com/ggml-org/llama.cpp).
All ROCm-versus-Vulkan figures above come from retained same-machine benchmark
artefacts collected on 19 August 2026. The candidate was installed side by side;
the production Lemonade configuration was not changed during this test.*
