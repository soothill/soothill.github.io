---
layout: post
title: "llama.cpp on Strix Halo: Vulkan versus ROCm"
seo_title: "llama.cpp: Vulkan vs ROCm on Strix Halo"
date: 2026-08-03 10:00:00 +0100
last_modified_at: 2026-08-03 18:00:00 +0100
permalink: /blog/2026/08/03/llamacpp-vulkan-vs-rocm-strix-halo/
categories: [local-ai, benchmarks, software]
tags: [llama-cpp, vulkan, rocm, strix-halo, qwen3-coder, qwen3-5]
author: Darren Soothill
series: "Local LLMs on Strix Halo"
series_order: 3
description: "Matched llama.cpp benchmarks show why Strix Halo has no single fastest backend: ROCm wins prompt processing while Vulkan can win generation."
---

> **Test record:** the primary comparison uses the same EVO-X3, model, context, batch settings and benchmark protocol. The ROCm result is 50 repetitions; the Vulkan control is a five-run result from the same host. Backend revisions differ and are recorded, so the comparison describes these tested builds rather than an eternal property of the APIs.

The previous article established a [working, recoverable ROCm path](/blog/2026/08/03/rocm-on-strix-halo-without-folklore/). The obvious next question sounds simple: is ROCm faster than Vulkan?

It is the wrong shape of question.

An LLM request has at least two materially different phases. Prompt processing evaluates the input in parallel; token generation repeatedly decodes the next token and is usually more constrained by memory traffic and small-kernel efficiency. A backend can dominate the first and lose the second. A single blended score hides the product decision.

That distinction is particularly important for a Director of Product. Backend choice is not a leaderboard exercise. It changes time to first token, sustained reading speed, concurrency, operational risk and the class of interaction that feels responsive. I want the fastest path for the workload, not the most comforting label.

## The matched Qwen3-Coder test

The primary model is `Qwen3-Coder-30B-A3B-Instruct-Q4_K_S`, a 17.46GB GGUF containing 30.53 billion parameters. It is a mixture-of-experts model, so only a subset of those parameters is active for each token.

Both backends used:

```text
prompt tokens       512
generated tokens    128
runtime context     32,768
GPU layers          all available
flash attention     on
batch / ubatch      2,048 / 512
K/V cache           f16 / f16
memory mapping      off
CPU threads         6, pinned to mask 0x3f
```

The Vulkan control used `llama.cpp` build `b10216` for five repetitions. The deployed ROCm result used build `b10085` for 50 repetitions. A genuinely perfect A/B would use one source commit and change only the backend build flag. I retain this result because it is the closest same-host production comparison available and disclose the revision difference instead of smoothing it away.

## The result splits in two

| Backend | Prompt processing, 512 tokens | Token generation, 128 tokens |
| --- | ---: | ---: |
| Vulkan, five runs | 1,115.30 tok/s | **97.73 tok/s** |
| ROCm, 50 runs | **1,344.65 ± 29.79 tok/s** | 73.65 ± 0.50 tok/s |
| ROCm, safe-core / no-graphs control, 50 runs | **1,376.78 tok/s** | 73.96 tok/s |

Against this Vulkan build, ROCm is **20.56% faster at prompt processing** and **24.64% slower at generation**.

Both statements are true. “ROCm is faster” and “Vulkan is faster” are both incomplete.

The practical impact depends on request shape. With a long document and a short answer, the extra ROCm prefill speed can dominate. In an interactive coding session with a modest prompt and a long completion, Vulkan's additional 24 tokens per second is conspicuous. Retrieval-augmented generation, chat, batch summarisation and agentic code edits do not place the same weight on the two phases.

The best short ROCm run reached 1,446.56 tok/s for prefill and 74.52 tok/s for generation, but I do not use the best run as the headline. The 50-run average is the number a product can plan around. A separate ten-request API gate delivered a mean 73.20 tok/s, with a narrow 72.82–73.30 range, confirming that the benchmark binary and served path told the same generation story.

## Turning rates into a user-visible wait

Tokens per second are useful engineering units, but product work needs elapsed time.

For an illustrative request with a 4,096-token prompt and a 512-token answer, a simple two-phase estimate is:

| Backend | Estimated prompt time | Estimated generation time | Estimated total |
| --- | ---: | ---: | ---: |
| Vulkan | 3.67s | 5.24s | 8.91s |
| ROCm | 3.05s | 6.95s | 10.00s |

That estimate deliberately ignores tokenisation, scheduling, API overhead and context-length scaling. It is not a measured end-to-end request. It shows why workload mix matters: ROCm saves about 0.62 seconds in prefill and then gives back about 1.71 seconds during the longer answer.

Change the request to a 32,000-token input and a 128-token extraction, and the balance moves sharply towards ROCm. Backend selection should therefore be tied to a request distribution, not a synthetic winner.

## Profiling explains where to look next

ROCm's generation result was stable, so I profiled it rather than endlessly changing launch flags. The top two Q4_K matrix-vector kernels accounted for **68.62%** of captured kernel time; the top three were close to 78%.

That concentration is useful. It says the service layer, JSON API and CPU pinning are not the main explanation for the decode gap. The opportunity is in a small number of backend-specific quantised matrix-vector kernels. The safe-core / no-graphs control barely changed generation, which makes graph capture an unlikely explanation as well.

This is an important product-management habit in technical work: stop optimising the visible control surface once evidence points below it. Tuning every batch size will not repair a kernel that dominates the critical path.

