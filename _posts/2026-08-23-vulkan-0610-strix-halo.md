---
layout: post
title: "Vulkan 0.6.10 on Strix Halo: safer MTP costs speed"
seo_title: "Vulkan 0.6.10 vs 0.6.7 on Strix Halo"
date: 2026-08-23 02:00:00 +0100
last_modified_at: 2026-08-23 02:00:00 +0100
permalink: /blog/2026/08/23/vulkan-0610-strix-halo/
categories: [local-ai, benchmarks, engineering]
tags: [vulkan, llama-cpp, strix-halo, qwen3-6, mtp, deepseek-v4, lemonade]
author: Darren Soothill
editorial_standard: soothill-human-v1
editorial_review_status: pending
editorial_reviewer: Darren Soothill
editorial_reviewed_at: 2026-08-23
series: "Local LLMs on Strix Halo"
series_order: 12
description: "I tested Vulkan 0.6.10 against 0.6.5 and 0.6.7 on Strix Halo. Its MTP fix prevents long stalls, but cuts speculative decode by about 11%."
---

> **Test record:** I compared Strix Halo Vulkan releases 0.6.5, 0.6.7 and
> 0.6.10 on the same 128GB GMKtec EVO-X3. Qwen3.6-35B-A3B ran repeated
> 800- and 3,000-token plain and native-MTP requests, followed by cold-start
> ABBA controls. Release 0.6.10 completed every long MTP request, but its cold
> MTP decode was about **11% slower than 0.6.7**. Plain decode did not move.
> DeepSeek Q4_0 retained 0.6.7's prompt-processing gains over 0.6.5, while
> decode slipped by 3–4% against 0.6.7. A 30-minute mixed MTP soak completed
> **419/419 validated requests** with no service, recovery, isolation or GPU
> fault, but free-form prose still exposed the reused-slot output boundary.

Vulkan 0.6.10 gave me a less comfortable result than a simple upgrade
benchmark. It fixed the failure I cared about, but the fix was not free.

Release 0.6.8 introduced a deterministic MTP stall on hybrid recurrent models
such as Qwen3.6-35B-A3B. Release 0.6.9 removed the hang by reverting full
checkpoint rollback, which also restored the older state drift after a rejected
draft. Release 0.6.10 keeps the full checkpoint and changes how replayed tokens
are handled, so the slot makes forward progress instead of verifying the same
replayed draft forever.

The publisher's 3,000-token smoke result completed at about 65 tokens per
second. That established that the package could cross the former stall horizon.
It did not answer whether the fix retained 0.6.7 performance, behaved
consistently when a server slot was reused or changed the long-context
quantised-KV path I had already measured. Those were the questions that could
change my production decision.

## Three builds, one unchanged host

I used the released portable packages and verified the 0.6.10 archive against
its published SHA-256 digest. The builds were:

| Release | llama.cpp build | Commit | Relevant release change |
| --- | ---: | --- | --- |
| 0.6.5 | 10567 | `0b0f35d0` | DFlash2 support; baseline here uses native MTP |
| 0.6.7 | 10570 | `9b9ac3e3` | Chat-parser change only; backend unchanged from 0.6.6 |
| 0.6.10 | 10579 | `2586f6ed` | Full MTP checkpoints, replay fix and driver gate |

All tests used the bundled RADV driver on the Radeon 8060S (`gfx1151`). I left
IOMMU enabled because disabling it had already cost functionality on this host
without earning enough performance to justify the trade. I made no clock,
firmware, power, thermal or production-configuration change.

Production Lemonade remained on loopback port 13305 with no model loaded. Each
test server used loopback port 18080, one slot and a traffic guard that would
terminate the test if production loaded a model.

The Qwen target was the same 28GB `UD-Q6_K` GGUF in every arm, with SHA-256
`49935b04ad883c2f3d4da61f65b609d447dad67d0b08453b90abb09a1bb35464`.
The common settings were a 65,536-token context, Q8_0 K/V cache, Flash
Attention, 512-token batch and micro-batch, no host loading and greedy
sampling. MTP used draft width three and a zero acceptance threshold.

## Plain decode stayed where it was

I first ran all three releases through one server per mode, with two 800-token
and two 3,000-token forced outputs. The table reports the median generation
rate. Higher is better.

| Release | Plain 800 | MTP 800 | MTP gain | Plain 3,000 | MTP 3,000 | MTP gain |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.6.5 | 56.28 | **63.57** | +12.9% | 56.04 | **64.99** | +16.0% |
| 0.6.7 | 56.52 | **63.54** | +12.4% | 56.11 | **64.81** | +15.5% |
| 0.6.10 | 56.26 | **58.11** | +3.3% | 56.03 | **59.92** | +6.9% |

