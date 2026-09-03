---
layout: post
title: "Qwen3.8 can now roll back recurrent state, but that is only half the MTP story"
seo_title: "Qwen3.8 recurrent rollback in llama.cpp PR 28123"
date: 2026-09-03 17:00:00 +0100
last_modified_at: 2026-09-03 17:00:00 +0100
permalink: /blog/2026/09/03/qwen38-recurrent-rollback-pr28123/
categories: [local-ai, engineering, upstream]
tags: [qwen3.8, qwen4exp, llama-cpp, mtp, speculative-decoding, recurrent-state, strix-halo]
author: Darren Soothill
editorial_standard: soothill-human-v1
editorial_review_status: approved
editorial_reviewer: Darren Soothill
editorial_reviewed_at: 2026-09-03
series: "Local LLMs on Strix Halo"
series_order: 22
description: "PR 28123 makes Qwen3.8 recurrent rollback practical for MTP. It removes a large copy cost, but does not make concurrent drafting safe."
---

> **Source record:** llama.cpp [PR 28123](https://github.com/ggml-org/llama.cpp/pull/28123)
> merged on 1 September 2026 as
> [`0eadefeb`](https://github.com/ggml-org/llama.cpp/commit/0eadefebd3f8f92a86d634a0e5b8fffc9dc792c0).
> The patch adds Qwen4Exp recurrent-state rollback and snapshots its two
> convolution histories for each rollback position. The reported performance
> was measured on an RTX PRO 6000, not on EVO-X3.

Speculative decoding is only useful if rejecting a draft is cheaper than the
tokens it saves. Before PR 28123, Qwen3.8 Flash Next could not cheaply restore
its recurrent state after a rejected MTP token. The server fell back to copying
the complete state to host memory on every speculative round.

On the upstream author's test, that overhead was large enough to make MTP prose
slower than running without a draft at all.

## The missing state was convolution history

Adding Qwen4Exp to the list of architectures that support rollback was not
sufficient. This model has its own convolution-state writer for the delta-net
QKV convolution and the PLE path. It recorded only the current plane, so a
rollback could restore the SSM state beside a convolution history that had
already consumed the rejected token.

The merged patch stores a history for every rollback slot. Rolling back one or
more tokens can now select a state that genuinely predates them rather than
pairing old and new halves of the recurrent calculation.

That is both a correctness fix and an enabler for useful MTP performance.

## The upstream speed claim is substantial and specific

With one slot, an MTP head and `n-max 3`, the PR records these RTX PRO 6000
generation rates:

| Mode | Reported rate |
| --- | ---: |
| No draft | 108 tokens/s |
| MTP before rollback fix, code | 123 tokens/s |
| MTP before rollback fix, prose | 83 tokens/s |
| MTP after rollback fix, code | **183 tokens/s** |
| MTP after rollback fix, prose | **144 tokens/s** |

The telling row is 83 tokens/s. Drafting was not merely less impressive before
the fix; it was slower than no speculation for that prose workload.

These numbers do not prove a Strix Halo gain; that path remains not tested.
GPU, model quantisation, sampler,
draft depth and available memory all change speculative acceptance and cost.
The production EVO-X3 route also runs two slots with a 103.7 GiB main model,
not one RTX slot with comfortable discrete VRAM.

## What the merge changes for EVO-X3

I would require `0eadefeb` in any Qwen3.8 MTP canary. Testing an older branch
would spend time measuring a known host-copy fallback and could mistake a state
bug for a poor draft model.

I would not enable MTP in production because this prerequisite merged. The
separate [cross-slot contamination report](/blog/2026/09/03/qwen38-mtp-parallel-cross-slot-contamination/)
shows that `draft-mtp` with more than one parallel slot can mix content between
requests. The live route is deliberately `--parallel 2`.

The next safe test is therefore single-slot and isolated: deterministic output,
accepted-token accounting, rollback at every draft length, ABCCBA state
restoration, mixed code and prose, then a clean unload. Two-slot performance is
irrelevant until two-slot correctness is fixed.

## Where I would stop claiming

PR 28123 repairs the rollback machinery described in its scope. It does not
merge Qwen4Exp MTP support itself, validate Unsloth's new sidecars on gfx1151 or
resolve concurrent draft-state isolation.

My decision is to treat this merge as a mandatory foundation, not a deployment
signal. It makes a sensible experiment possible. It does not make that
experiment production-safe.

*Upstream state checked 3 September 2026. No local inference test or production
change was made for this note.*
