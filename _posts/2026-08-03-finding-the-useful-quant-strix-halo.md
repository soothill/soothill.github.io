---
layout: post
title: "Finding the useful quant: what fits is not what wins"
seo_title: "Strix Halo quantisation: 0.8B to 397B"
date: 2026-08-03 11:00:00 +0100
last_modified_at: 2026-08-03 18:00:00 +0100
permalink: /blog/2026/08/03/finding-the-useful-quant-strix-halo/
categories: [local-ai, benchmarks, product]
tags: [quantization, qwen3-5, gguf, mixture-of-experts, strix-halo]
author: Darren Soothill
editorial_standard: soothill-human-v1
editorial_review_status: approved
editorial_reviewer: Darren Soothill
editorial_reviewed_at: 2026-08-17
series: "Local LLMs on Strix Halo"
series_order: 4
description: "A measured 0.8B-to-397B Strix Halo model sweep showing why file size, active parameters, context cost and answer quality must be separate decisions."
---

> **Test record:** eight Qwen3.5 model sizes were measured on the same 128GB EVO-X3. The optimised ROCm figures below use the same host and benchmark shape; the 397B model required smaller batch settings and is identified separately. This is a throughput and fit study, not a quality evaluation.

Strix Halo makes a seductive promise: enough shared memory to run models that do not fit on ordinary consumer GPUs. That is true. It is also where a great deal of local-AI advice goes wrong.

Fitting a model into memory is a binary engineering gate. Choosing the model is a product decision. The largest file that crosses the gate may be slower, less accurate after aggressive quantisation, short of useful context or simply worse value than a smaller mixture-of-experts model.

As a Director of Product, I want a portfolio rather than a trophy. A small model can make a utility feel instant. A mid-sized model can be the daily driver. A 122B model can justify its wait on harder work. A 397B model that technically loads may only prove the platform boundary. One machine can support all four roles, but only if “best” is allowed to mean different things.

## The size sweep

I measured the Qwen3.5 family from 0.8B to 397B. The 0.8B through 122B files use `Q4_K_XL`; the 397B model uses the much more aggressive `IQ1_M` quantisation so that its 397 billion parameters can fit at all.

| Model | Architecture | GGUF size | Prompt 512 | Prompt 4,096 | Generation 128 |
| --- | --- | ---: | ---: | ---: | ---: |
| Qwen3.5 0.8B | Dense | 0.56GB | **8,093.89 tok/s** | **6,762.24 tok/s** | **198.73 tok/s** |
| Qwen3.5 2B | Dense | 1.34GB | 4,124.50 | 4,193.08 | 114.55 |
| Qwen3.5 4B | Dense | 2.91GB | 1,826.42 | 1,719.26 | 57.59 |
| Qwen3.5 9B | Dense | 5.97GB | 1,097.62 | 1,122.51 | 34.87 |
| Qwen3.5 27B | Dense | 17.62GB | 366.29 | 355.51 | 11.82 |
| Qwen3.5 35B-A3B | MoE | 22.24GB | 1,059.38 | 1,423.49 | 50.35 |
| Qwen3.5 122B-A10B | MoE | 77.03GB | 316.68 | 524.81 | 21.33 |
| Qwen3.5 397B-A17B | MoE, `IQ1_M` | 106.82GB | 100.73 | 106.73 | 15.46 |

The 397B run used a 512/256 batch and micro-batch rather than the larger optimised settings used by the other models. It is included to show the outer envelope, not to pretend that every row is a perfectly isolated scale test.

The table still overturns the simplest assumption. The 22.24GB 35B-A3B file generates at **50.35 tok/s**, while the smaller 17.62GB dense 27B produces **11.82 tok/s**. The larger file is 4.26 times faster at generation. Even the 77.03GB 122B-A10B model is 80.4% faster than the dense 27B.

File size did not stop mattering. It stopped being enough to predict compute.

## Total parameters and active parameters are different products

A dense model uses essentially all of its model layers for each token. A mixture-of-experts model routes each token through a subset of expert weights. That allows it to store more total learned capacity while activating much less compute per token.

The suffixes make the important distinction visible:

- `35B-A3B` means roughly 35 billion total parameters and about 3 billion active parameters per token;
- `122B-A10B` means roughly 122 billion total and 10 billion active;
- `397B-A17B` means roughly 397 billion total and 17 billion active.

Those labels are not exact performance forecasts. Attention layers, routing, memory access, quantisation kernels and context length all contribute. They are nevertheless more useful than comparing 35, 122 and 397 as though every parameter participates in every token.

The 35B-A3B result is the clearest expression of the Strix Halo opportunity. It has enough memory to hold the experts and enough bandwidth to generate at a genuinely interactive rate. The slower dense 27B is not “bad”; it simply occupies an awkward point in this particular family and backend.

## A quantisation label is not a quality score

Quantisation stores weights at lower precision so that a model needs less memory and memory bandwidth. It is what makes the upper half of this table possible on a 128GB host. It also discards information.

`Q4_K_XL` and `IQ1_M` are storage and compute formats, not portable promises about answer quality. A four-bit quant generally preserves more signal than a one-bit-class format, but the practical loss depends on the model, task and quantisation method. The 397B file is only 1.39 times the size of the 122B file despite representing more than three times the total parameters. That compression is not free.

This benchmark does **not** answer whether the 397B `IQ1_M` model reasons, codes or follows instructions better than the 122B `Q4_K_XL` model. It only proves that the 106.82GB file loads and produces 15.46 tokens per second under the tested settings.