## The 122B model tests whether the pattern generalises

A second model changes the shape of the result. I tested Qwen3.5-122B-A10B `Q4_K_XL`, a 77.03GB GGUF, using the optimised `llama.cpp` configurations for each backend.

| Backend | Prompt 512 | Prompt 4,096 | Generation 128 |
| --- | ---: | ---: | ---: |
| ROCm | **339.9 tok/s** | **523.0 tok/s** | 21.3 tok/s |
| Vulkan | 285.0 tok/s | 374.3 tok/s | **22.9 tok/s** |

The broad split remains: ROCm leads prompt processing and Vulkan leads generation. The size of the generation difference is much smaller than it was for Qwen3-Coder, which is exactly why a backend verdict should include the model.

I also compared the same 122B workload through an OpenAI-compatible API, using roughly 615 prompt tokens, up to 64 generated tokens, two warm-ups and ten measured waves. Prefix caching was disabled and runtime context held at 4,096.

| Runtime and format | One client, aggregate tok/s | One client TTFT | Two clients, aggregate tok/s | Two-client TTFT |
| --- | ---: | ---: | ---: | ---: |
| `llama.cpp` ROCm, GGUF | **13.84** | 1.634s | 15.93 | 4.160s |
| `llama.cpp` Vulkan, GGUF | 12.87 | 2.133s | **17.11** | 3.805s |
| vLLM, GPTQ Int4 | 10.11 | **1.091s** | 15.97 | **1.773s** |
| vLLM, GGUF | 12.03 | 2.170s | 12.94 | 4.127s |

At one interactive client, `llama.cpp` ROCm delivered the highest generation rate. At two clients, Vulkan produced the highest aggregate rate, 6.7% above ROCm. vLLM's GPTQ path essentially tied ROCm's two-client aggregate result — the 0.26% difference is noise at this level — while returning the first token much sooner.

That is a better decision table than “backend A wins”. If first-token latency for two simultaneous users is the main requirement, vLLM GPTQ is compelling even though it loses the one-client throughput test. If one person is working locally, `llama.cpp` ROCm is the faster 122B interactive path. If two clients need maximum aggregate decode, Vulkan wins this run.

The vLLM comparison is also outside its official sweet spot. The project's [Qwen3.5 recipes](https://github.com/vllm-project/recipes/blob/main/Qwen/Qwen3.5.md) validate data-centre accelerators and multi-GPU configurations, not this 128GB integrated-memory desktop. It is a useful control and an interesting engineering path, not evidence of official support for this exact host.

## Settings that mattered, and settings that did not

Across these runs, four disciplines mattered more than speculative tweaking:

- keep the whole model resident instead of allowing accidental CPU offload;
- size batch and micro-batch for the prompt phase without destabilising shared memory;
- pin a small CPU set for orchestration and leave the GPU path measurable;
- keep context, cache precision, prompt and output length identical across the comparison.

The ROCm Qwen3-Coder result used flash attention, a 2,048 batch, 512 micro-batch and F16 K/V cache. Disabling graph-related optimisation and using the conservative kernel path did not recover the Vulkan generation lead. That negative result saves more time than another page of unexplained flags.

For vLLM, tuning improved the original GPTQ baseline by 11.7%, but the stock WNA16 path remained the stable production choice. A native fused-MoE prototype passed numerical validation and then triggered GPU resets after roughly six requests. Serialising it stopped the resets and reduced performance to 7.05 tok/s. It stays an opt-in experiment.

## A backend policy, not a backend religion

My current policy for this machine is:

| Workload | Starting choice | Reason |
| --- | --- | --- |
| Long input, short extraction | `llama.cpp` ROCm | Stronger prompt processing on both measured models |
| Qwen3-Coder, long completion | `llama.cpp` Vulkan | Materially faster measured decode |
| 122B, one interactive user | `llama.cpp` ROCm | Best measured single-client API throughput |
| 122B, two throughput-oriented clients | `llama.cpp` Vulkan | Best measured aggregate generation |
| Two clients prioritising first token | vLLM GPTQ | Lowest measured two-client TTFT |
| New or unqualified model | Run the matched test | Architecture can change the answer |

Keeping both ROCm and Vulkan available costs a little disk space and some release discipline. It buys a better product: the runtime can be chosen for the workload, and one backend remains a useful recovery path when the other regresses.

The conclusion is not that Vulkan or ROCm has won Strix Halo. It is that **backend performance is a two-phase, model-specific product decision**. Once the prompt and generation phases are measured separately, the apparent contradiction disappears — and the next question becomes which model and quantisation are worth serving at all.

That is the subject of [the next article: finding the useful quant](/blog/2026/08/03/finding-the-useful-quant-strix-halo/).

*Sources checked 3 August 2026: the official [`llama.cpp` repository](https://github.com/ggml-org/llama.cpp), [Lemonade's `llama.cpp` backend documentation](https://lemonade-server.ai/docs/guide/configuration/llamacpp/), [Lemonade's experimental vLLM backend documentation](https://lemonade-server.ai/docs/guide/configuration/vllm/), the [vLLM Qwen3.5 recipe](https://github.com/vllm-project/recipes/blob/main/Qwen/Qwen3.5.md) and the [Qwen3.5-122B-A10B model card](https://huggingface.co/Qwen/Qwen3.5-122B-A10B). All performance figures above come from retained same-machine benchmark artefacts.*
