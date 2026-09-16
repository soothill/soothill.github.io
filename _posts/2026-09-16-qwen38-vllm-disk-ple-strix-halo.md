---
layout: post
title: "Qwen3.8 in vLLM: the 95 GiB table stays on disk"
seo_title: "Qwen3.8 Flash Next in vLLM on 128 GB Strix Halo"
date: 2026-09-16 14:20:00 +0100
last_modified_at: 2026-09-16 14:20:00 +0100
permalink: /blog/2026/09/16/qwen38-vllm-disk-ple-strix-halo/
categories: [local-ai, benchmarks, engineering]
tags: [qwen3.8, vllm, rocm, strix-halo, lemonade, llama-cpp, unified-memory]
author: Darren Soothill
editorial_standard: soothill-human-v1
editorial_review_status: approved
editorial_reviewer: Darren Soothill
editorial_reviewed_at: 2026-09-16
series: "Local LLMs on Strix Halo"
series_order: 32
description: "Qwen3.8 Flash Next runs in vLLM on my 128 GB Strix Halo with disk-backed embeddings. At 32K, first output falls from 306 to 81 seconds."
---

> **Test record:** Qwen3.8 Flash Next served successfully in an experimental
> AMD vLLM build on my 128 GB EVO-X3. Its 95.4 GiB BF16 embedding table stayed
> on NVMe; requested rows were copied exactly. At 32K input, repeated
> single-request first output fell from 306.42 seconds under llama.cpp/Vulkan
> to 81.04 seconds. Both deployments passed 27/27 retrieval checks. vLLM kept
> at least 44.35 GiB available during requests, with no measured swap-out in
> that phase. I restored the existing Lemonade GPU and NPU services afterwards.

My [earlier Qwen3.8 ROCm and Vulkan work](/blog/2026/08/27/qwen38-flash-next-rocm-vulkan-strix-halo/)
left a useful question open. Vulkan could run the model, but could vLLM make
long prompts less painful on the same machine?

“Faster than Lemonade” is too loose a description. Lemonade manages the
service. The production inference engine underneath it is llama.cpp, using
Vulkan and a 103.7 GiB GGUF. For this test I needed a working native vLLM
checkpoint, a memory plan and a measured comparison against that deployment.

The first obstacle arrived before any tokens per second. The four-bit
checkpoint did not fit in 128 GB.

## Four-bit experts do not make a four-bit model

