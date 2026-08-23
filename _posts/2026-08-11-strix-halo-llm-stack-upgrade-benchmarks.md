---
layout: post
title: "Strix Halo LLM upgrades: what got faster and what failed"
seo_title: "Strix Halo LLM upgrade: wins and regressions"
date: 2026-08-11 11:00:00 +0100
last_modified_at: 2026-08-11 11:00:00 +0100
permalink: /blog/2026/08/11/strix-halo-llm-stack-upgrade-benchmarks/
categories: [local-ai, benchmarks, engineering]
tags: [llama-cpp, vllm, lemonade, rocm, strix-halo, gfx1151, qwen35, deepseek-v4, bf16, kv-cache, speculative-decoding]
author: Darren Soothill
editorial_standard: soothill-human-v1
editorial_review_status: approved
editorial_reviewer: Darren Soothill
editorial_reviewed_at: 2026-08-23
series: "Local LLMs on Strix Halo"
series_order: 11
description: "Matched before-and-after tests of llama.cpp, vLLM and Lemonade on Strix Halo, plus quantised KV, BF16, MTP, DFlash and ROCmFPX experiments."
---

> **Test record:** I updated the main inference engines on my 128GB Ryzen AI
> MAX+ 395 / Radeon 8060S (`gfx1151`) system, then repeated matched
> before-and-after benchmarks before touching the working services.
> `llama.cpp` b10362 stayed within **1.02%** of the old result and vLLM 0.27.0
> stayed within **0.30%** on the 122B throughput test. Lemonade 11.5.2 with my
> existing memory fix retained **97.9% less request memory** than unpatched
> 11.5.2. Quantised-KV decode improved by as much as **151.5%**, and a BF16
> patch improved 32K decode by **34.3%**, but the speculative candidates changed
> deterministic output and did not pass the deployment gate.

I expected this to be a fairly routine round of upgrades. It was not.

The official `llama.cpp` and vLLM updates barely moved performance. The quiet Lemonade memory fix was the change I was happy to deploy. The eye-catching community patches produced the largest numbers, but some of them also changed output or failed at a different context depth.

On a shared-memory APU, those failures matter more than the headline speed-up. I built each candidate away from the stable services, repeated the useful controls and only then decided what could stay on the machine.

## What I actually changed

“Latest” is a moving target, so this test pins the exact boundary captured on 11 August 2026:

