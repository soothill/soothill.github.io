---
layout: post
title: "Qwen3.8 Flash Next on AMD Strix Halo: ROCm vs Vulkan"
seo_title: "Qwen3.8 Flash Next: ROCm vs Vulkan on Strix Halo"
date: 2026-08-27 10:30:00 +0100
last_modified_at: 2026-08-27 10:30:00 +0100
permalink: /blog/2026/08/27/qwen38-flash-next-rocm-vulkan-strix-halo/
categories: [local-ai, benchmarks, engineering]
tags: [qwen3.8, qwen4exp, llama-cpp, vulkan, rocm, strix-halo, lemonade, prompt-caching, long-context]
author: Darren Soothill
editorial_standard: soothill-human-v1
editorial_review_status: approved
editorial_reviewer: Darren Soothill
editorial_reviewed_at: 2026-08-27
series: "Local LLMs on Strix Halo"
series_order: 18
description: "I compare ROCm and Vulkan for Qwen3.8 Flash Next on AMD Strix Halo, then tune a 104GiB model to 15.6 tok/s single-stream and 24.3 tok/s aggregate."
---

> **Test record:** On a 128 GB Ryzen AI MAX+ 395 workstation, Vulkan first
> made this 104 GiB experimental Qwen model usable. A second tuning pass has
> now pushed it to 15.6 generated tokens per second for one request and 24.3
> aggregate tokens per second for two cached requests.

## The short version

