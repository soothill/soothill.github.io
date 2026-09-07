---
layout: post
title: "Qwen Vulkan PRs 28489 and 28501: below noise"
seo_title: "llama.cpp PR 28489 and 28501 on Strix Halo"
date: 2026-09-07 13:20:00 +0100
last_modified_at: 2026-09-07 13:20:00 +0100
permalink: /blog/2026/09/07/qwen38-vulkan-pr28489-pr28501-strix-halo/
categories: [local-ai, benchmarks, engineering]
tags: [qwen3.8, qwen4exp, llama-cpp, vulkan, strix-halo, lemonade, mixture-of-experts]
author: Darren Soothill
editorial_standard: soothill-human-v1
editorial_review_status: approved
editorial_reviewer: Darren Soothill
editorial_reviewed_at: 2026-09-07
series: "Local LLMs on Strix Halo"
series_order: 31
description: "I benchmark llama.cpp PR 28489 and PR 28501 with the 103.7 GiB Qwen3.8 Flash Next model on Strix Halo. Both are correct; neither is a production speed-up."
---

> **Test record:** I built exact base and head pairs for llama.cpp PR 28489 and
> PR 28501, then served the 103.7 GiB Qwen3.8 Flash Next Q4_K_XL model with my
> production 512K/two-slot profile. PR 28489 improved repeated 8K prefill by
> 1.1%. PR 28501 improved 8K by 0.3% and 32K by 0.26%. All retrieval checks
> passed, memory remained safe and neither result cleared my 5% materiality
> gate. I promoted nothing and restored the existing Lemonade service.