| Component | Previous state | Candidate | Exact identity |
| --- | --- | --- | --- |
| `llama.cpp` | b10333 | [b10362](https://github.com/ggml-org/llama.cpp/releases/tag/b10362) | `4801e3c567d5` |
| vLLM | 0.26.0 | [0.27.0](https://github.com/vllm-project/vllm/releases/tag/v0.27.0) | `4bdc8a788d2e` |
| Lemonade Server | 11.5.1 plus local memory fix | [11.5.2](https://github.com/lemonade-sdk/lemonade/releases/tag/v11.5.2) plus the rebased fix | `14904dd5f74e` |
| Open WebUI | 0.11.0 | 0.11.0 | already current; digest-pinned image |
| SGLang | 0.5.17 | 0.5.17 | already current for this qualification |
| ROCm | 7.14 | 7.14 | unchanged platform baseline |

I built every candidate in an isolated directory. The stable binaries were not overwritten during measurement, and the production DeepSeek service was unloaded before each GPU campaign and restored afterwards. `llama.cpp` completed **12,801 of 12,801** backend-operation tests before I treated its performance numbers as usable. The vLLM 0.27 wheel was built locally for Python 3.12 and the ROCm 7.14 environment, with SHA-256 `020fac1682b2e500bbb327466d01a552fe12a3e750843ded5cd599155b0ced50`.

The compact dataset behind the tables is available as [CSV](/assets/data/evox3-version-upgrade-2026-08-11.csv).

## `llama.cpp`: the apparent regression that disappeared

The small-model comparison used the same lossless Qwen3.5-0.8B BF16 GGUF, deterministic prompt stream, 64 output tokens, two warm-up waves and ten measured waves. My first sequential run suggested that b10362 had lost more performance at eight clients than I was willing to accept.

I repeated it in an interleaved old/new/old/new order. That changed the conclusion:

| Concurrent clients | b10333 | b10362 | Change |
| ---: | ---: | ---: | ---: |
| 1 | 81.80 | 81.73 | -0.08% |
| 2 | 122.72 | 123.03 | +0.25% |
| 4 | 158.17 | 159.11 | +0.59% |
| 8 | 206.41 | 210.08 | +1.78% |

All values are aggregate completion tokens per second. The balanced run makes b10362 a clean update for this workload. More importantly, it shows why I do not promote a release from one convenient A/B order: a warmed page cache, compilation state or thermal sequence can become a fictional source-code regression.

## vLLM 0.27: small movement, then a 122B confirmation

The Qwen3.5-0.8B matrix kept vLLM 0.27 inside my predeclared 3% throughput gate at every concurrency:

| Concurrent clients | vLLM 0.26 | vLLM 0.27 | Change |
| ---: | ---: | ---: | ---: |
| 1 | 86.33 | 86.30 | -0.04% |
| 2 | 150.71 | 151.85 | +0.76% |
| 4 | 250.84 | 247.43 | -1.36% |
| 8 | 316.54 | 308.73 | -2.47% |

The eight-client result is slower, but still inside the gate. A tiny model is not enough evidence for the service I care about, so I loaded the same [Qwen3.5-122B-A10B GPTQ-Int4](https://huggingface.co/Qwen/Qwen3.5-122B-A10B-GPTQ-Int4) snapshot under both versions. Both used ROCm 7.14, the same tuned MoE records, a 4,096-token server limit, two warm-up waves, ten measured waves, 64 output tokens and seed 12345.

| Clients | Metric | vLLM 0.26 | vLLM 0.27 | Change |
| ---: | --- | ---: | ---: | ---: |
| 1 | completion tok/s | 10.28 | 10.25 | -0.30% |
| 2 | completion tok/s | 16.10 | 16.10 | -0.04% |
| 1 | mean TTFT | 1,108ms | 1,115ms | +0.64% |
| 2 | mean TTFT | 1,608ms | 1,680ms | +4.46% |
| 1 | mean end-to-end | 6,226ms | 6,244ms | +0.30% |
| 2 | mean end-to-end | 7,908ms | 7,915ms | +0.09% |

Both versions completed all 30 measured requests. The two-client TTFT means moved, but their 95% confidence intervals overlap widely: 1,367–1,849ms for 0.26 and 1,432–1,928ms for 0.27. Throughput and completed-request latency are flat. That is enough to stage vLLM 0.27 without claiming that it is a performance release for this model.

## DeepSeek exposed the HIP-graph trap

The direct DeepSeek check used the same 97.05GiB, four-shard `UD-IQ3_XXS` model from my [ROCm-versus-Vulkan study](/blog/2026/08/09/deepseek-v4-flash-vulkan-rocm-strix-halo/):

```text
-ngl 99 -fa 1 -p 2048 -n 64 -r 1 -mmp 0
```

The deep case added `-d 24576`. Both matched builds used ROCm 7.14, `GGML_HIP_GRAPHS=ON` and `HIP_LAUNCH_BLOCKING=1`.

| Test | b10286 | b10362 | Change |
| --- | ---: | ---: | ---: |
| shallow pp2048 | 145.33 | 145.01 | -0.22% |
| shallow tg64 | 14.13 | 14.10 | -0.21% |
| d24576 pp2048 | 89.29 | 88.38 | -1.02% |
| d24576 tg64 | 10.77 | 10.77 | -0.04% |

The source update is flat. I almost reported something very different.

My first b10362 build deliberately disabled HIP graphs because of a current [Strix Halo warning about long-output corruption](https://www.reddit.com/r/StrixHalo/comments/1vjopen/psa_llamacpp_currently_broken_on_strix_halo/). Compared with the graph-enabled old build, prompt processing stayed flat but generation fell to 10.35 tok/s shallow and 8.01 tok/s deep—about 26% slower.

That was a build-option mismatch, not a version regression. Rebuilding b10362 with graphs enabled restored generation to 14.10 and 10.77 tok/s. On this model, graphs improve decode by roughly 34–36% relative to the graph-disabled build.

The practical safety profile is therefore:

```text
HIP graphs on
HIP_LAUNCH_BLOCKING=1
```

Blocking launches retain the current community workaround without surrendering the graph benefit. It is not proof that every long-output problem has been fixed; it is the qualified configuration for this host.

The update does not reverse my earlier backend result. Patched Vulkan still leads the matched upstream-style DeepSeek GGUF comparison, particularly in generation. The specialised ROCmFP3 service remains the production route because it is a different quantisation and kernel stack, not because upstream ROCm has universally overtaken Vulkan.

## Lemonade 11.5.2: the clearest production win

The daemon update rebased the existing large-request memory fix onto Lemonade 11.5.2 and passed all 55 CTest cases. I then ran the same synthetic request-retention stress test against unpatched and patched 11.5.2:

| Build | Median retained RSS | Throughput |
| --- | ---: | ---: |
| 11.5.2 unpatched | 399,836KiB | 435.76 requests/s |
| 11.5.2 plus memory fix | 8,448KiB | 499.48 requests/s |
| Change | **-97.9%** | **+14.6%** |

This benchmark intentionally gives allocation overhead an unusually large share of total work; it is not a prediction that real model inference becomes 14.6% faster. The retained-memory result is the product reason to keep the patch. A local server that accepts large request bodies should not hold nearly 400MiB after the work is complete when it can retain about 8MiB instead.

This was the only candidate I promoted immediately. The active service now runs patched Lemonade 11.5.2, the previous 11.5.1 unit override is retained for rollback, and the production DeepSeek model passed a fresh end-to-end chat request after restart.

## Quantised KV fixed the long-context slowdown

The [quantised-KV work discussed in the Strix Halo community](https://www.reddit.com/r/StrixHalo/comments/1uzqg5m/i_made_quantized_kv_cache_workable_on_strix_halo/) changes the ROCm Flash Attention path rather than the model weights. I tested Q8 KV at increasing depth on Qwen3-Coder-30B-A3B:

| Context depth | Stock ROCm tg | Fixed ROCm tg | Change |
| ---: | ---: | ---: | ---: |
| 0 | 44.35 | 45.05 | +1.6% |
| 16K | 27.08 | 37.47 | +38.4% |
| 32K | 18.61 | 32.68 | +75.6% |
| 64K | 10.38 | 26.11 | +151.5% |

F16 KV was flat at the 32K control, isolating the gain to the quantised path. Prompt processing was also flat except for a 2.2% loss at 16K.

The ROCm-focused operation tests passed. The corresponding Vulkan candidate did not: its `FLASH_ATTN_EXT` correctness test produced a mismatch, so I did not benchmark or deploy it. A large number does not get to outrank a failed reference comparison.

This patch narrows an important ROCm weakness and could make long-context Q8 KV genuinely practical. It still belongs on a pinned ROCm-only experimental branch until the wider correctness surface and upstream state are clearer.

## BF16 was the patch worth watching

The most promising result came from [`llama.cpp` PR #26856](https://github.com/ggml-org/llama.cpp/pull/26856), also discussed in the [Strix Halo BF16 thread](https://www.reddit.com/r/StrixHalo/comments/1vl02db/llamacpp_pr26856_faster_prefill_better_quality/).

On Qwen3.6-35B-A3B Q6 at 32K:

| Build and KV type | pp512 | tg32 |
| --- | ---: | ---: |
| b10362 F16 | 508.35 | 31.12 |
| candidate F16 | 504.73 | 31.25 |
| b10362 BF16 | 503.83 | 23.24 |
| candidate BF16 | **564.28** | **31.21** |

The F16 control is flat. The candidate BF16 path improves prompt processing by 12.0% and decode by 34.3% relative to stock BF16.

Perplexity is the stronger part of the result:

| Path | WikiText-2 perplexity |
| --- | ---: |
| F32 reference, Flash Attention off | 9.2320 |
| stock F16 | 9.7953 |
| stock BF16 | 9.7774 |
| candidate F16 | 9.7953 |
| candidate BF16 | **9.2304** |

The candidate BF16 result matches the F32 reference rather than merely becoming faster. In this test, it improved both the serving metric and the quality control.

I still did not put it into the stable service. The pull request remains an upstream work in progress, and a strong three-chunk perplexity result is not the same as broad model coverage. This is the first patch I would revisit after upstream review.

## The speed-ups I did not ship

The remaining experiments explain why the release gate includes output and workload shape rather than throughput alone:

| Candidate | Performance result | Gate result | Decision |
| --- | --- | --- | --- |
| old MoE [PR #21344](https://github.com/ggml-org/llama.cpp/pull/21344) | +25.6% shallow prefill | at 32K: -10.8% prefill and -42.1% decode | reject |
| [ROCmFPX](https://github.com/charlie12345/ROCmFPX) Q6 | +0.5% generation | -13.6% prompt processing; perplexity +1.39% | reject current model/build |
| MTP | +16.8% completion throughput | deterministic 4,096-token output diverged | do not deploy |
| [Lucebox DFlash](https://github.com/Luce-Org/lucebox) | 37.51 versus 10.31 tok/s, **3.64x** | only 4 of 10 output hashes matched | experimental only |

### MTP: faster, but not byte-identical here

The [community MTP result](https://www.reddit.com/r/StrixHalo/comments/1tgxh2a/llamacpp_mtp_on_strix_halo_qwen36_27b_q8_hits_244/) reported large gains and byte-identical output. On my Qwen3.6-35B-A3B test, MTP raised aggregate completion throughput from 23.44 to 27.38 tok/s and shortened the measured run by 10.7%.

The 4,096-token, same-seed outputs diverged at byte 181. That may be a bug, an implementation boundary or a difference in the expected acceptance contract, but it is not byte identity. I will not trade deterministic output for a 16.8% throughput gain in the stable lane.

### DFlash: much faster, but different output

Lucebox DFlash completed ten HumanEval-style prompts at 37.51 generated tok/s; plain `llama.cpp` produced 10.31 tok/s. Mean end-to-end latency fell from 10.77s to 3.31s.

Only four of ten output hashes matched. I repeated the plain baseline and reproduced all ten of its hashes exactly, so the six differences were not ordinary baseline randomness. Lucebox's own validation guidance treats “autoregressive repeat matches, DFlash differs” as a warning. I agree with that gate.

This is an excellent research result and an unsuitable default today.

### ROCmFPX: generation was not the bottleneck it solved

The ROCmFPX build passed its focused quantisation tests, and the matched Q6 model was about 0.5% faster in generation. The order-balanced shallow comparison was nevertheless 13.6% slower in prompt processing. Its perplexity was 6.4329 versus 6.3445 for the stock Q6 model, a 1.39% increase with overlapping uncertainty intervals.

The model-card claim may hold for another build, shape or conversion. It did not reproduce as a useful end-to-end win on this host, so I rejected the current candidate rather than averaging unlike phases into a comforting number.

## Nothing reset the GPU

The useful negative result is that none of the retained runs reset the GPU.

- no compute-ring timeout;
- no `DeviceLost`;
- no GPU page fault, wedge or reset;
- every measured API request in the stable version matrices succeeded;
- the production DeepSeek model was restored after each experiment;
- Open WebUI remained active throughout the final deployment.

Normal ROCm queue-eviction messages appeared when large processes exited. They are not ring resets and should not be reported as one.

AMD's [ROCm 7.14 release notes](https://rocm.docs.amd.com/en/docs-7.14.0/about/release-notes.html) still list lower-than-expected LLM inference performance on RDNA 3, RDNA 4 and Ryzen AI MAX as a known issue. The [RDNA 3/4 optimisation guide](https://rocm.docs.amd.com/en/develop/reference/system-optimization/rdna3-5.html) remains the host baseline, but these results show that model-specific kernels and graph behaviour can dominate after the host is configured correctly.

## What I left running

| Component | Retained state |
| --- | --- |
| Lemonade | patched 11.5.2 active; rollback to 11.5.1 retained |
| production DeepSeek | specialised ROCmFP3 image restored, healthy and chat-tested |
| vLLM | 0.27.0 / ROCm 7.14 launcher staged for Qwen3.5-122B; service remains on-demand and disabled |
| upstream-style `llama.cpp` | b10362 qualified; HIP graphs required for DeepSeek decode |
| Open WebUI | unchanged and active at pinned 0.11.0 image |
| SGLang | unchanged at 0.5.17 |
| BF16 and quantised-KV patches | retained as isolated experimental builds |
| MTP, DFlash, old MoE patch and ROCmFPX | not deployed |

The custom ROCmFP3 DeepSeek backend is still pinned. Qualifying upstream b10362 does not magically rebase a separate quantisation and kernel stack. That work deserves its own build and correctness campaign rather than a version-label shortcut.

## What I will do for the next upgrade

The version updates were uneventful, which is a useful result. I would use the same sequence again:

1. Accept a release when the balanced before-and-after test stays inside the gate.
2. Repeat on the large model that matters, not only the convenient smoke model.
3. Match compile-time graph settings before blaming source code.
4. Run a reference or quality test before a fast kernel.
5. Treat deterministic divergence as a release blocker until explained.
6. Keep a rollback path and prove the production model after changing the daemon.

The production improvement I kept was not the 3.64x speculative result. It was the quieter Lemonade update that returned memory correctly, passed its tests and restarted the existing model cleanly.

The quantised-KV and BF16 work show real headroom in ROCm on Strix Halo. The failed Vulkan operation test, long-context MoE regression and speculative output mismatches show why that headroom still needs qualification.

For now, BF16 and quantised KV remain the two experiments worth revisiting. MTP and DFlash need an explanation for the output differences before I would put either in the stable lane.

Continue with the complete [Local LLMs on Strix Halo series](/series/strix-halo/), or read the preceding [five-model SGLang, vLLM and `llama.cpp` comparison](/blog/2026/08/10/sglang-vllm-llamacpp-evox3/).

*Benchmark date: 11 August 2026. Host: GMKtec EVO-X3, Ryzen AI MAX+ 395 / Radeon 8060S (`gfx1151`), 128GB unified memory, Ubuntu 24.04.4, kernel 6.17.0-40 and ROCm 7.14.60850. Candidate source identities and the retained comparison dataset are recorded above. Community claims are treated as hypotheses until reproduced on this host.*