I tested the four-shard [Unsloth Qwen3.8 Flash Next GGUF](https://huggingface.co/unsloth/Qwen3.8-Flash-Next-GGUF), using the `UD-Q4_K_XL` quantisation, on an AMD Ryzen AI MAX+ 395 system with Radeon 8060S graphics and 128 GB of unified memory. The model is approximately 103.7 GiB, which makes both performance and memory placement unusually important.

The first stable, matched eight-layer comparison made the backend decision clear:

| Result | ROCm | Vulkan | Difference |
|---|---:|---:|---:|
| Mean generation speed | 1.79 tokens/s | **11.50 tokens/s** | **6.43× faster** |
| Steady prompt processing | 16.95 tokens/s | **17.90 tokens/s** | 5.6% faster |
| Model load time | 83.3 seconds | **29.4 seconds** | **64.7% shorter** |
| Minimum available system memory | 54.29 GiB | **109.14 GiB** | **54.85 GiB more headroom** |
| Peak GPU-addressable UMA (GTT) | 39.88 GiB | **12.15 GiB** | **69.5% lower** |

That was the starting point, not the end of the tuning. Once Vulkan had passed correctness and stability gates, I increased ordinary transformer-block offload from eight to 40 layers, added a second 256K slot and enabled a bounded 4 GiB explicit prompt cache. The latest tuning and production measurements now show:

| Latest Vulkan result | Measured performance |
|---|---:|
| Single-request retrieval prefill | **109.55 tokens/s** |
| Single-request generation | **15.56 tokens/s** |
| Two-request uncached aggregate | **17.37 tokens/s** |
| Two-request cached aggregate | **24.30 tokens/s** |
| 3,149-token uncached request through Lemonade | **27.15 seconds** |
| Same request with a prompt-cache hit | **0.73 seconds** |

The optimized production release is registered in Lemonade as `Qwen3.8-Flash-Next-Q4KXL-PR27742-Fixed`. The two-slot design preserves a full 262,144-token context for each request; it does not turn either request into a 512K-context request.

This is not evidence that Vulkan always beats ROCm. It is evidence that, for this experimental Qwen4Exp graph, this quantization, this llama.cpp build, and this AMD unified-memory architecture, Vulkan was the substantially better runtime.

## The hardware and model

The test machine was an EVOX3 workstation with:

- AMD Ryzen AI MAX+ 395;
- integrated Radeon 8060S, reported as GFX1151;
- 128 GB of unified system memory;
- Linux with the RADV Vulkan driver;
- Lemonade Server 11.8 for production serving.

The model was Unsloth's `Qwen3.8-Flash-Next-UD-Q4_K_XL`, stored as four GGUF shards totalling about 103.7 GiB. The initial backend comparison used the experimental llama.cpp Qwen4Exp work in [pull request 27742](https://github.com/ggml-org/llama.cpp/pull/27742) at commit `0b19188e935480369f3b006e0cf17576dce066a3` (build 10666). The current production tuning uses build 10707 at commit `250b61446efc91e3a179c8677956f2667c8fbda0`, with Mesa 26.3.0-devel RADV for GFX1151.

That model size matters. On a discrete GPU, we would normally reason about VRAM and system RAM separately. On Strix Halo, the CPU and GPU compete for the same physical memory. Model mappings, pinned GPU pages, the KV cache, temporary compute buffers, the operating system, and applications all draw from the same 128 GB pool.

Simply observing that 103.7 is less than 128 is therefore not enough to say the model fits safely.

## How I compared the runtimes

The original direct ROCm and Vulkan performance runs used the same core inference settings:

- eight GPU-offloaded layers;
- 4,096-token test context;
- 16 CPU threads;
- batch size 512 and micro-batch size 128;
- F16 key and value cache;
- flash attention enabled;
- one inference slot;
- prompt caching disabled;
- speculative decoding disabled.

Each timed generation produced 128 tokens after the same 46-token prompt. I recorded server-reported prompt and generation timing, wall-clock time, Linux `MemAvailable`, and AMD GTT usage.

There is one important qualification: this compares the best stable end-to-end configurations, not a synthetic test in which only the backend name changes. The per-layer token embedding operation used by the experimental architecture had to remain on the CPU for the Vulkan path. Attempting that placement on the Vulkan GPU aborted because the required operation was not supported. The ROCm baseline used its working placement. The CPU override is therefore part of the Vulkan configuration being evaluated, rather than an incidental benchmark change.

## Generation performance: Vulkan by a wide margin

ROCm produced 1.74 and 1.84 tokens/s in the two measured generation runs, for a mean of 1.79 tokens/s. Vulkan produced 11.41 and 11.59 tokens/s, averaging 11.50 tokens/s.

That makes the direct Vulkan configuration 6.43 times faster, or approximately 543% above the ROCm result.

The difference is easy to feel. The steady ROCm run took 71.9 seconds to process the prompt and generate 128 tokens. The comparable Vulkan run took 13.5 seconds. At 1.8 tokens/s, interactive use feels laborious. At roughly 11.5 tokens/s, the model becomes practical for local chat, structured output, and agent work.

Prompt processing was much closer: 16.95 tokens/s on the steady ROCm sample and 17.90 tokens/s on the second Vulkan sample. The largest gain was therefore in autoregressive generation rather than short-prompt ingestion.

Vulkan also loaded the model in 29.4 seconds, compared with 83.3 seconds for ROCm. That is a 64.7% reduction in startup time and helps when a model manager needs to switch between large specialist models.

## The memory result was just as important

The speed difference was striking, but the memory measurements determined which configuration was safe enough to deploy.

During the comparable direct tests, ROCm's minimum available memory was 54.29 GiB and its peak GTT use was 39.88 GiB. Vulkan retained 109.14 GiB of available memory and peaked at 12.15 GiB of GTT.

In other words, the Vulkan run preserved 54.85 GiB more usable memory headroom and reduced peak GPU-addressable UMA by about 69.5%.

Those figures should not be interpreted as “the 104 GiB model consumes only 12 GiB.” The GGUF is memory-mapped. Linux can keep file-backed model pages in its page cache and reclaim them when necessary, so mapped or resident process memory is not additive in the same way as anonymous, locked allocations. `MemAvailable` is useful because it estimates how much memory the system can still supply without swapping. GTT is useful because it shows how much memory the AMD GPU path has made addressable and potentially less reclaimable while working.

The ROCm snapshot also showed roughly 27 GiB of shared memory, while the Vulkan snapshot showed almost none. Combined with the GTT difference, that explains why looking only at the GGUF size or process resident set would have hidden the operational risk.

This is also why memory-mapped loading remained mandatory. A direct, non-mapped loading experiment ran the machine out of memory. The final server clears stale model processes and model-backed cache state before constrained tests, then checks both available memory and residual GTT before loading `Qwen3.8-Flash-Next-Q4KXL-PR27742-Fixed`.

The later 40-layer profile deliberately spends much more of that headroom. Its heaviest two-slot, filled-cache canary peaked at 77.30 GiB of GTT and bottomed at 36.96 GiB of available memory. That is still above the deployment guard, but it is why the fastest configuration stops at 40 rather than blindly offloading every layer.

## How eight GPU layers became 40

The first tuning pass tried small changes around an eight-layer baseline. The decisive improvement came from measuring a clean offload ladder while keeping the CPU-backed per-layer token-embedding table, prompt, cache rules and correctness tests fixed.

| Vulkan profile | Retrieval prompt tok/s | Retrieval generation tok/s | Uncached pair aggregate tok/s | Cached pair aggregate tok/s | Peak GTT GiB | Minimum available GiB |
|---|---:|---:|---:|---:|---:|---:|
| 8 layers, 1 slot, 2 GiB cache | 40.95 | 10.71 | 8.37 | 11.30 | 14.96 | 96.04 |
| 16 layers, 1 slot, 2 GiB cache | 48.07 | 11.54 | 9.00 | 11.94 | 28.72 | 83.06 |
| 24 layers, 1 slot, 2 GiB cache | 57.49 | 12.41 | 9.71 | 12.58 | 42.71 | 71.46 |
| 32 layers, 1 slot, 2 GiB cache | 75.39 | 13.61 | 10.81 | 14.02 | 56.45 | 58.97 |
| 40 layers, 1 slot, 2 GiB cache | **109.55** | **15.56** | 12.66 | 16.79 | 70.27 | 47.33 |
| 40 layers, 2 slots, 2 GiB cache | 104.24 | 14.90 | 17.14 | 23.73 | 77.30 | 38.71 |
| 40 layers, 2 slots, 4 GiB cache | 105.09 | 15.37 | **17.37** | **24.30** | 77.30 | 36.96 |

[Download the tuning matrix as CSV](/assets/data/evox3-qwen38-flash-next-vulkan-tuning-2026-08-27.csv).

At one slot, moving from eight to 40 layers improved retrieval prefill by 167.5% and generation by 45.3%. Adding the second slot raised uncached aggregate throughput by a further 35.3% over the 40-layer single-slot result. Against the original eight-layer, one-slot shape, the final canary delivered 107.5% more uncached aggregate output.

Concurrency improves total throughput and queueing rather than making an individual response faster. With both slots busy, each request generated at roughly 12.4–13.5 tokens/s, compared with about 15.6 tokens/s when one request had the GPU to itself.

## Moving from a benchmark to two 256K production slots

The production goal was a 256K context window, not merely a fast 4K benchmark. The current Lemonade profile allocates 524,288 tokens across two slots, giving each request its own 262,144-token context, and uses:

- the Vulkan GFX1151 llama.cpp build;
- 40 GPU-offloaded transformer layers;
- per-layer token embeddings on CPU;
- 16 threads;
- batch 512 and micro-batch 128;
- flash attention;
- F16 KV cache;
- memory-mapped model loading;
- two inference slots;
- a 4 GiB explicit prompt cache;
- idle-slot caching disabled;
- no speculative decoding.

The important llama.cpp arguments are:

```text
--ctx-size 524288 --parallel 2
--gpu-layers 40
--cache-ram 4096 --cache-prompt --no-cache-idle-slots
--fit off --batch-size 512 --ubatch-size 128 --flash-attn on
--override-tensor '^per_layer_token_embd[.]weight$=CPU'
```

The earlier profile passed retrieval checks with context allocations of 16K, 32K, 64K, 128K, and 256K, followed by a correct 27,986-token retrieval through Lemonade. The optimized production profile then passed exact output, arithmetic, strict JSON and retrieval again. Its production retrieval result reached 103.05 prompt tokens/s and 15.41 generated tokens/s.

Two simultaneous exact-output requests started together and finished in 14.41 and 15.86 seconds. They delivered 13.81 aggregate tokens/s without a cache hit and 24.32 aggregate tokens/s with cached prefixes. Every answer was exact, and there were no GPU page faults, resets, device-loss messages or wedged-GPU events.

I did not run a literal near-256K prompt. A simple linear estimate at the optimized 103–105 prompt tokens/s is about 42 minutes for a completely uncached 256K prefill, but real performance can fall as context grows. The allocation and execution path have been validated at 256K, and materially long retrieval has been validated at nearly 28K, but those are different claims. Lemonade's production timeout remains four hours so that a genuine 256K request is not cancelled prematurely.

## Prompt caching changes repeat-request performance

The original deployment disabled prompt caching while the Qwen4Exp cache path was being qualified. The fixed runtime now uses explicit prompt caching while keeping idle-slot caching disabled.

The 4 GiB cache test filled eight distinct 4,588-token histories. After all eight had run, the oldest two still restored 4,584 of 4,588 tokens. Their cold prompt processing took roughly 40.1–41.5 seconds; restoration took only 0.176–0.187 seconds. In production, a 3,149-token request fell from 27.15 seconds uncached to 0.73 seconds on a cache hit.

The cache is bounded and demand-allocated. Filling the test workload added about 4.09 GiB of anonymous memory, and three older entries were evicted as the limit was reached. The extra capacity therefore improves repeated long conversations, but it retains prompt content in RAM, adds memory-copy work and reduces the safety margin available to other applications. It does nothing for a genuinely new prompt.

## A one-hour stability follow-up

After the original production deployment, I ran a controlled 60-minute soak against `Qwen3.8-Flash-Next-Q4KXL-PR27742-Fixed`. The workload combined continuous 256-token generation, 13 exact-output checks, and six repeated 4K retrievals. All 136 requests passed, covering 29,643 prompt tokens and 30,147 generated tokens, with no backend restart or GPU fault.

The memory trend was effectively flat after warm-up. Private dirty memory increased by about 2.46 MiB between the 10–15 minute and 55–60 minute windows, equivalent to a regression of approximately 0.91 MiB/hour. Anonymous RSS trended at 0.67 MiB/hour, while GTT, threads, and file descriptors showed zero growth. Available memory never fell below 100.11 GiB.

Performance did not decay: the first 20 sustained decode requests averaged 11.57 tokens/s and the last 20 averaged 11.61 tokens/s. Two additional idle minutes showed no GTT increase or retained private-memory step. A one-hour run cannot exclude an extremely slow leak or substitute for repeated near-256K prompts, but it found no observable memory leak in the model and runtime.

That soak predates the 40-layer, two-slot, 4 GiB-cache profile. The new profile passed clean memory, correctness, cache-eviction, concurrency and AMD-fault canaries, but I do not present the earlier one-hour result as a 60-minute soak of the new memory shape.

## What helped, what did not, and where I stopped

Several apparently obvious optimizations were either slower or unsafe:

- Increasing from 16 to 32 CPU threads substantially reduced performance.
- Raising the batch and micro-batch sizes to 2,048 and 512 was slower than 512 and 128.
- Removing GPU offload was slower.
- Moving the experimental per-layer token embedding operation to the Vulkan GPU caused an unsupported-operation abort.
- Direct/non-mapped loading exhausted memory.
- Speculative MTP decoding was unavailable because this GGUF does not contain the required MTP tensors.

The clean layer ladder showed that substantial ordinary-block offload did help once measured systematically. The model has 48 ordinary blocks of roughly 1.5 GiB each, plus a separate 26.82 GiB per-layer token-embedding table that remains CPU-backed. Extrapolating from 40 to all 48 layers suggested roughly another 14 GiB of GTT. Under the heaviest canary that would leave only about 5 GiB above the server's 18 GiB shutdown guard, so I did not attempt all-48 offload.

The best result came from selective placement rather than maximum offload: accelerate 40 layers that Vulkan handles well, leave the large problematic table on the CPU, and preserve enough unified-memory headroom for the operating system and other services.

## Correctness and production deployment

Performance is irrelevant if an experimental backend silently changes answers. The current Vulkan profile passed four Lemonade checks covering exact instruction following, arithmetic, strict JSON and retrieval. It also passed simultaneous exact-output requests, divergent cache suffixes, alternating slots, oldest-entry restoration and cache eviction. No GPU fault was recorded.

The model is exposed through Lemonade under the registered name `Qwen3.8-Flash-Next-Q4KXL-PR27742-Fixed`, with the default routes `llm` and `llm-exact` pointing to the same profile. The current production retrieval check reached 103.05 prompt tokens/s and 15.41 generated tokens/s, and six repeated cache cycles all returned the expected answer in roughly 0.65–0.72 seconds end to end.

`Qwen3.8-Flash-Next-Q4KXL-PR27742-Fixed` is warmed when Lemonade starts and remains resident after ordinary idle periods, but it is not pinned. An explicitly selected specialist model can still replace it. Clients can request the registered model name directly or follow the `llm` default route; requests for different model names are serialized because this memory-constrained profile permits only one resident LLM.

## What I learned

The usual advice to prefer a vendor compute stack is too broad for experimental local inference. Backend maturity is operation-specific. A graph can spend most of its time in paths where one implementation is dramatically better, even on hardware made by another vendor.

On this machine, Vulkan delivered four benefits at once:

1. generation became fast enough for interactive use;
2. concurrency and explicit prefix caching made repeated agent work much faster;
3. startup became much shorter;
4. selective offload retained enough unified-memory headroom to make a 104 GiB model operationally safe.

The result is specific, reproducible, and bounded: Qwen3.8 Flash Next UD-Q4_K_XL, this experimental llama.cpp Qwen4Exp implementation, RADV on GFX1151, and a deliberately hybrid 40-layer configuration. The headline 24.3 tokens/s is aggregate throughput for two cached requests, not one request running at that rate. A lone request tops out around 15.6 tokens/s in this test. Future ROCm kernels, improved Vulkan support for the remaining per-layer embedding operation, or a compatible MTP-enabled GGUF could change the ranking.

For the software and model available today, however, Vulkan was not merely the faster option. With 40 layers offloaded, two 256K slots and a bounded explicit prompt cache, it turned Qwen3.8 Flash Next from an interesting experiment into a usable concurrent 256K-context service on AMD Strix Halo.

*Benchmark and deployment update: 27 August 2026. Lemonade 11.8.0; llama.cpp
build 10707 at `250b61446`; Mesa 26.3.0-devel RADV; Unsloth UD-Q4_K_XL;
Ryzen AI MAX+ 395 / Radeon 8060S. All performance figures come from retained
same-host qualification and production evidence.*
