---
layout: post
title: "SGLang vs vLLM vs llama.cpp on Strix Halo: five models, three winners"
seo_title: "SGLang vs vLLM: Strix Halo benchmarks"
date: 2026-08-10 08:00:00 +0100
last_modified_at: 2026-08-10 08:00:00 +0100
permalink: /blog/2026/08/10/sglang-vllm-llamacpp-evox3/
categories: [local-ai, benchmarks, engineering]
tags: [sglang, vllm, llama-cpp, rocm, strix-halo, qwen3, qwen35, deepseek-v4, prefix-caching]
author: Darren Soothill
editorial_standard: soothill-human-v1
editorial_review_status: approved
editorial_reviewer: Darren Soothill
editorial_reviewed_at: 2026-08-17
series: "Local LLMs on Strix Halo"
series_order: 9
description: "Twenty matched SGLang-vLLM points plus llama.cpp and DeepSeek tests show why vLLM wins native Qwen while specialised runtimes win large quants."
---

> **Test record:** I compared the newest releases available on 10 August 2026—[SGLang 0.5.17](https://github.com/sgl-project/sglang/releases/tag/v0.5.17), [vLLM 0.26.0](https://github.com/vllm-project/vllm/releases/tag/v0.26.0) and [llama.cpp b10333](https://github.com/ggml-org/llama.cpp/releases/tag/b10333)—on a 128GB GMKtec EVO-X3 with a Ryzen AI MAX+ 395 / Radeon 8060S (`gfx1151`). I then made a deliberate search for a workload where SGLang could beat vLLM: dense Qwen3-8B, Qwen3-Coder-30B-A3B MoE, and a shared-prefix cache test from one to sixteen clients. Across **14 new comparison points and 1,540 measured API requests, vLLM won every point**; both engines completed every request. The wider study still has three deployment winners: custom vLLM reached **311.59 completion tok/s** on Qwen3.5-0.8B, llama.cpp reached **13.57 tok/s at one client and 17.88 at two** on Qwen3.5-122B-A10B, and the specialised DeepSeek V4 Flash service retained a qualified **23.70 tok/s**. SGLang's patched and tuned WNA16 lane is a working 122B fallback at **7.75 / 13.48 tok/s**, but it did not win on throughput.

There is no single fastest LLM server on Strix Halo.

That is not an attempt to avoid a verdict. The verdict changes with model size, quantisation and workload:

| Workload | What I would run | Why |
|---|---|---|
| Small Qwen, one to eight clients | custom vLLM 0.26.0 / ROCm 7.14 | fastest completion throughput and lowest TTFT at every tested concurrency |
| Qwen3-8B BF16, unique or shared-prefix prompts | custom vLLM 0.26.0 / ROCm 7.14 | SGLang trailed vLLM by 36–47% across C=1 to C=16, even when both prefix caches worked |
| Qwen3-Coder-30B-A3B BF16 MoE | custom vLLM 0.26.0 / ROCm 7.14 | SGLang trailed vLLM by 51–69% across C=1 to C=8; both engines used untuned default Triton MoE profiles |
| Qwen3.5-122B-A10B, one interactive client | custom llama.cpp b10333 / ROCm 7.14 / HIP graphs off | 13.57 completion tok/s and 4.72s mean end-to-end |
| Qwen3.5-122B-A10B, two simultaneous clients | official llama.cpp b10333 binary | 17.88 aggregate completion tok/s; slightly ahead of the custom build |
| DeepSeek V4 Flash in production | specialised Lucebox ROCmFP3 service / ROCm 7.14 | 23.70 tok/s qualified target-only decode; the quant and kernels are purpose-built |
| DeepSeek V4 Flash through a general GGUF server | patched Vulkan llama.cpp | 18.90 tok/s shallow and 16.30 tok/s deep generation |

The more interesting conclusion is what **does not** appear in the table: “compile everything with the newest ROCm” is not a useful deployment policy. ROCm 7.14 materially helped small-model vLLM, made a current SGLang experiment possible, did almost nothing for 122B vLLM, and produced mixed llama.cpp results.

## What “latest” meant in this test

Version comparisons age quickly, so I pinned the boundary explicitly:

| Component | Tested release | Exact identity |
|---|---|---|
| SGLang | 0.5.17 | `29481685462732237d80d86076d6563e1f658102` |
| vLLM | 0.26.0 | `568afb3a13806beb53bb2e6bd518269357b237c0` |
| llama.cpp | b10333 | `08659901c43b51de735740f1cf61bb82fbe0c4e4` |
| custom toolchain | ROCm 7.14.0 | HIP `7.14.60850` |

[ROCm 7.14's release notes](https://rocm.docs.amd.com/en/docs-7.14.0/about/release-notes.html) matter here because “ROCm supports `gfx1151`” and “this engine release ships a supported `gfx1151` build” are different claims. AMD validates vLLM on `gfx1151` in the 7.14 ecosystem, but its framework table pins an older vLLM than 0.26; the [vLLM 0.26 installation guide](https://docs.vllm.ai/en/v0.26.0/getting_started/installation/gpu.html) separately lists Ryzen AI MAX support. SGLang's validated 7.14 GPU list excludes `gfx1151`, and [SGLang 0.5.17's ROCm AOT builder](https://github.com/sgl-project/sglang/blob/v0.5.17/python/sglang/kernels/aot/setup_rocm.py) accepts only `gfx942` and `gfx950` without a source change.

The stock lanes therefore differed by project:

- vLLM used its official 0.26.0 ROCm wheel environment with ROCm 7.2.3 user-space libraries, then the same vLLM tag rebuilt from source against ROCm 7.14.
- llama.cpp used the official b10333 “Ubuntu x64 ROCm 7.2” asset, then the same revision compiled by ROCm 7.14 specifically for `gfx1151`. The official binary resolved ROCm shared libraries from the host's `/opt/rocm-7.14.0`; “7.2” describes its published build toolchain, not a second kernel driver.
- SGLang had no runnable stock 0.5.17 `gfx1151` lane. I report that as unavailable, not as zero throughput. Its only working lane was a patched source build against ROCm 7.14.

This distinction prevents a common benchmark sleight of hand: a failed install is a support result, but it is not a performance sample.

## The common benchmark

The small-model comparison is the clean engine test. SGLang and vLLM loaded the exact [Qwen3.5-0.8B](https://huggingface.co/Qwen/Qwen3.5-0.8B) snapshot at revision `2fc06364715b967f1860aea9cf38778875588b17`. llama.cpp loaded a lossless BF16 GGUF conversion of the same files, with SHA-256 `eb4e637d…04c3d0d`.

Every request used the same deterministic 480-word prompt generator, roughly 598–638 model tokens, followed by 64 requested output tokens at temperature zero and seed 12345. Each concurrency had two discarded warm-up waves and ten measured waves. vLLM prefix caching and SGLang's radix cache were disabled. llama.cpp retained its slot prompt cache, but every generated passage was unique, limiting reuse to the short common boilerplate. The API limit was 4,096 tokens, and one common OpenAI-compatible streaming client measured TTFT, end-to-end latency and completion throughput.

“Completion tok/s” below is completed output tokens divided by the full measured wave time. It includes prompt ingestion and scheduling. It is deliberately not the larger decode-only rate printed by a server after a request has finished.

For the 122B test, the API workload remained identical but the formats could not. vLLM and SGLang used Qwen's official [GPTQ-Int4 checkpoint](https://huggingface.co/Qwen/Qwen3.5-122B-A10B-GPTQ-Int4); llama.cpp used [Unsloth's UD-Q4_K_XL GGUF](https://huggingface.co/unsloth/Qwen3.5-122B-A10B-GGUF). That is a comparison of deployable serving solutions, not a pure engine A/B. Quantisation can change both quality and performance, so I do not attribute the whole gap to the server.

## Small Qwen: vLLM wins cleanly

| Engine and build | C=1 | C=2 | C=4 | C=8 |
|---|---:|---:|---:|---:|
| SGLang 0.5.17, custom ROCm 7.14, graphs disabled | 58.23 | 107.02 | 173.62 | 250.32 |
| SGLang 0.5.17, custom ROCm 7.14, decode graphs | 57.25 | 105.48 | 171.48 | 248.43 |
| vLLM 0.26.0, official ROCm 7.2.3 userspace | 81.93 | 143.40 | 231.42 | 291.75 |
| **vLLM 0.26.0, custom ROCm 7.14** | **86.59** | **152.48** | **246.53** | **311.59** |
| llama.cpp b10333, official build | 81.04 | 111.00 | 133.41 | 213.79 |
| llama.cpp b10333, custom ROCm 7.14, HIP graphs on | 81.35 | 110.84 | 137.05 | 203.05 |
| llama.cpp b10333, custom ROCm 7.14, HIP graphs off | 81.74 | 111.61 | 138.04 | 207.09 |

All values are aggregate completion tokens per second; all measured requests succeeded.

The ROCm 7.14 vLLM build improved on the official wheel by **5.7%, 6.3%, 6.5% and 6.8%** as concurrency rose from one to eight. Its one-client mean TTFT was also the best at 53.2ms, versus 54.6ms for the official vLLM wheel, 79.7ms for SGLang and roughly 117ms for llama.cpp.

llama.cpp matched official vLLM surprisingly closely at one client—81.04 versus 81.93 tok/s—but did not scale with the server-oriented engines. At eight clients, official vLLM was 36.5% ahead of official llama.cpp; the custom vLLM build extended that to 45.7%.

SGLang scaled much better than its single-client number suggests: C=8 throughput was 4.30 times C=1. Full decode graphs also captured and replayed successfully on the custom port, but made completion throughput **0.7–1.7% slower** across the matrix. I retained the graph-disabled row rather than assuming a normally useful server optimisation must help. SGLang still finished behind vLLM at every point. On this APU, reaching that result required more compatibility work than performance tuning, which changes the practical judgement even if the gap later closes.

The llama.cpp graph experiment is a useful warning against generic tuning advice. Disabling HIP graphs made the custom build 0.5–0.7% faster at C=1 and C=2 and 0.7% faster at C=4, but recovered only part of its C=8 loss. The official binary remained faster at C=8. I would keep the simpler official build for this small model unless I needed a source patch for another reason.

## I tried to find an SGLang win

The Qwen3.5 results left a fair question: was SGLang merely losing on those
particular model shapes, or was the gap broader on this APU? I added two
official BF16 checkpoints that exercise different paths:

- dense [Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B/tree/b968826d9c46dd6066d109eabc6255188de91218), pinned at revision `b968826d9c46dd6066d109eabc6255188de91218`;
- [Qwen3-Coder-30B-A3B-Instruct](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct/tree/b2cff646eb4bb1d68355c01b18ae02e7cf42d120), pinned at revision `b2cff646eb4bb1d68355c01b18ae02e7cf42d120`, with 128 experts and eight active experts per token.

Both engines used the same downloaded files, BF16 weights, 4,096-token API
limit, deterministic prompt stream and OpenAI-compatible client. Prefix
caching was disabled for the first pass. SGLang used Triton attention,
PyTorch sampling, the Triton MoE runner and graph-disabled execution; vLLM
used ROCm attention and successful full-decode graph capture at the measured
batch sizes. These are the retained configurations for each engine, not an
artificial graph-off tie.

### Dense Qwen3-8B

| Engine | C=1 | C=2 | C=4 | C=8 | C=16 |
|---|---:|---:|---:|---:|---:|
| SGLang 0.5.17 / ROCm 7.14 | 7.08 | 13.52 | 24.52 | 40.44 | 59.46 |
| **vLLM 0.26.0 / ROCm 7.14** | **13.28** | **24.93** | **42.49** | **64.04** | **93.24** |

SGLang finished **36.2–46.7% behind vLLM**. It did scale—its aggregate
completion rate grew 8.4 times from one to sixteen clients—but its p50
inter-token interval remained 132–146ms. vLLM's was 70–90ms. At one client,
mean TTFT was 708ms for SGLang and 352ms for vLLM; mean end-to-end latency was
9.04s and 4.82s respectively. The deficit narrowed with concurrency, but it
never approached a crossover.

The absolute throughput is much lower than the 0.8B table above because this
is an 8B model executing 64-token completions after roughly 630 input tokens.
The comparison is internal to each row, not a claim that the two model sizes
should produce similar rates.

### Qwen3-Coder-30B-A3B: MoE did not reverse it

| Engine | C=1 | C=2 | C=4 | C=8 |
|---|---:|---:|---:|---:|
| SGLang 0.5.17 / ROCm 7.14 | 7.90 | 13.67 | 22.26 | 34.56 |
| **vLLM 0.26.0 / ROCm 7.14** | **25.73** | **35.09** | **45.50** | **77.41** |

This was the strongest rejection of the “right model will fix it” hypothesis.
SGLang finished **51.1–69.3% behind vLLM**. Its p50 inter-token interval ranged
from 115ms at C=1 to 190ms at C=8; vLLM ranged from 34ms to 79ms. At one
client, the first-token difference was 527ms, while complete-request latency
differed by 5.61s. Most of the loss accumulated during decode.

Both server logs exposed the same missing optimisation. Neither project ships
a Radeon 8060S Triton MoE profile for `E=128, N=768`; both warned that they
were using a default configuration. That makes a new SGLang profile a valid
next experiment, but not a sufficient explanation for this result: vLLM used
an untuned profile too and was still more than three times as fast at C=1.
The earlier WNA16 work provides a useful bound—shape tuning improved SGLang by
7–9%, while SGLang's BF16 MoE shortfall relative to vLLM was 51–69%.

### Shared prefixes: both caches work, vLLM still wins

SGLang is well known for radix-prefix reuse, so I added the workload most
likely to favour it. Every prompt contained a common 400-word prefix followed
by an 80-word unique suffix. After the first request, SGLang reported roughly
520 cached tokens and only 107–114 new tokens per request. vLLM's automatic
prefix-cache hit rate climbed to roughly 79%. Both caches were therefore doing
real work.

| Engine | C=1 | C=2 | C=4 | C=8 | C=16 |
|---|---:|---:|---:|---:|---:|
| SGLang 0.5.17, RadixCache | 7.37 | 14.82 | 29.05 | 54.94 | 98.73 |
| **vLLM 0.26.0, automatic prefix cache** | **13.88** | **27.42** | **50.43** | **87.37** | **153.40** |

Caching helped both engines almost identically:

| Concurrency | SGLang throughput gain | vLLM throughput gain | SGLang TTFT reduction | vLLM TTFT reduction |
|---:|---:|---:|---:|---:|
| 1 | 4.1% | 4.5% | 50.5% | 59.2% |
| 2 | 9.6% | 10.0% | 61.8% | 59.1% |
| 4 | 18.5% | 18.7% | 71.9% | 65.5% |
| 8 | 35.9% | 36.4% | 77.1% | 74.3% |
| 16 | 66.1% | 64.5% | 79.5% | 74.8% |

SGLang's largest result, 98.73 tok/s at C=16, was 66.1% above its own
cache-disabled baseline. vLLM improved by 64.5% to 153.40 tok/s, while SGLang
remained 35.6% behind it. The experiment validates SGLang's cache; it does not turn cache
reuse into an engine win.

Across these three added matrices, all **1,540 measured requests** completed
successfully. There was no GPU reset, timeout or fault in the captured kernel
log, and each runner restored the production Lemonade model. The result is
not “SGLang cannot run Qwen.” It can run dense BF16, unquantised MoE BF16 and
patched WNA16 on `gfx1151`. The result is that none of the tested model or
cache cases made it faster than this vLLM build.

### What could still improve SGLang

The evidence points to three bounded follow-ups rather than another round of
generic flag changes:

1. Generate and retain `E=128,N=768` up/down Triton profiles for the Radeon
   8060S, then repeat the Coder matrix. This removes a documented fallback but
   is unlikely by itself to close SGLang's 51–69% shortfall relative to vLLM.
2. Target decode kernels. Dense Qwen3-8B remained roughly 1.6–1.9 times slower
   per output-token interval, and the MoE model was roughly 2.4–3.4 times
   slower. Prefix reuse cut TTFT without changing that relationship.
3. Run a model-specific SGLang graph A/B for Qwen3-Coder. Graphs were slightly
   negative on Qwen3.5-0.8B and on the 122B WNA16 path, so enabling them by
   assumption would not be evidence; the MoE shape deserves its own control.

The practical answer today remains vLLM for native Qwen serving on this
machine. SGLang is a tested experimental option where its API or scheduling
features are the requirement, not the throughput choice.

## Large Qwen: llama.cpp wins throughput, vLLM wins first token

| Engine and build | Format | C=1 | C=2 |
|---|---|---:|---:|
| vLLM 0.26.0, official | GPTQ-Int4 | 10.335 | 16.161 |
| vLLM 0.26.0, custom ROCm 7.14, retuned mean | GPTQ-Int4 | 10.329 | 16.179 |
| llama.cpp b10333, official | UD-Q4_K_XL | 13.369 | **17.878** |
| llama.cpp b10333, custom ROCm 7.14, HIP graphs off | UD-Q4_K_XL | **13.573** | 17.562 |
| SGLang 0.5.17, custom ROCm 7.14, tuned `moe_wna16` | GPTQ-Int4 | 7.751 | 13.483 |

At one client, the custom llama.cpp build completed the workload at 13.57 tok/s, **31.3% above** official vLLM. At two clients, the official llama.cpp artefact was fastest at 17.88 aggregate tok/s, **10.5% above** the retuned ROCm 7.14 vLLM mean.

The latency shape is more nuanced. Official vLLM delivered the first token in 1.056s on average, while custom llama.cpp needed 1.775s. llama.cpp then decoded fast enough to finish the complete 64-token request in 4.715s, versus 6.192s for vLLM. If the interface prizes immediate acknowledgement more than time to complete, vLLM retains an advantage. If “fastest” means finishing the response, llama.cpp wins this test.

ROCm 7.14 changed neither incumbent large-model performance answer:

- vLLM's retuned ROCm 7.14 mean was effectively flat: 10.329 versus 10.335 tok/s at C=1, and 16.179 versus 16.161 at C=2.
- custom llama.cpp improved C=1 by 1.5%, then lost 1.8% at C=2. Those are small, opposing changes rather than a new performance tier.

SGLang's WNA16 path is now a working option, but it is the slowest of the
three serving lanes here. The stock Triton fallback delivered 7.253 and
12.332 tok/s; adding the missing Radeon 8060S MoE records raised those figures
by 6.9% and 9.3% to 7.751 and 13.483 tok/s. Tuned SGLang delivered 75.0% of
official vLLM's completion throughput at C=1 and 83.4% at C=2. Mean time to
first token was 1.252s and 2.036s respectively; mean end-to-end latency was
8.257s and 9.493s. The stability gate returned exactly `PARIS` in 20
consecutive deterministic chat requests, followed by a 100% success rate
across all 30 measured benchmark requests.

The most honest deployment rule is therefore specific: use the custom llama.cpp build for a single interactive 122B session, but do not replace the official build for a two-client service on the strength of the newer compiler.

## How SGLang's 122B WNA16 path was made to work

SGLang's [AMD quantisation documentation](https://docs.sglang.io/docs/hardware-platforms/amd_gpu#quantization-on-amd-gpus) says plain GPTQ works on AMD and `gptq_marlin` does not. Qwen3.5-122B-A10B exposes an awkward boundary between those two statements.

With automatic selection, SGLang chose `gptq_marlin` and stopped because Marlin is unsupported on ROCm. I then forced `--quantization gptq --dtype float16`. Model construction began, but its MoE layer stopped with:

```text
TypeError: GPTQ Method does not support MoE, please use gptq_marlin
```

Those two failures are real, but they are not the end of SGLang's W4A16
support. Version 0.5.17 also contains `MoeWNA16Method`, which accepts this
checkpoint's four-bit, group-size-128, activation-order-disabled layout and
runs its expert GEMMs through Triton. SGLang's ROCm validation allow-list did
not include that method, so I added a one-line `moe_wna16` entry and selected
it explicitly.

The model then loaded all 39 shards and allocated 64.62GB for weights, but
the first request exposed a second `gfx1151` boundary: SGLang's packaged AOT
`topk_softmax` router kernel failed with an unspecified launch error. The
retained opt-in patch uses SGLang's own PyTorch-native top-k fallback for the
router only. The quantised expert path remains the Triton WNA16 runner. That
combination survived the correctness and performance matrix without a
request failure, so the support result is now “works with two narrow source
patches,” not “no load.”

The first successful server log also identified a performance fault directly:
SGLang had no `gfx1151` Triton MoE configuration for either the up/gate or down
projection and warned that its default might be sub-optimal. I added retained
M=1, M=2 and prefill records for both shapes. That improved end-to-end latency
by 6.4% at C=1 and 8.5% at C=2. Full decode graphs at batch sizes one and two
were a negative control: they reduced throughput by 0.55% and 0.26%, so the
launch remains graph-disabled.

Most of the remaining vLLM gap is decode. At C=1, roughly 90% of the original
end-to-end difference accumulated after the first token, and SGLang's p50
inter-token interval was 119.64ms versus vLLM's 81.34ms. The source paths
match that result: SGLang's non-expert GPTQ projections still use its generic
`gptq_gemm`, while vLLM 0.26 has a `gfx1151`-tuned hybrid W4A16 backend with a
HIP skinny GEMM for decode batches up to five. Closing the rest requires a
comparable RDNA linear kernel in SGLang, not another graph or scheduler flag.

This still shows why a broad “GPTQ supported” tick is insufficient for a
particular model architecture. Automatic GPTQ selection remains wrong for
this ROCm MoE checkpoint; the working command must name `moe_wna16`.

## DeepSeek V4 Flash: specialised kernels beat general servers

DeepSeek is a separate comparison because the useful 128GB deployment is a custom quant. The production file is a roughly 102GB ROCmFP3-MIX GGUF with model-specific H32 rotations, sparse indexer work and fused expert kernels. SGLang's AMD documentation explicitly lists GGUF among unsupported methods; neither SGLang nor the [current vLLM GGUF plugin](https://github.com/vllm-project/vllm-gguf-plugin) provides the local ROCmFP3 implementation. They cannot consume the artefact that makes the model fit and run well here.

The general-server comparison is therefore inside llama.cpp:

| DeepSeek V4 Flash test | tuned ROCm 7.14 llama.cpp | patched Vulkan llama.cpp | Vulkan advantage |
|---|---:|---:|---:|
| shallow pp2048 | 207.87 ± 0.54 | **231.84 ± 0.55** | 11.5% |
| shallow tg64 | 14.79 ± 0.46 | **18.90 ± 0.03** | 27.8% |
| depth 24,576 pp2048 | 112.01 ± 0.68 | **131.47 ± 0.33** | 17.4% |
| depth 24,576 tg64 | 11.02 ± 0.76 | **16.30 ± 0.01** | 47.9% |

The Vulkan build includes the `LIGHTNING_INDEXER` fix needed to avoid the pathological fallback for this model. Both sides use a 2,048 micro-batch and no memory mapping. The matched details and stability evidence are in my [DeepSeek Vulkan-versus-ROCm test](/blog/2026/08/09/deepseek-v4-flash-vulkan-rocm-strix-halo/).

The specialised ROCm 7.14 Lucebox service remains faster for production. Five measured target-only 2,048-prompt / 510-output requests produced a **23.70 tok/s median** with a 23.70–23.80 range. That is not directly interchangeable with the llama.cpp `tg64` test—it uses another quant, another request length and purpose-built kernels—but it answers the operational question: the fastest qualified way I have to run the production DeepSeek artefact is the specialised service.

There is a 28.70 tok/s DSpark result in the retained experimental stack. I do not use it as the default recommendation because that publication-shaped profile used approximate sparse prefill and four routed experts rather than the exact six-expert production policy. A high number with a weaker quality boundary is a laboratory ceiling, not a deployment decision.

## The tuning philosophy is different for each engine

### SGLang: make the platform exist first

The working SGLang 0.5.17 environment is a real ROCm 7.14 source port, not a pip install with one environment variable:

1. Add `gfx1151` to the ROCm AOT target list and use a conservative 48KB dynamic shared-memory allowance.
2. Disable AITER and guard three unconditional Quark/MoE AITER imports so unrelated BF16 and GPTQ code can import.
3. Add the existing `moe_wna16` method to the ROCm allow-list and select it explicitly for Qwen3.5-122B-A10B.
4. Opt into PyTorch-native MoE routing on `gfx1151`; the expert WNA16 computation still runs through Triton.
5. Supply the retained Radeon 8060S Triton MoE profiles; the stock tree has no matching up/down records.
6. Override `compressed-tensors` 0.15 with 0.16 because the release pin excludes the ROCm 7.14 PyTorch 2.11 environment.
7. Put the isolated runtime's `bin` directory on `PATH` so Ninja JIT builds work.
8. Do not install the SDK `amdsmi` Python package in this environment: on this APU it made Torch report zero devices even while HIP remained available.

For the measured small-model runs I used Triton attention, PyTorch sampling, eight running requests and disabled radix caching so repeated unique prompts did not gain from cache state. I tested full decode graphs at capture sizes 1, 2, 4 and 8, then retained the faster graph-disabled configuration. This is maintainable as a benchmark experiment. It is not yet the engine I would ask to own this workstation.

### vLLM: scheduler and W4A16 kernels matter

vLLM 0.26 is the cleanest native serving stack here. The small model used BF16, eight sequences, an 8,192-token batching ceiling and full-decode graphs captured at batch sizes 1, 2, 4 and 8.

The 122B GPTQ path uses vLLM's [`gfx1151` HybridW4A16 work](https://github.com/vllm-project/vllm/pull/40977). I separately retuned the actual MoE shapes under ROCm 7.14. One M=616 Triton microkernel improved by 7.77%, but the end-to-end server stayed flat. The lesson is familiar but worth publishing: a hot kernel can win in isolation without moving a model dominated by hundreds of other launches, scheduling and memory traffic.

The ROCm 7.14 source runtime also needs a dedicated environment, AMD's modular PyTorch/Triton wheels, a build-pin workaround, controlled library ordering and an initialisation entry point that brings up AMD SMI and HIP before vLLM. That work buys 6–7% on the 0.8B model and essentially nothing on the 122B GPTQ model. I keep both facts, not an average of them.

### llama.cpp: format and memory controls are the advantage

llama.cpp exposes the knobs that matter most on a unified-memory APU. The custom build targets `gfx1151`, enables `GGML_HIP_NO_VMM` and `GGML_HIP_MMQ_MFMA`, and tests HIP graphs both on and off. The 122B server uses:

```text
--ctx-size 8192 --parallel 2
--batch-size 2048 --ubatch-size 2048
--n-gpu-layers 99 --flash-attn on
--cache-type-k f16 --cache-type-v f16
--no-mmap --fit off --no-context-shift
```

`--no-mmap` is important at this size: a 73GB model mapping plus GPU-visible allocations can make the Linux page cache compete with the same 128GB unified-memory budget. `--fit off` prevents automatic retuning from silently changing the comparison. Context is divided deliberately across two slots rather than assuming that `--ctx-size` applies independently to each client.

For DeepSeek, backend selection becomes another tuning dimension. ROCm prefers a 2,048 micro-batch for prompt processing; patched Vulkan remains much faster in quantised decode. llama.cpp is not the universal fastest engine, but it is the most adaptable one in this comparison.

## Does a custom ROCm 7.14 deployment pay for itself?

| Engine / model | ROCm 7.14 outcome | Keep it? |
|---|---|---|
| vLLM / Qwen 0.8B BF16 | +5.7% to +6.8% throughput | yes, if small-model throughput matters |
| vLLM / Qwen 122B GPTQ | -0.2% at C=1, +0.4% at C=2 versus fresh control | no; retain the official wheel |
| llama.cpp / Qwen 0.8B BF16 | roughly flat at low concurrency, 3.1% behind official at C=8 even with graphs off | no |
| llama.cpp / Qwen 122B Q4_K_XL | +1.5% at C=1, -1.8% at C=2 | only for the single-client profile |
| SGLang / Qwen 0.8B BF16 | converts “no stock gfx1151 lane” into a working server | experimental value, high maintenance |
| SGLang / Qwen 122B GPTQ WNA16 | converts two stock GPTQ failures into a tuned 7.75 / 13.48 tok/s working lane | viable fallback, slower and patch-dependent |
| Lucebox / DeepSeek V4 Flash | specialised ROCmFP3 kernels enable the best qualified production decode | yes, but kernel work—not the version number—is the reason |

The right abstraction is not “ROCm 7.14 is faster”. It is “ROCm 7.14 is a toolchain with model- and kernel-specific consequences”. The custom build is justified only when the measured workload pays back its maintenance surface.

## Final deployment choices

For a native Qwen model, I would run **vLLM 0.26 built against ROCm 7.14**.
It won every matched SGLang comparison: Qwen3.5-0.8B, dense Qwen3-8B,
Qwen3-Coder-30B-A3B MoE and the Qwen3-8B shared-prefix workload. That is 20
direct concurrency points with no SGLang throughput win. If installation
simplicity matters more than the 6–7% uplift measured on the smallest model,
the official vLLM wheel is the sensible fallback.

For Qwen3.5-122B-A10B, I would run **llama.cpp b10333 with UD-Q4_K_XL**. The `gfx1151` ROCm 7.14 build with HIP graphs off is the one-client winner. For a persistent two-client endpoint, the official b10333 build is fractionally faster and substantially easier to maintain. If official Qwen GPTQ weights, earlier TTFT or vLLM's production serving features matter more than final completion time, vLLM remains the better product choice despite lower throughput. SGLang WNA16 is now a tested fallback when SGLang-specific serving features matter, but its lower throughput and two extra compatibility patches keep it out of the default recommendation.

For DeepSeek V4 Flash, I would run the **specialised Lucebox ROCmFP3 service** already integrated behind Lemonade. For a general GGUF path, I would use the patched Vulkan llama.cpp build. SGLang and vLLM are excluded by artefact and kernel support before performance enters the discussion.

The winning stack on this machine is therefore deliberately plural: vLLM for small native models, llama.cpp for large GGUF models, and a specialised backend for a specialised DeepSeek quant. A single-server policy would be simpler. It would also leave measurable performance on the table.

The complete Qwen result table is available as [CSV](/assets/data/evox3-engine-comparison-2026-08-10.csv), and the added per-concurrency SGLang/vLLM comparisons—including latency and exact source-result paths—are available as [JSON](/assets/data/evox3-sglang-vllm-model-evaluation-2026-08-10.json). Every fresh benchmark runner restored the model it found on entry; after the final run, Lemonade again reported `DeepSeek-V4-Flash-0731-ROCmFP3-MIX` healthy and ready.

*Benchmark dates: 6–10 August 2026. Qwen API figures use two warm-up waves and ten measured waves at each concurrency. The shared-prefix case uses a 400-word common prefix plus an 80-word unique suffix with both engines' caches enabled; the other API matrices use unique prompts and disabled caches. DeepSeek figures use the separately documented retained protocols. No engine failure is represented as zero throughput, and unlike quantisations are labelled rather than averaged.*