I used [wtdcode's native AWQ W4A16 checkpoint, pinned to revision
0939125b](https://huggingface.co/wtdcode/Qwen3.8-Flash-Next-AWQ-W4A16/tree/0939125b929543a783ce700c90e36dd1a575c00c).
Its routed experts are INT4, with symmetric groups of 128. Other weights,
including the PLE n-gram embedding table, remain BF16.

Reading the safetensors headers gave the actual storage budget:

| Component | Stored size |
| --- | ---: |
| Text backbone | 67.225 GiB |
| BF16 PLE table | 95.368 GiB |
| Vision tower | 0.836 GiB |
| MTP head | 4.856 GiB |

The backbone and PLE alone total about 162.6 GiB. Linux sees approximately
124 GiB on this 128 GB machine. There is no allocation flag that closes that
gap while also leaving room for KV cache and runtime workspaces.

CPU offload does not solve this capacity problem on Strix Halo. The CPU and
Radeon 8060S share physical memory. The 120 GiB GTT allowance and 1 GiB
dedicated reservation are not another 121 GiB of RAM sitting beside it.

The PLE table is the interesting part: 320,001,536 rows, each containing 160
BF16 values. A lookup needs selected rows, not a resident copy of every row.
That made it a candidate for a disk-backed implementation.

## Keeping the table on NVMe

The experimental module reads the safetensors headers, validates all 128
shards and maps them read-only. For each lookup it copies the requested IDs
to the CPU, deduplicates them, gathers the rows and transfers the result to
the GPU. It never creates the full embedding parameter.

There is no new quantisation of this table. The gather copies the original
BF16 bit patterns. Synthetic CPU and GPU tests covered duplicate IDs, shard
boundaries and empty inputs. Six sampled rows from the real checkpoint also
matched the corresponding safetensors slices exactly.

After a gather, the module releases the mapped resident pages. Linux can
still retain useful clean pages in its reclaimable file cache. “On disk”
therefore does not mean every lookup must fetch every byte from the SSD again.
That distinction matters when interpreting repeated-prompt results.

The price is synchronisation. This implementation moves IDs through the CPU
and does filesystem work. It requires a single rank and eager execution;
GPU graph capture is unsupported. I accepted those restrictions to establish
whether the full text backbone could run within the memory budget.

Vision and MTP were disabled. The text backbone and routed expert count were
retained: 48 layers, 512 experts and 10 selected experts per token.

## Three compatibility problems before the first answer

I started from the existing [AMD Flash Next vLLM development
work](https://github.com/vllm-project/vllm/pull/53896), copying the tree at
`d4d0f73ef171154eac6f1914dca47001d662cfbb` into an isolated workspace.
This was an adaptation of a development build, with existing gfx1151 compiled
extensions, rather than a clean installation of a released wheel.

First, AMD-SMI returned no device handles even though Torch/HIP could see the
GPU. A fallback to HIP device discovery and naming got past that mismatch.

Second, the full model stopped at a QSA constructor check for dense
FlashAttention. The actual AMD sparse-attention forward path uses its own
Triton kernel. Removing the redundant availability check let that path run;
all ten existing AMD QSA tests passed.

Third, a representative-shape fixture exposed the inherited KV cache updater.
Its implementation had only been imported when optional FlashAttention was
installed. The AMD path now calls the existing native cache scatter operation
directly. An exact test across cache block boundaries passed before I tried
the full model again.

These were specific compatibility fixes. I did not replace the sparse
attention calculation with a dense approximation.

The successful smoke run loaded in about 70 seconds, with vLLM reporting
68.03 GiB for model loading. Multiplication, exact label retrieval and an
ordinary explanation all worked. That was enough to begin a benchmark, not
enough to declare the model qualified for every task.

## What I compared

The host was a GMKtec EVO-X3 with Ryzen AI Max+ 395, Radeon 8060S and 128 GB
of shared memory, running Ubuntu 24.04.4 and kernel 6.17.0-40-generic. The
vLLM environment used ROCm 7.14, Torch 2.11.0 and Triton 3.7.1 development
builds, with Transformers 5.14.1.

The two serving profiles deliberately expose the deployment difference:

| Setting | Experimental vLLM | Existing llama.cpp/Vulkan route |
| --- | --- | --- |
| Checkpoint | Native AWQ W4A16 | UD-Q4_K_XL GGUF |
| Text backbone placement | GPU | Existing 40 GPU layers |
| PLE | BF16 rows gathered from disk | CPU memory-mapped GGUF path |
| KV format | BF16 | Q8 |
| Context per sequence | 33,280 | 33,280 |
| Sequences / slots | 2 | 2 |
| Prefill batch | 256 | 512, micro-batch 128 |
| Prefix reuse / speculation | Disabled | Disabled |

vLLM had a 4 GiB KV budget. The Vulkan arm used the existing qualified
v0.7.1 binary. I reduced its normal two 262,144-token slots to the comparison
size and disabled its host prompt cache. The NPU helper was unloaded during
both arms.

Each engine received identical input token IDs at 512, 8,192 and 32,768
tokens, with one or two simultaneous clients. Three tokenizer probes covering
the benchmark prose and control tokens matched between the native tokenizer
and GGUF backend.

The prompt placed a unique label near the beginning, followed by repeated
records, then asked for the label and an explanation. Sampling was greedy,
with a fixed seed and a 128-token output cap. Responses could finish early.
All 27 requests per engine returned the expected label; neither completed
matrix had an HTTP failure.

Each length/concurrency case had three waves. The tables below use waves one
and two, retaining wave zero separately because it can include first-use
compilation or colder pages. Startup checks warmed common paths, but there
was no separate warmup for every shape. Two repeats give descriptive results,
not a confidence interval.

## The first-output difference is substantial

| Input tokens | vLLM first output | Vulkan first output | TTFT ratio | vLLM output tok/s | Vulkan output tok/s |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 512 | 1.47 s | 4.54 s | 3.08× | 13.34 | 17.31 |
| 8,192 | 19.70 s | 68.96 s | 3.50× | 13.05 | 14.75 |
| 32,768 | 81.04 s | 306.42 s | 3.78× | 13.62 | 12.17 |

<img src="/assets/images/qwen38-vllm-single-request-20260916.png" alt="First-output latency and generation rate for a single request at three input lengths" width="2160" height="954" loading="lazy">

At 32K, waiting about 81 seconds instead of just over five minutes changes
the usefulness of the service. The repeated median full-request time was
90.36 seconds for vLLM and 316.86 seconds for Vulkan.

Short prompts tell a less convenient story. vLLM begins sooner, but Vulkan
generates faster once it starts: 17.31 against 13.34 tokens per second at
512 input tokens. The same ordering holds at 8K. I would not turn the
first-output result into a blanket claim that vLLM decodes faster.

The output rates are approximate streamed measurements: generated tokens
minus one, divided by time after the first non-empty output chunk. Chunking
and end-of-sequence accounting can differ between backends.

## Two clients still pay for prefill

| Input tokens | vLLM median first output | Vulkan median first output | vLLM aggregate tok/s | Vulkan aggregate tok/s |
| ---: | ---: | ---: | ---: | ---: |
| 512 | 2.22 s | 9.09 s | 19.01 | 13.65 |
| 8,192 | 29.90 s | 111.09 s | 4.58 | 1.29 |
| 32,768 | 122.87 s | 471.87 s | 1.39 | 0.40 |

<img src="/assets/images/qwen38-vllm-aggregate-20260916.png" alt="Aggregate completion throughput including prompt processing, for one and two clients" width="2160" height="936" loading="lazy">

These first-output medians combine the earlier and later requests in each
pair. Long prefills queue substantially on one GPU. Aggregate throughput
counts actual generated tokens over the whole wave, including prompt
processing; it is not the sum of two decode speeds. A request's output
interval can also contain pauses while the scheduler prefills its neighbour.

The unrounded [measurement summary](/assets/data/qwen38-vllm-summary-20260916.json)
includes the first waves, completion counts and memory counters. The
[run manifest](/assets/data/qwen38-vllm-manifest-20260916.json) records the
checkpoint, source revision, runtime and comparison settings.

## The memory guard caught a startup I needed to inspect

| Deployment | Minimum available RAM during requests | Startup swap-out | Request-phase swap-out |
| --- | ---: | ---: | ---: |
| vLLM | 44.35 GiB | 3.55 MiB | 0.00 MiB |
| llama.cpp/Vulkan | 56.82 GiB | 404.56 MiB | 1.48 MiB |

My first Vulkan baseline attempt stopped at a conservative 64 MiB startup
swap-out guard, despite roughly 78 GiB still being available. I retained the
failed run and allowed 512 MiB during the baseline's retry startup. The
10 GiB available-memory floor and separate 64 MiB request-phase guard stayed
in place.

That successful startup moved 404.56 MiB out to swap. The subsequent request
matrix moved only 1.48 MiB. These are system-wide counters, including unrelated
pages; they do not demonstrate that the model itself was being swapped.
Available memory also includes reclaimable cache. Startup reclamation and
sustained inference-time paging need separate treatment.

The available kernel journal for the trial window contained no matched GPU
fault, reset or timeout events. The controller restored the original services,
and the four recorded production configuration hashes were unchanged.

## The production decision

I now have a working vLLM text deployment and a strong reason to investigate
it for prompt-heavy work. I have not replaced the production service.

The existing [Vulkan production profile](/blog/2026/08/28/qwen38-vulkan-071-q8-dual-slot-production/)
serves much larger context slots than this experiment qualified. Its short
prompt generation is also faster in this matrix. A 32K latency win is useful,
but it does not establish equivalent context capacity or broad model quality.

The original Lemonade GPU model and pinned NPU helper were both ready again
after the tests. Simultaneous vLLM and NPU inference remains untested here;
the helper was unloaded for the comparison. Memory headroom alone is not a
concurrency qualification.

The next useful work is a broader quality screen, more varied long prompts
and a less synchronous PLE lookup path. Larger prefill batches also deserve
measurement. None of those prospective improvements is included in today's
numbers.

## Where I would stop claiming

This is a comparison of two deployments. Quantisation, KV format, layer
placement, scheduling and kernels all differ. It cannot isolate an
engine-only vLLM advantage, and it is not an exhaustive tuning contest.

Repeated filler exercises retrieval but gives a narrow view of PLE row
locality. It does not establish worst-case cold NVMe behaviour on diverse
text. Exact embedding lookup tests and 27/27 markers do not prove equal
coding, reasoning or multilingual quality.

The result is text-only, single-rank, eager execution, without MTP. Inputs
stop at 32,768 tokens. It depends on a patched development tree and reused
compiled extensions, so it is not a claim of stock-wheel support or a fresh
Linux build recipe.

What it does establish is concrete: the native text model can run within
this machine's memory by leaving the BF16 table on disk, and this particular
vLLM deployment starts answering the measured long prompts much sooner.

*Benchmarked 16 September 2026 on a GMKtec EVO-X3 with Ryzen AI Max+ 395,
Radeon 8060S and 128 GB unified memory. Source changes, failed startups,
streamed responses and recovery records were retained. Production was restored.*
