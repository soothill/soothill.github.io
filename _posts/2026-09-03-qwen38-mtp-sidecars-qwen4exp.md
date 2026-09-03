---
layout: post
title: "Six Qwen3.8 MTP heads; only one fits my next test"
seo_title: "Qwen3.8 MTP GGUF sidecars"
date: 2026-09-03 17:00:00 +0100
last_modified_at: 2026-09-03 17:00:00 +0100
permalink: /blog/2026/09/03/qwen38-mtp-sidecars-qwen4exp/
categories: [local-ai, engineering, upstream]
tags: [qwen3.8, qwen4exp, unsloth, gguf, mtp, speculative-decoding, strix-halo]
author: Darren Soothill
editorial_standard: soothill-human-v1
editorial_review_status: approved
editorial_reviewer: Darren Soothill
editorial_reviewed_at: 2026-09-03
series: "Local LLMs on Strix Halo"
series_order: 23
description: "Unsloth's six Qwen3.8 MTP GGUF sidecars range from 1.776 to 7.237 GiB. Shared Q8_0 is the sensible canary, not a production download."
---

> **Repository record:** Unsloth added six MTP GGUF files to
> [`unsloth/Qwen3.8-Flash-Next-GGUF`](https://huggingface.co/unsloth/Qwen3.8-Flash-Next-GGUF/tree/38bb39ee97821de2c9009abb7e93950eec396e66/MTP)
> in revision [`eb2a07ec`](https://huggingface.co/unsloth/Qwen3.8-Flash-Next-GGUF/commit/eb2a07ecb33b5495cbc8dc3183b9421a1dda4b46).
> The repository was at revision `38bb39ee` when I checked it. I recorded the
> exact files and LFS sizes from the Hub; I have not downloaded or benchmarked
> them on EVO-X3.

There is finally a concrete Qwen3.8 Flash Next draft-model set to evaluate, not
just an MTP pull request and an attractive performance claim. The practical
choice is much narrower than the six filenames suggest.

For this 128 GiB unified-memory machine, I would begin with the shared Q8_0
head. It is not the smallest file, but Unsloth reports that it drafts as well as
the self-contained version, avoids duplicated embedding/output tensors and has
better acceptance than shared Q4_K_M.

## The six files, exactly

| Hub path | Quantisation | Bytes | GiB | LFS SHA-256 |
| --- | --- | ---: | ---: | --- |
| `MTP/mtp-Qwen3.8-Flash-Next-BF16.gguf` | BF16, self-contained | 7,770,760,320 | 7.237 | `8ac04a65…149a99c` |
| `MTP/mtp-Qwen3.8-Flash-Next-Q4_K_M.gguf` | Q4_K_M, self-contained | 2,786,204,800 | 2.595 | `b646ef60…22a1575` |
| `MTP/mtp-Qwen3.8-Flash-Next-Q8_0.gguf` | Q8_0, self-contained | 4,137,429,120 | 3.853 | `cd87e5d1…09351e` |
| `MTP/mtp-Qwen3.8-Flash-Next-shared-BF16.gguf` | BF16, shared tensors | 5,227,963,456 | 4.869 | `32473fa7…34cc596b` |
| `MTP/mtp-Qwen3.8-Flash-Next-shared-Q4_K_M.gguf` | Q4_K_M, shared tensors | 1,907,151,936 | 1.776 | `f521868a…b149dfc` |
| `MTP/mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf` | Q8_0, shared tensors | 2,786,568,256 | 2.595 | `5ff54097…fa96e6` |

The `shared-` variants borrow the token embedding and output projection from
the main model. Unsloth's [MTP usage note](https://huggingface.co/unsloth/Qwen3.8-Flash-Next-GGUF/blob/38bb39ee97821de2c9009abb7e93950eec396e66/MTP/README.md)
recommends shared Q8_0, reports 66.1% acceptance and describes shared Q4_K_M as
about two acceptance points lower. It also records shared BF16 as larger and
slower because the draft output projection is cheaper at eight bits.

Those are upstream B200 measurements. They are not evidence that the same
ordering, acceptance or speed-up will hold on Radeon 8060S Vulkan.

## The runtime is still a moving target

Stock llama.cpp at the repository revision checked here cannot use these heads.
The mainline integration is [PR 28243](https://github.com/ggml-org/llama.cpp/pull/28243),
currently a draft with conflicts at head `2857e511`. It builds on the older MTP
work, adds shared-tensor borrowing and claims 1.3–2× generation.

Two other details matter before interpreting a test:

- Qwen4Exp recurrent rollback only became available in merged [PR 28123](https://github.com/ggml-org/llama.cpp/pull/28123).
- The MTP file lives in a subdirectory, so the server must receive its path
  explicitly; auto-discovery does not search `MTP/`.

The shared head also cannot be measured on its own during automatic memory
fit, because the main model is not yet present to lend its tensors. Explicit
context and offload settings are safer on a machine with tight headroom.

## The safe EVO-X3 fit is single-slot only

The production main model occupies 103.7 GiB before adding draft weights,
rollback state and KV/cache working memory. A 2.595 GiB file is a plausible
isolated canary; it is not permission to add the same reservation to the live
two-slot service.

More importantly, open [issue 28286](https://github.com/ggml-org/llama.cpp/issues/28286)
reports cross-slot content contamination with Qwen4Exp MTP and
`--parallel > 1`. Until that is fixed and reproduced cleanly, the current
two-slot route must stay non-speculative.

I would test shared Q8_0 with one slot, `n-max 2`, greedy decoding and explicit
memory limits. The gate should record accepted drafts, output hashes, code and
prose rates, recurrent rollback, long-context memory, rejection recovery and a
full unload. Q4_K_M is the fallback only if Q8_0 headroom is unsafe.

## Where I would stop claiming

The repository publication is material because it makes a well-defined canary
possible. It does not prove a production improvement on EVO-X3. The advertised
1.3–1.7× low-concurrency gains were measured elsewhere, and the integration PR
is still draft/conflicted.

My decision is therefore to record the exact shared Q8_0 artifact and wait for
a single-slot qualification window plus a concurrency fix. I would not download
six variants, and I would not trade cross-request isolation for a speculative
throughput headline.

*Hub and upstream state checked 3 September 2026. No model was downloaded and
the production Qwen service was not modified.*