The shape of [PR 28501](https://github.com/ggml-org/llama.cpp/pull/28501) is
almost irresistible if you run Qwen3.8 Flash Next. The model has 512 experts.
The Vulkan path hoisted row IDs for no more than 256. Raise the limit to 512,
keep the lookup in shared memory and a sizeable prefill gain sounds plausible.

The pull request even arrived with useful Strix Halo figures: roughly 19% at
8K and 16% at 32K using Q5_K and batch 2,048. Those are large enough to test.
They are not large enough to copy into a production claim.

[PR 28489](https://github.com/ggml-org/llama.cpp/pull/28489) is subtler. It
makes Vulkan's MMVQ path choice independent of batch size, removing a special
`n > 1` route that can make speculative verification behave differently from
single-token decode. That reads primarily as correctness work, but a kernel
selection change can still move throughput in either direction.

On my EVO-X3, neither patch produced a noticeable speed-up.

## Why I did not patch the production binary

The current service uses the qualified Nathan Vulkan v0.7.1 build at llama.cpp
commit `39817c47`. That source predates the row-hoisting machinery changed by
PR 28501. Applying its three-line headline diff would therefore be a false
backport: I would have to pull in the prerequisite implementation and would no
longer be measuring one change.

I instead built each pull request twice, from its exact upstream base and
exact head:

| Pull request | Base | Head | State on 7 September |
| --- | --- | --- | --- |
| PR 28489, batch-independent MMVQ selection | `73a43d1f` | `ef94c091` | Open, non-draft, merge state blocked |
| PR 28501, 512-expert hoisted row IDs | `465e49b9` | `266464c8` | Open, draft, merge state blocked |

The four binaries used the same RADV Strix Halo userspace bundle, GCC 13.3 and
shaderc 2026.3. Their full source and binary hashes are in the [qualification
manifest](/assets/data/qwen38-vulkan-pr28489-pr28501-manifest-2026-09-07.json).
The old production binary was also served once as a sanity control, but I did
not attribute broad upstream differences to either patch.

## The production shape stayed fixed

Every arm used the same model and serving geometry:

```text
model                  Qwen3.8-Flash-Next-UD-Q4_K_XL
model size             103.688 GiB, four shards
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

I used deterministic requests with temperature zero, `top_k=1` and a fixed
seed. Each measured prompt received a distinct prefix and request-level prompt
caching was disabled. The server log had to show processing from 512 tokens
and 2% or 6% progress, rather than resuming from an earlier KV prefix.

That detail mattered. The first 8K request after model load was consistently
slower than the second full-token request on the other slot. The difference
was as large as 18%, even though the binary and token count had not changed.
Comparing a cold base with a warmed candidate would have manufactured a much
better story than the patch earned.

I therefore compared first request with first request and warmed request with
warmed request. The materiality rule was set before the run: a repeatable gain
above 5%, with correct output, safe memory and clean unload/reload.

## The paired result

| Change | Prompt | Base run 1 / run 2 | Head run 1 / run 2 | Median change |
| --- | ---: | ---: | ---: | ---: |
| PR 28489 | 8K | 77.74 / 91.68 tok/s | 78.36 / 92.94 tok/s | **+1.11%** |
| PR 28501 | 8K | 77.95 / 92.56 tok/s | 77.85 / 93.22 tok/s | **+0.32%** |
| PR 28501 | 32K | 84.55 / 88.17 tok/s | 85.03 / 88.13 tok/s | **+0.26%** |

The [complete paired
CSV](/assets/data/qwen38-vulkan-pr28489-pr28501-evox3-2026-09-07.csv)
contains the unrounded values and output hashes.

The individual deltas make the result clearer. PR 28489's two 8K pairs were
+0.8% and +1.4%. PR 28501's 8K pairs were -0.13% and +0.71%. Its 32K pairs
were +0.57% and -0.04%. None is close to a material improvement, and the signs
do not even stay positive in every PR 28501 pair.

The initial served screen told the same story outside prefill. PR 28489 moved
single-stream decode from 16.962 to 16.973 tokens per second and two-stream
aggregate throughput from 7.048 to 6.920. PR 28501's one decode sample moved
from 16.144 to 16.568 tokens per second, a 2.6% change below the gate and
outside the code path the patch is intended to improve. I did not turn that
single sample into a decode claim.

## PR 28489 is still useful correctness work

Removing batch size from MMVQ route selection makes sense. A verification
batch should not silently pick a different policy merely because it contains
more than one token. That is particularly relevant to speculative decoding.

My production Qwen3.8 Flash Next service deliberately has speculation disabled,
so the intended benefit is not exercised here. The served marker tests passed
and the generated explanations remained coherent, although exact greedy text
changed when the kernel route changed. Performance was noise-level.

One audit note belongs in the record. My attempted focused backend filter used
a test label that matched no cases, so I excluded it rather than claiming a
pass count. The served comparison is valid; there is no invented “16/16” test
result behind it. I would revisit PR 28489 as a correctness dependency if I
enable speculative decoding on this profile, not as a speed patch.

## PR 28501 depends on batch geometry

PR 28501 did execute the full Vulkan `MUL_MAT_ID` selection: 891 cases completed
successfully. The 512-expert model returned the exact 8K and 32K retrieval
markers on both base and head, with identical hashes across each pair.

The performance result does not contradict the pull request author's test. It
defines a narrower boundary. Their Q5_K run used batch 2,048. My production
service uses batch 512 and micro-batch 128 because it is balancing a 103.7 GiB
model, two 256K slots, Q8 KV and reliable unified-memory headroom. At that
geometry the larger hoisted table is not a useful end-to-end optimisation.

I could raise the batch merely to make the patch look better. That would be a
different production proposal with different latency, allocation and recovery
behaviour. It needs its own qualification; it is not evidence for changing the
current service.

## Memory and recovery stayed uneventful

The repeated PR 28489 pair peaked at 70.72 GiB of GTT and never fell below
47.86 GiB of available system memory. PR 28501 peaked at 70.83 GiB and stayed
above 46.20 GiB. No 18 GiB memory guard fired, no GPU reset or Vulkan device
loss appeared, and every private server unloaded cleanly.

After the final arm I removed the warmer inhibitor and verified the normal
idle state again: Qwen3.8 Flash Next ready and unpinned at 524,288 total
context, two slots, all 40 GPU layers, Q8 K/V, prompt caching and
`auto_evict=false`. The pinned qwen3.5 NPU helper was also ready. The residency
warmer and guard timer remained enabled and active.

No production model file, binary, recipe or Lemonade option changed.

## The production decision

Neither pull request is a production performance candidate for this profile.

I would carry PR 28489 with a future speculative-decoding correctness update
once its upstream state settles. I would reconsider PR 28501 if the service
moves to a larger batch and the draft pull request matures. Today, +1.1%,
+0.3% and +0.26% are not benefits a user will notice, and they do not justify
replacing a qualified runtime.

The useful result is the negative one. The 512-expert patch has a plausible
mechanism and impressive numbers in a neighbouring configuration. Matching
the actual batch, micro-batch, quantisation and residency policy turns that
headline into noise.

## Where I would stop claiming

This is a one-host, two-repeat performance qualification. It exercises 8K and
32K full-token prefill, a deterministic decode screen, two-slot serving,
output markers, memory guards and recovery. It is not a perplexity comparison,
a 262K prefill result, a speculative-decoding test or a multi-day production
soak.

It does not show that either patch is useless on another GPU or batch size. It
shows that neither delivers a material, safe performance improvement for my
current EVO-X3 Qwen3.8 Flash Next service.

*Benchmarked 7 September 2026 on a GMKtec EVO-X3 with Ryzen AI MAX+ 395,
Radeon 8060S and 128 GiB unified memory. Lemonade 11.9.0; Qwen3.8 Flash Next
UD-Q4_K_XL; 524K context; two slots; Q8 K/V; Vulkan. Nothing was promoted.*
