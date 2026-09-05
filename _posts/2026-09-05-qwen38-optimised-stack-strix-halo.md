---
layout: post
title: "Two draft changes delivered most of Qwen3.8's stack gain"
seo_title: "Qwen3.8 optimised stack tested on Strix Halo"
date: 2026-09-05 15:50:00 +0100
last_modified_at: 2026-09-05 15:50:00 +0100
permalink: /blog/2026/09/05/qwen38-optimised-stack-strix-halo/
categories: [local-ai, benchmarks, engineering]
tags: [qwen3.8, dflash2, llama-cpp, vulkan, rocm, hip, strix-halo, speculative-decoding]
author: Darren Soothill
editorial_standard: soothill-human-v1
editorial_review_status: approved
editorial_reviewer: Darren Soothill
editorial_reviewed_at: 2026-09-05
series: "Local LLMs on Strix Halo"
series_order: 30
description: "I isolate five Qwen3.8 27B optimisations on Strix Halo. Two improve the current Vulkan stack; IQ4 main and TOP_K do not."
---

> **Test record:** I reproduced the useful parts of a community Qwen3.8 27B
> recipe on a 128 GiB EVO-X3. The smaller IQ4_XS draft model and a draft width
> of three improved generated-token speed by up to 75% over my current profile.
> The IQ4_XS main model was a mixed regression, the TOP_K patch was noise-level,
> and retained PM4 added a smaller 3.4–4.3% decode gain. Nothing was promoted to
> production during this test.