All 24 responses reached their requested output length and passed the checks
for empty output, early termination, long repeated loops and obvious corruption.
None stalled. Plain decode varied by less than half a percent across the three
packages, which is the useful control: the performance change sits in the MTP
path rather than the base Vulkan backend.

Release 0.6.10's MTP result was **8.6% slower at 800 tokens** and **7.6% slower
at 3,000 tokens** than 0.6.7 in this reused-slot test. Its two-run coefficient
of variation was about 3.8–4.2%, against 1.6–1.8% on 0.6.7. That was enough to
justify a cleaner control before assigning the spread to the new checkpoint.

The full [served comparison data](/assets/data/strix-halo-vulkan-065-067-0610-mtp-2026-08-23.csv)
is available without the rounding used above.

## A fresh process made the consistency boundary visible

The server reused the common prompt prefix between requests even when the API
body set `cache_prompt` to false. Repeated greedy outputs inside one process
were therefore not token-identical in plain or MTP mode. That result is
operationally relevant, but it mixes checkpoint behaviour with slot state.

I repeated 0.6.7 and 0.6.10 in ABBA order with a fresh server, fixed seed and
empty RAM cache for every request. Both plain runs were byte-identical to each
other and both MTP runs were byte-identical to each other at both lengths.

| Release and mode | 800 tokens | Two-run CV | 3,000 tokens | Two-run CV |
| --- | ---: | ---: | ---: | ---: |
| 0.6.7 plain | 56.40 | 0.004% | 56.15 | 0.063% |
| 0.6.7 MTP | **64.31** | 0.012% | **67.39** | 0.125% |
| 0.6.10 plain | 56.54 | 0.245% | 56.04 | 0.151% |
| 0.6.10 MTP | 56.99 | 0.082% | 59.87 | 0.008% |

Under this cleaner comparison, 0.6.10 MTP was **11.4% slower at 800 tokens**
and **11.2% slower at 3,000 tokens** than 0.6.7. It accepted a higher share of
draft tokens—53.4% versus 49.9% at 800, and 58.7% versus 54.7% at 3,000—so a
less predictable completion does not explain the loss. The added full-checkpoint
and replay work is the material difference between the releases.

The [cold-start ABBA data](/assets/data/strix-halo-vulkan-067-0610-mtp-cold-2026-08-23.csv)
contains the exact rates, acceptance and repeatability fields.

## “Token-exact” needs a narrower reading

Cold 0.6.10 MTP was repeatable, but it was not identical to 0.6.10 plain. The
first difference appeared at output token 437 in both forced lengths. On 0.6.7
the first difference appeared at token 220.

This does not by itself disprove the checkpoint fix. The replay commit records
that Vulkan target logits can change with batch shape or memory layout, while
the full checkpoint exists to restore recurrent state after rejected drafts.
“Token-exact rollback” describes that restored state. It should not be expanded
into a claim that the complete Vulkan speculative path must equal a
non-speculative request token for token.

The same-server result still matters. A long-lived production server does not
cold-start between user turns. Every release in this test changed deterministic
output after slot reuse, including plain 0.6.10. I therefore would not use the
cold ABBA result as evidence that the open inter-request state report is fully
resolved. The 30-minute mixed workload needs to test the service shape, not only
the checkpoint in isolation.

## Quantised K/V did not need another headline

The MTP fix should not affect DeepSeek's quantised-KV kernels, but 0.6.10 also
contains later backend changes. I reran the production-shaped Q4_0 path at 32K,
64K and 128K, with F16 as a control. The retained 0.6.5 and 0.6.7 arms had two
fresh process launches. The 0.6.10 arm had one complete matrix plus an
independent Q4_0 repeat at 128K. I did not repeat Q8_0, so I have left it out of
the three-version claim.

Each cell below is prompt processing followed by decode, in tokens per second.

| Q4_0 depth | 0.6.5 prompt / decode | 0.6.7 prompt / decode | 0.6.10 prompt / decode | 0.6.10 change vs 0.6.7 |
| --- | ---: | ---: | ---: | ---: |
| 32K | 86.24 / 17.21 | 99.95 / 17.33 | 99.55 / 16.62 | -0.4% / **-4.1%** |
| 64K | 71.28 / 16.59 | 96.03 / 16.72 | 96.12 / 16.22 | +0.1% / **-3.0%** |
| 128K | 57.05 / 15.54 | 88.56 / 15.66 | 88.74 / 15.12 | +0.2% / **-3.5%** |

Release 0.6.10 kept the Q4_0 prompt-processing improvement that arrived between
0.6.5 and 0.6.7: it was 15.4% faster than 0.6.5 at 32K, 34.8% at 64K and 55.5%
at 128K. It added nothing measurable to 0.6.7's result. F16 stayed within 1.8%
of both older builds across all six control cells.