I would not ship a model decision without a separate quality gate built from the intended work:

1. deterministic factual and formatting checks;
2. representative product or coding tasks scored blind;
3. long-context retrieval cases with answer evidence;
4. tool-use and structured-output validity;
5. regression cases drawn from previous failures;
6. human preference only after the objective failures are visible.

The useful unit is quality per second at the target context, not parameters per pound or a model's position on a generic benchmark.

## Model memory is not the whole memory budget

The EVO-X3 has 128GB of physical memory and Linux exposes about 124GiB. The model file is only the first claim on it. The runtime also needs compute buffers, K/V cache, graph data, service memory, filesystem cache and enough headroom to keep the operating system healthy.

K/V cache grows with context length and parallel slots. It is the reason “the weights fit” can turn into an allocation failure when a user asks for 256K context. Cache precision matters too. In the long-session test I use `q8_0` K and V cache to make a 262,144-token slot practical without reducing it to an unqualified low-precision experiment.

The capacity policy I use is therefore:

```text
physical memory
- operating-system reserve
- lifecycle and backend reserve
- model allocation
- target-context K/V cache
- transient compute buffers
= safety headroom
```

I want tens of gigabytes free for the everyday model, not a screenshot showing 99.8% allocation. For an occasional large-model run, the reserve can be smaller if the machine is otherwise quiet and the load path is well observed. Swap activity is a warning, not an extension of GPU memory: once active weights spill into storage, an impressive capacity claim can become an unusable product.

## Serving format can change the decision

GGUF is not the only way to present a quantised model. For the 122B comparison, I also served Qwen's official GPTQ Int4 release through vLLM. That file set comprised 39 shards and about 73.45GiB on disk. The API benchmark produced:

| 122B path | One-client throughput | Two-client aggregate | Two-client TTFT |
| --- | ---: | ---: | ---: |
| `llama.cpp` ROCm, GGUF `Q4_K_XL` | **13.84 tok/s** | 15.93 tok/s | 4.160s |
| vLLM, official GPTQ Int4 | 10.11 tok/s | **15.97 tok/s** | **1.773s** |

The two-client throughput difference is 0.26%, which is not meaningful. The time-to-first-token difference is. This is not a claim that GPTQ and GGUF have equal quality or even identical weights. It shows that format, runtime and scheduler form one serving solution. The fastest single-user model file is not automatically the best multi-user API.

## The useful tiers on this machine

After separating fit, speed and quality, the size sweep turns into a practical portfolio.

### Instant utilities: 0.8B to 4B

At 58–199 generated tokens per second, these models suit classification, short transformations, structured extraction and UI features where latency is part of the experience. Their small footprint also leaves nearly the whole machine available to another workload.

They should not be dressed up as universal reasoning engines. Their value is focus and speed.

### Responsive general work: 9B and 35B-A3B

The 9B dense model remains comfortably interactive at 34.87 tok/s. The 35B-A3B is the standout: 50.35 tok/s with a much larger expert pool. Subject to task-quality validation, it is the family's obvious daily-driver candidate.

My current everyday coding service uses the related Qwen3-Coder 30B-A3B `Q4_K_S`, which delivered about 74 tok/s on ROCm and 98 tok/s on Vulkan in the [backend comparison](/blog/2026/08/03/llamacpp-vulkan-vs-rocm-strix-halo/). It combines useful model capacity with an interaction rate that does not make every edit feel like a batch job.

### Deliberate hard work: 122B-A10B

At 21.33 tok/s in the kernel benchmark and 13.84 tok/s through the measured single-client API, the 122B model is slower but usable. It belongs on tasks where its extra capability earns the wait: difficult analysis, code review or long documents. It also leaves enough memory for a carefully sized context and stable service.

### Boundary demonstration: 397B-A17B `IQ1_M`

Loading a 397B-class model on an integrated GPU desktop is technically remarkable. At 15.46 tok/s, the measured rate is not merely ceremonial. The unresolved question is whether the extreme quant retains enough quality to outperform the 122B four-bit model on the work that matters.

Until that gate exists, I treat 397B as a platform experiment, not the default product.

## The selection rule

The most useful quant is the smallest format that clears the quality bar for a defined workload while preserving the required context, latency and operational headroom.

That rule may select a larger MoE over a smaller dense model. It may select GPTQ for a concurrent service and GGUF for one local user. It may even select two models — an instant router and a slower expert — instead of forcing one enormous model into every interaction.

Strix Halo's 128GB memory pool is valuable because it expands those choices. The achievement is not that a 106.82GB file fits. It is that models from 0.56GB to 106.82GB can be assigned to the roles they are actually good at.

The next article tests the part a size sweep cannot: whether the 122B configuration remains useful when the context is nearly full and the session lasts more than an hour. Read [the 256K long-session test](/blog/2026/08/03/qwen35-122b-256k-long-session-test/).

*Sources checked 3 August 2026: the official [Qwen3.5-122B-A10B model card](https://huggingface.co/Qwen/Qwen3.5-122B-A10B), [`llama.cpp`](https://github.com/ggml-org/llama.cpp) and [vLLM's GGUF documentation](https://docs.vllm.ai/en/latest/features/quantization/gguf/). Model sizes and throughput figures come from retained EVO-X3 benchmark summaries; no quality score is inferred from them.*