A fast screenshot is not the same thing as a useful upgrade. The
[`Qwen3.8 27B on Strix: the optimized setup`](https://www.reddit.com/r/StrixHalo/comments/1w7wsfx/qwen38_27b_on_strix_the_optimized_setup/)
post combines a new main quantisation, a smaller DFlash model, a different
draft policy, a patched ROCm runtime, a new TOP_K kernel and retained PM4 HIP
graphs. The reported result is interesting, but changing that many things at
once does not say which part earned its place.

I split the recipe into five changes and measured each one against the
configuration immediately before it. Two are useful on my existing Vulkan
runtime. One is a plausible canary. Two do not justify a change.

The more important finding is that the safer combination already reaches 28.7
generated tokens per second on a short prompt and 26.4 at 8K. The complete
custom ROCm stack reaches 27.1 and 26.7 respectively. I do not need to replace
the serving runtime to obtain most of the practical gain.

## What I used as the baseline

The comparison starts with the 27B profile currently registered on my EVO-X3,
not a newly assembled reference configuration:

- `ROCMFPX-MQ-Q4.gguf` as the main model, 15,719,027,872 bytes;
- `Qwen3.8-27B-DFlash2-Q8_0.gguf` as the draft model, 2,056,414,816 bytes;
- the hardened Vulkan llama.cpp build used by the existing profile;
- 262,144-token context, one slot, batch 2,048 and micro-batch 256;
- Q8_0 K and V caches, flash attention and no prompt cache;
- DFlash width seven with a draft probability floor of 0.9.

The candidate files came from
[`ilintar/qwen3.8-27b-gguf-strix-halo`](https://huggingface.co/ilintar/qwen3.8-27b-gguf-strix-halo/tree/96c04f96a641f25e56deb3cadefe5399e6b7960b)
at revision `96c04f96`:

| Candidate | Bytes | SHA-256 |
| --- | ---: | --- |
| `Qwen3.8-27B-IQ4_XS-ALL-IMATRIX-Q8-OUT-MTP.gguf` | 16,110,851,680 | `9e5f86c7…6324` |
| `Qwen3.8-27B-DFlash2-IQ4_XS.gguf` | 1,038,313,376 | `11c78480…445` |

For the runtime tests I built the author's ROCm fork at
[`c4b77ac5`](https://github.com/pwilkin/rocm-systems/commit/c4b77ac5cb2879f9dd1f839fac9908b1f5975d64)
and two versions of the llama.cpp fork: pre-TOP_K
[`c20179e0`](https://github.com/pwilkin/llama.cpp/commit/c20179e0814cf8b00191b16d948110b962602e46)
and TOP_K head
[`d3b5cc43`](https://github.com/pwilkin/llama.cpp/commit/d3b5cc43d1fcfce891f2de94d5274ee40eceb21c).
The candidate binaries and runtime libraries were private copies. I did not
replace any production file.

## Why I ran two benchmark passes

Each arm used the same source-code prompt at approximately 512, 8,192 and
31,497 tokens, produced two samples in palindrome order, and generated 256
tokens for the deterministic pass or 128 for the sampler-active pass. The
server was unloaded between arms. I recorded prompt and generation timing,
draft acceptance, output hashes, `MemAvailable`, GTT, VRAM, major faults and
swap activity.

The deterministic pass used temperature zero, `top_k=1` and seed 12345. It
checked stable output and exposed an awkward behavioural difference: my
hardened production build deliberately suppresses DFlash for greedy hybrid
requests, while the community fork still drafts. Its apparent two-times greedy
decode advantage is therefore not an exact runtime-only comparison.

The second pass used a fixed sampler: temperature 0.7, `top_k=20`, `top_p=0.8`
and seed 12345. DFlash was active on both builds. This is the pass I use for the
speculative-decoding conclusions below. Across both passes, all 54 measured
workload summaries were non-empty and passed the repetition check.

## The result by change

The table shows median generated tokens per second. Percentages compare each
row with its proper matched control, not always with production.

| Arm | 512 | 8K | 31.5K | What changed |
| --- | ---: | ---: | ---: | --- |
| Current production profile | 16.44 | 18.31 | 17.44 | Q8 draft, width 7, floor 0.9 |
| Floor 0.1 control | 21.80 | 24.10 | 15.20 | +32.6%, +31.6%, **−12.8%** vs production |
| **1. IQ4_XS draft** | 21.96 | 27.08 | 18.25 | +0.7%, +12.4%, +20.0% vs Q8 at floor 0.1 |
| **2. Width three** | 26.57 | 26.99 | 18.67 | +21.8%, +12.0%, +22.8% vs width 7 at floor 0.1 |
| IQ4_XS draft + width three | **28.69** | **26.39** | 19.59 | +31.6%, +9.5%, +28.8% vs floor 0.1 control |
| **3. IQ4_XS main model** | 21.35 | 21.93 | 21.25 | **−25.6%, −16.9%**, +8.5% vs the combined Vulkan arm |
| ROCm fork before TOP_K | 25.77 | 24.80 | 21.87 | Runtime bridge for the next two tests |
| **4. TOP_K patch** | 26.01 | 25.64 | 21.88 | +0.9%, +3.4%, +0.03% |
| **5. Retained PM4** | 27.12 | 26.69 | **22.62** | +4.3%, +4.1%, +3.4% |

[Download the complete CSV](/assets/data/qwen38-strix-optimised-stack-evox3-2026-09-05.csv)
or [inspect the JSON record](/assets/data/qwen38-strix-optimised-stack-evox3-2026-09-05.json),
which includes all three prompt depths, both benchmark modes, acceptance,
memory summaries, revisions and artifact hashes.

## The probability floor was not a free win

The Reddit configuration uses a draft probability floor of 0.1, so I measured
that before changing a model file. It was spectacular on two prompts and poor
on the third.

At 512 and 8K, the lower floor increased decode by roughly 32%. At 31.5K it
fell by 12.8%. The reason is visible in the counters. Production's 31.5K pair
accepted 124 of 125 high-confidence drafts, or 99.2%. The 0.1-floor pair made
678 proposals and accepted only 155, or 22.9%. More speculation became more
wasted work.

That is not an argument for keeping 0.9 forever. It is an argument against
turning one prompt's best setting into a global default. Any production policy
needs a mixed prompt suite, not just an average.

## The two useful changes are on the draft side

The 1.04 GB IQ4_XS drafter is about half the size of the current 2.06 GB Q8_0
file. At the same width and probability floor it improved 8K decode by 12.4%
and 31.5K by 20.0%. It also reduced peak GTT by about 0.96 GiB in the matched
deterministic arm.

Width three helped even more consistently. Against width seven with the same
Q8 draft, it improved decode by 12.0–22.8% and removed about another 0.59 GiB
of rollback-state GTT. The narrower run made fewer speculative proposals and
accepted a much larger share of them.

Together, the smaller draft and width three peaked at 24.16 GiB of GTT rather
than the baseline's 25.70 GiB. Relative to the actual production sampler
profile, their median decode was 74.5% faster at 512 tokens, 44.1% at 8K and
12.3% at 31.5K. Deterministic decode changed by less than 1%, which is what I
would expect when the hardened build has disabled drafting for that mode.

This combination is the result I would carry into a larger correctness and
soak gate. It uses the existing serving binary and main quantisation, improves
memory headroom, and does not depend on a private HIP runtime.

## The IQ4_XS main model did not win on Vulkan

Replacing the current main quantisation was not a general improvement. With
the same IQ4_XS draft and width-three policy, the IQ4_XS main model lost 25.6%
at 512 and 16.9% at 8K. It gained 8.5% at 31.5K because that particular output
accepted more draft tokens, but its deterministic decode was also about 1.3%
slower across the prompt set.

The file may have quality or ROCm-kernel advantages that this benchmark does
not measure. It is still a rejection for my Vulkan profile: a larger
validation burden and two common-workload regressions are not a sensible trade
for one sequence-dependent long result.

## TOP_K was noise; PM4 was real but modest

The dedicated TOP_K change touches the sampling kernel, yet at `top_k=20` its
median decode changes were 0.9%, 3.4% and 0.03%. Prompt processing moved by
less than 0.4%. The middle result is interesting, but the three-workload median
is under 1% and the deterministic pass was flat. I would not call that a
material end-to-end improvement for Qwen3.8 27B.

Retained PM4 was different. With model, sampler, TOP_K code and runtime fixed,
it added 4.3%, 4.1% and 3.4% decode. It also raised short-prompt deterministic
prefill by 30%, while the 31.5K prefill result moved only 0.3%. That shape fits
a dispatch-overhead optimisation: useful for many small graph submissions,
not a new memory-bandwidth ceiling.

The caveat is substantial. The retained-PM4 path is custom code rather than an
upstream feature, and each ROCm arm emitted a `ROCm_Host compute buffer size`
mismatch warning while the context was destroyed. The process unloaded and
memory returned cleanly, but I would not put that warning into a production
service simply to gain four per cent.

## What the complete custom stack actually buys

Against today's production sampler baseline, the full IQ4_XS/ROCm/TOP_K/PM4
stack improved decode by 65.0% at 512, 45.8% at 8K and 29.7% at 31.5K. It also
improved 8K and 31.5K prompt processing by 18.2% and 16.7%, though short-prompt
prefill was 11.2% slower.

Those are material results. They do not mean every ingredient is valuable.
The isolated tests show that TOP_K contributed almost nothing here, while PM4
contributed about four per cent. Much of the headline comes from the draft
policy and from the ROCm fork's long-prefill path.

The simpler Vulkan candidate is faster than the complete custom stack at 512,
28.69 versus 27.12 tok/s, and effectively tied at 8K, 26.39 versus 26.69. ROCm
wins at 31.5K decode, 22.62 versus 19.59, and long prefill, 298.35 versus
258.06 tok/s. I would describe the custom stack as a long-context canary, not
as an across-the-board replacement.

Every arm stayed above 93 GiB of available memory, below 25.70 GiB of peak
GTT, and recorded no swap-out, OOM, guard stop or GPU fault. After both test
passes, the exact idle services were restored: the unpinned 125B Qwen model at
two 256K slots with all 40 GPU layers, Q8 K/V and prompt caching, plus the
pinned NPU model.

## The upstream boundary still matters

As checked on 5 September 2026, the relevant work is not a settled release:

- llama.cpp [PR 27311](https://github.com/ggml-org/llama.cpp/pull/27311), the
  UMA scheduler ring buffer, is open and mergeable;
- llama.cpp [PR 28313](https://github.com/ggml-org/llama.cpp/pull/28313), the
  ROCm TOP_K work, is open and mergeable;
- ROCm/rocm-systems [PR 11069](https://github.com/ROCm/rocm-systems/pull/11069),
  a HIP graph-update memory fix, is open and mergeable;
- the retained-PM4 implementation tested here remains private fork work.

My production runtime also contains availability and state-recovery behaviour
that the community fork was not built to replace. A faster isolated server is
not automatically a safer model-manager backend.

## Where I would stop claiming

This is a two-repeat, one-host performance qualification using source-explanation
prompts assembled from llama.cpp code. It checks non-empty output and obvious repetition;
it is not a perplexity comparison, an evaluation of IQ4_XS answer quality, a
multi-user concurrency test or a production soak. The fixed seed does not make
different quantisations produce the same text, so acceptance can change with
the generated sequence.

I would keep the current main model and Vulkan runtime. I would next qualify
the IQ4_XS draft, width three and a workload-aware draft floor through the
full exact-output, malformed-reasoning, cache-cycle, long-context and soak
suite. I would retain PM4 as a research canary, reject the IQ4_XS main model
for this Vulkan profile, and leave TOP_K unpromoted until another workload
shows a repeatable gain beyond noise.

That is less dramatic than copying the complete recipe. It is also the useful
result: most of the interactive improvement is available without changing the
main model or trusting a private runtime, while ROCm's genuine long-context
advantage remains isolated for a safer upstream version.

*Benchmarked 5 September 2026 on a GMKtec EVO-X3 with Ryzen AI MAX+ 395,
Radeon 8060S and 128 GiB unified memory. No production model, binary, registry
entry or Lemonade option was modified.*
