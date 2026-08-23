---
layout: post
title: "DeepSeek V4 Flash on Strix Halo: tuning ROCm, matching Vulkan"
seo_title: "DeepSeek V4 Flash: ROCm vs Vulkan on Strix Halo"
date: 2026-08-09 16:00:00 +0100
last_modified_at: 2026-08-09 16:00:00 +0100
permalink: /blog/2026/08/09/deepseek-v4-flash-vulkan-rocm-strix-halo/
categories: [local-ai, benchmarks, engineering]
tags: [deepseek-v4, llama-cpp, vulkan, rocm, strix-halo, gfx1151]
author: Darren Soothill
editorial_standard: soothill-human-v1
editorial_review_status: approved
editorial_reviewer: Darren Soothill
editorial_reviewed_at: 2026-08-17
series: "Local LLMs on Strix Halo"
series_order: 8
description: "Matched DeepSeek V4 Flash tests on Strix Halo show a 44% ROCm prefill gain from tuning, but patched Vulkan still wins all four llama.cpp workloads."
image: "/assets/images/deepseek-v4-flash-rocm-vulkan-strix-halo-og.png"
image_alt: "DeepSeek V4 Flash ROCm versus Vulkan benchmark card in the Soot and Silicon visual style"
image_type: image/png
---

> **Test record:** I repeated the DeepSeek V4 Flash Vulkan-versus-ROCm comparison on `evox3`, a Ryzen AI MAX+ 395 / Radeon 8060S (`gfx1151`) system with 128GB unified memory. The model was the same 97.05GiB four-shard `UD-IQ3_XXS` GGUF. ROCm 7.14 gained **44.3%** in shallow prompt processing after moving from a 512 to 2,048 micro-batch, but an equally configured patched Vulkan build still finished ahead in all four tests: by **11.5% to 47.9%**. Both final runs exited cleanly, and the captured kernel log contained no timeout, `DeviceLost`, wedge or reset.

I started with a result that appeared to show Vulkan ahead of ROCm on three of four DeepSeek V4 Flash tests. Then ROCm tuning seemed to change the answer. Matching that tuning on Vulkan changed it again.

That is the useful part of this benchmark. The final table matters, but so does the sequence: a backend comparison can be technically reproducible and still be unfair because one ordinary runtime setting was left at its default on only one side.

## The original result and the question it left open