The only repeatable movement from 0.6.7 was a small Q4_0 decode loss: 4.1% at
32K, 3.0% at 64K and 3.5% at 128K. At 128K, the two 0.6.10 launches varied by
0.61% for prompt processing and 0.71% for decode, so I do not think the 3.5%
result is a noisy launch.

I also forced a 2,048-token DeepSeek completion. Both 0.6.10 launches were
byte-identical to 0.6.7 and passed the output checks. Their median was 18.24
tokens/s against 18.48 on 0.6.7, a 1.3% difference. In other words, 0.6.10 did
not improve this path and gave me no reason to move an existing DeepSeek route.

The [DeepSeek K/V matrix](/assets/data/strix-halo-vulkan-065-067-0610-deepseek-kv-2026-08-23.csv)
and [long-output runs](/assets/data/strix-halo-vulkan-065-067-0610-deepseek-long-2026-08-23.csv)
contain the unrounded results.

## The soak decides whether this is a candidate or a default

The final test held one 0.6.10 MTP server open for 1,803 seconds. It cycled code,
prose, strict JSON-schema and tool-call requests over an 8K common prefix. After
the first request in each case, the remaining 415 requests reported a cache
hit.

| Workload | Requests | Median decode | Run CV | Median draft acceptance | Stable useful output |
| --- | ---: | ---: | ---: | ---: | --- |
| Code | 105 | 84.99 | 0.38% | 90.5% | Yes |
| Strict JSON schema | 105 | 90.65 | 0.29% | 97.5% | Yes |
| Prose | 105 | 55.50 | 0.83% | 56.1% | No: three variants |
| Tool call | 104 | 87.71 | 0.69% | 100.0% | Yes |

All **419/419 responses passed** their workload validator. The harness also
cancelled 34 live streams; every follow-up recovery request succeeded. All 52
cross-request marker checks returned only their own marker. I found no harness
error, server error, malformed structured response, leaked marker or GPU fault.
The temporary server shut down cleanly and production Lemonade remained
unchanged.

The code, JSON and tool result were stable across the run, ignoring the random
identifier attached to an otherwise identical tool call. Greedy prose produced
three different valid completions. That did not cause a service failure, but it
agrees with the earlier reused-slot observation and stops me treating this soak
as proof of byte-exact request independence.

The [soak summary](/assets/data/strix-halo-vulkan-0610-mtp-soak-2026-08-23.csv)
contains the per-workload counts, rates, variation, acceptance and cache reuse.
It qualifies a single-slot cached service. It does not qualify concurrent slots
or close the upstream state report.

## I would canary Qwen, not replace every route

Release 0.6.10 is the first of these three packages I would use to canary long
native-MTP output. It contains the full-checkpoint replay fix and repeatedly
crossed 3,000 generated tokens, then survived the mixed 30-minute run. Choosing
0.6.7 only because it is 11% faster would put the old rollback behaviour back
into the request path.

That is not a reason to replace every Vulkan route. I would operate the result
in three bounded steps:

1. Put Qwen3.6 native MTP through a single-slot 0.6.10 canary behind Lemonade,
   with the existing prefix cache and no separately exposed inference port.
2. Keep DeepSeek on its current route. Release 0.6.10 did not improve its long
   output or F16 path and gave back 3–4% of Q4_0 decode against 0.6.7.
3. Do not qualify multi-slot concurrency from this test. It used one slot, and
   the open inter-request state report still defines a separate boundary.

Release 0.6.5 has no remaining advantage in these results. Release 0.6.7 is the
faster MTP benchmark and the source of the retained quantised-KV prefill gain,
but it is not the build I would choose for a genuinely long native-MTP route.
Release 0.6.10 trades some of that speculative speed for the checkpoint fix.
The useful result is a safer canary boundary, not a headline performance
upgrade.

*Sources checked 23 August 2026: the [Vulkan 0.6.5
release](https://github.com/Nathanw1014/strix-halo-llamacpp/releases/tag/v0.6.5),
the [0.6.7 release](https://github.com/Nathanw1014/strix-halo-llamacpp/releases/tag/v0.6.7),
the [0.6.10 release and its stated evidence
boundary](https://github.com/Nathanw1014/strix-halo-llamacpp/releases/tag/v0.6.10),
the [MTP replay commit](https://github.com/Nathanw1014/llama.cpp/commit/9c5d899ff7966179f56e49edd5c7a57f7b6172e6)
and the open [`llama.cpp` inter-request state
report](https://github.com/ggml-org/llama.cpp/issues/26425). All performance and
consistency figures come from retained same-machine artefacts collected on 23
August 2026.*