The original test came from an ASUS PX13 running Fedora 44 on the same Strix Halo GPU architecture. Its Vulkan build included a `LIGHTNING_INDEXER` implementation that avoided the DeepSeek V4 fallback behind [`llama.cpp` issue #25664](https://github.com/ggml-org/llama.cpp/issues/25664). Without that operator, the fallback performs a permute and contiguous copy with a pathological access pattern; at sufficient depth, the work can exceed the AMD compute-ring watchdog and end in `vk::Queue::submit: ErrorDeviceLost`.

The patched Vulkan run completed instead of losing the device. Its published numbers were:

| Test | Original Vulkan | Original ROCm | Faster backend |
| --- | ---: | ---: | --- |
| shallow pp2048 | **124.16** | 114.37 | Vulkan |
| shallow tg64 | **18.15** | 13.27 | Vulkan |
| d24576 pp2048 | 63.67 | **74.31** | ROCm |
| d24576 tg64 | **14.36** | 9.25 | Vulkan |

All rates in this article are tokens per second. The original post identified Vulkan build 867 at revision `4a1fb6c` and ROCm build 824 at `cd0fa60`. It did **not** state the ROCm userspace version, so those ROCm numbers cannot honestly be labelled “ROCm 7.14”. My tests below did use ROCm **7.14.60850**.

The original Vulkan patch set is available in the author's [`vk-indexer-plus-hc` branch](https://github.com/neuromaniacMD/llama.cpp/tree/vk-indexer-plus-hc); the indexer-only version is in [`vk-lightning-indexer`](https://github.com/neuromaniacMD/llama.cpp/tree/vk-lightning-indexer). The published result tested all three patches together, so it was evidence for the combined result rather than an isolation test of any one patch.

## Repeating it on `evox3`

My host differs from the original machine in enough ways that I treat this as a reproduction, not a pooled dataset:

| Component | Original ASUS PX13 | My `evox3` |
| --- | --- | --- |
| Processor / GPU | Strix Halo / Radeon 8060S | Ryzen AI MAX+ 395 / Radeon 8060S |
| Memory | 128GB unified | 128GB unified |
| Operating system | Fedora 44 | Ubuntu 24.04.4 |
| Kernel | 7.1.5-201.fc44 | 6.17.0-40 |
| Mesa | 26.1.5 | 25.2.8 |
| ROCm | not stated | 7.14.60850 |
| VRAM / GTT policy | 512MiB / 120GB GTT | 1GiB / 120GiB GTT |

Both machines used `-mmp 0`. At roughly 99GiB loaded, memory mapping can cause the page cache and GPU-visible allocation to compete for the same unified memory budget. This is a capacity requirement on these configurations, not a throughput tweak.

My first run retained the default 512 micro-batch and used one measured repetition. Vulkan was the patched `d93e2df7` build 10329; ROCm was `cd0fa605` build 10286 under ROCm 7.14.

| Test | Initial Vulkan | Initial ROCm | Faster backend |
| --- | ---: | ---: | --- |
| shallow pp2048 | 138.99 | **142.68** | ROCm |
| shallow tg64 | **18.93** | 14.19 | Vulkan |
| d24576 pp2048 | **94.53** | 89.58 | Vulkan |
| d24576 tg64 | **16.19** | 11.23 | Vulkan |

The shape was familiar: Vulkan led generation, while prompt processing was closer and changed with depth. The important next question was whether ROCm had unused headroom in configuration or whether the gap sat inside the quantised kernels.

## The ROCm settings that mattered

The safe ROCm configuration was simple:

```text
-fa on -ub 2048 -mmp 0
```

Flash attention remained enabled, the micro-batch rose from 512 to 2,048, memory mapping stayed off, and HIP graph behaviour remained at its default. The one-repetition screen was:

| ROCm setting | shallow pp | shallow tg | deep pp | deep tg |
| --- | ---: | ---: | ---: | ---: |
| FA on, ubatch 512 | 144.08 | 14.01 | 89.61 | 11.47 |
| FA on, ubatch 1,024 | 187.10 | 14.59 | 110.04 | 11.22 |
| FA on, ubatch 2,048 | **212.45** | **14.52** | **113.35** | **11.38** |
| FA off, ubatch 512 | 127.88 | 12.43 | 81.53 | 5.65 |
| FA off, ubatch 1,024 | 168.78 | 12.66 | 93.36 | 5.57 |

After qualification over three repetitions, 2,048 versus the fresh 512 screen improved shallow prefill by **44.3%**, shallow generation by **5.6%**, and deep prefill by **25.0%**. Deep generation was 3.9% lower, within a notably noisy measurement. Disabling flash attention was a clear loss and nearly halved the deep generation rate.

Changing graph behaviour did not produce a meaningful win:

| HIP graph mode at ubatch 2,048 | pp2048 | tg64 | Decision |
| --- | ---: | ---: | --- |
| default | 207.87 ± 0.54 | 14.79 ± 0.46 | keep |
| disabled | 208.11 ± 0.29 | 14.95 ± 0.27 | difference too small |
| `GGML_CUDA_GRAPH_OPT=1` | 209.21 ± 0.33 | 14.70 ± 0.41 | no meaningful gain |

At this point, comparing tuned ROCm with the earlier Vulkan default would have made ROCm look decisively faster at both prompt-processing tests. It would also have been the wrong comparison.

## Match the micro-batch and the result changes

I repeated Vulkan at the same 2,048 micro-batch. The common arguments were:

```text
-ngl 99 -p 2048 -n 64 -ub 2048 -r 3 -mmp 0
```

ROCm used `-fa on`; the Vulkan build accepted `-fa 1`. The deep tests added `-d 24576`. Both used the same four model shards, the same host power policy, and no speculative decoding.

The final matched result was:

| Test | ROCm 7.14, tuned | Vulkan, matched | Vulkan advantage |
| --- | ---: | ---: | ---: |
| shallow pp2048 | 207.87 ± 0.54 | **231.84 ± 0.55** | 11.5% |
| shallow tg64 | 14.79 ± 0.46 | **18.90 ± 0.03** | 27.8% |
| d24576 pp2048 | 112.01 ± 0.68 | **131.47 ± 0.33** | 17.4% |
| d24576 tg64 | 11.02 ± 0.76 | **16.30 ± 0.01** | 47.9% |

The tuned ROCm gain is real. So is the Vulkan win. A larger micro-batch substantially accelerated prefill on both backends, and the matched Vulkan build led all four workloads.

Here is the complete progression in one place:

| Test | Original Vulkan | Original ROCm | `evox3` initial Vulkan | `evox3` initial ROCm | `evox3` final Vulkan | `evox3` final ROCm |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| shallow pp2048 | 124.16 | 114.37 | 138.99 | 142.68 | **231.84 ± 0.55** | 207.87 ± 0.54 |
| shallow tg64 | 18.15 | 13.27 | 18.93 | 14.19 | **18.90 ± 0.03** | 14.79 ± 0.46 |
| d24576 pp2048 | 63.67 | 74.31 | 94.53 | 89.58 | **131.47 ± 0.33** | 112.01 ± 0.68 |
| d24576 tg64 | 14.36 | 9.25 | 16.19 | 11.23 | **16.30 ± 0.01** | 11.02 ± 0.76 |

Those six columns are three comparison stages, not six interchangeable samples. The original figures come from another chassis and software stack. The initial `evox3` numbers use `ubatch=512` and one repetition. Only the final pair is the three-repetition, same-host, same-setting backend comparison.

## Why I did not keep a ROCm kernel patch

Configuration tuning improved prompt processing, but it did not explain the remaining generation gap. I profiled the exact IQ3_XXS matrix-vector shape used by this model: `m=4096,n=1,k=14336`.

`rocprofv3` attributed **98.62%** of kernel-dispatch time to `mul_mat_vec_q`; `quantize_q8_1` accounted for the remaining 1.38%. The unprofiled upstream microbenchmark took 122.09µs per call. That is a strong signal to work on the quantised matrix-vector kernel, but a strong signal is not the same as an easy win.

| IQ3_XXS candidate | Time | Outcome |
| --- | ---: | --- |
| upstream: one wavefront, one row | 122.09µs | baseline |
| two wavefronts | 123.25µs | 1.0% slower |
| four wavefronts | 137.60µs | 12.7% slower |
| stage IQ3 grid in shared memory | 121.67µs A/B mean | 0.7% apparent gain; below noise threshold |
| two rows per block | 123.01µs | 0.8% slower |
| four rows per block | 133.04µs | 9.0% slower |

Every candidate passed all 11 IQ3_XXS CPU-reference cases. Extra wavefronts and rows nevertheless increased lookup or register pressure enough to lose performance. Shared-memory staging occasionally won, then reversed direction in several paired trials. I rejected it rather than retaining a fragile change that I could not distinguish from noise.

The practical outcome is that there is no local ROCm kernel patch behind these published results. The isolated worktree was returned to pristine upstream and rebuilt successfully.

## Correctness and stability came before the score

The Vulkan indexer patch exists because “fast until the driver kills the context” is not a usable result. I applied the same standard to the ROCm experiments:

- `LIGHTNING_INDEXER` passed 144 of 144 supported ROCm cases in normal asynchronous mode and again with `HIP_LAUNCH_BLOCKING=1`;
- the DeepSeek host-combine operators plus `CONT` passed 48 of 48 cases in both modes;
- every IQ3_XXS kernel candidate passed 11 of 11 CPU-reference tests;
- the final ROCm and Vulkan benchmark commands both exited zero;
- the captured kernel log contained no ring timeout, `DeviceLost`, wedge or GPU reset.

I did not change clocks, firmware, the kernel, the memory split or the ROCm installation during this work. That matters because changing the platform under the benchmark can turn a tuning exercise into an attribution problem.

## What I would run

For this particular DeepSeek V4 Flash `UD-IQ3_XXS` GGUF, the patched Vulkan build is the faster `llama.cpp` path on `evox3`. It wins prompt processing and generation at both tested depths. ROCm 7.14 remains stable and materially better with `-ub 2048`, but configuration alone does not overtake Vulkan.

That does not make ROCm the wrong production backend. My specialised ROCmFP3 service, restored after the benchmark with the same model profile and options, returned the deterministic smoke output `BENCHMARK RESTORE OK` at 24.9 decode tokens per second. It is not an apples-to-apples comparison with upstream `llama.cpp`, a different quantisation and a patched Vulkan build, but it remains the practical production route when I want more decode throughput from this model on this machine.

So I keep both paths:

| Requirement | Current choice |
| --- | --- |
| Fastest tested upstream-style GGUF path for this model | patched Vulkan `llama.cpp` |
| Simple upstream ROCm GGUF path | ROCm 7.14 with `-fa on -ub 2048 -mmp 0` |
| Production DeepSeek serving with the highest observed decode | specialised ROCmFP3 service |
| Diagnosing another Vulkan `DeviceLost` case | test the indexer path, depth, parallelism and kernel log rather than assuming one universal cause |

The last row is important. Another report still crashed with a related patch applied on different hardware, a Gemma model and `--parallel 5`. The DeepSeek fallback fixed here is a concrete failure mode, not proof that every Vulkan device loss shares one cause.

My earlier [Vulkan-versus-ROCm article](/blog/2026/08/03/llamacpp-vulkan-vs-rocm-strix-halo/) concluded that backend choice was model- and phase-specific. DeepSeek V4 Flash makes the same point more sharply: it is also **configuration-specific**. Tune one side, then carry the winning setting across the boundary before declaring a winner.

The numbers changed twice. The disciplined conclusion changed only once the comparison stopped moving.

*Benchmark date: 9 August 2026. Model revision `fbbb5b93`; patched Vulkan build 10329 at `d93e2df7`; initial ROCm build 10286 at `cd0fa605`; final upstream ROCm build 10333 at `08659901c`; ROCm userspace 7.14.60850. All `evox3` figures come from retained same-machine benchmark and profiler artefacts.*
