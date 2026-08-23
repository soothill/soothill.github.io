---
layout: post
title: "Vulkan 0.6.10 on Strix Halo: the MTP fix has a cost"
seo_title: "Vulkan 0.6.10 vs 0.6.7 on Strix Halo"
date: 2026-08-23 04:13:17 +0100
last_modified_at: 2026-08-23 04:43:20 +0100
permalink: /blog/2026/08/23/vulkan-0610-strix-halo/
categories: [local-ai, benchmarks, engineering]
tags: [vulkan, llama-cpp, strix-halo, qwen3-6, mtp, deepseek-v4, lemonade]
author: Darren Soothill
editorial_standard: soothill-human-v1
editorial_review_status: approved
editorial_reviewer: Darren Soothill
editorial_reviewed_at: 2026-08-23
series: "Local LLMs on Strix Halo"
series_order: 15
description: "Vulkan 0.6.10 fixes the long MTP stall on my Strix Halo machine, but Qwen3.6 decode falls about 11% and DeepSeek does not improve."
---

> **Test record:** I compared Vulkan 0.6.5, 0.6.7 and 0.6.10 on the same 128GB
> GMKtec EVO-X3. Qwen3.6-35B-A3B completed repeated 800- and 3,000-token plain
> and native-MTP requests, followed by cold-start ABBA controls. Vulkan 0.6.10
> fixed the long MTP stall, but cold MTP decode was about **11% slower than
> 0.6.7**. DeepSeek Q4_0 kept the large prefill gain already present in 0.6.7,
> while decode fell by 3–4%. The final 30-minute soak completed **419/419
> validated requests**. All 34 cancellation recoveries and 52 isolation checks
> passed, and no GPU fault appeared.

Vulkan 0.6.10 fixed the long MTP hang on `evox3`. It also made Qwen3.6 about
11% slower.

I would still rather lose that speed than run a server that can wedge halfway
through a long response. Before I changed anything behind Lemonade, I wanted to
know exactly what the fix cost and whether it disturbed the DeepSeek path I had
already tested.

The problem appeared in 0.6.8. On hybrid recurrent models such as
Qwen3.6-35B-A3B, the MTP slot could keep checking the same replayed draft and
never move forward. Release 0.6.9 stopped the hang by removing full checkpoint
rollback, but that brought back the older state drift after a rejected draft.
Release 0.6.10 keeps the checkpoint and changes the replay instead.

The release page included a useful 3,000-token smoke test at roughly 65
tokens/s. It proved that the new package could cross the point where 0.6.8 had
stalled. It did not tell me how much slower the fix was, whether a reused server
slot behaved properly or what happened to quantised K/V at 128K. I ran those
tests on `evox3` rather than treating the release result as my deployment result.

## Same machine, same models, three builds

I used the three released portable packages and checked the 0.6.10 archive
against its published SHA-256 digest.

| Release | llama.cpp build | Commit | Relevant release change |
| --- | ---: | --- | --- |
| 0.6.5 | 10567 | `0b0f35d0` | DFlash2 support; baseline here uses native MTP |
| 0.6.7 | 10570 | `9b9ac3e3` | Chat-parser change only; backend unchanged from 0.6.6 |
| 0.6.10 | 10579 | `2586f6ed` | Full MTP checkpoints, replay fix and driver gate |

All three ran with the bundled RADV driver on the Radeon 8060S (`gfx1151`). I
left IOMMU enabled; disabling it had already removed useful functionality on
this machine for too little performance. I also left the clocks, firmware,
power policy and thermal setup alone.

Production Lemonade stayed on loopback port 13305 with no model loaded. The
test servers used port 18080, one slot and a guard that would stop the run if a
production model loaded. Nothing in the production configuration changed.

For Qwen I used the same 28GB `UD-Q6_K` GGUF in every arm, with SHA-256
`49935b04ad883c2f3d4da61f65b609d447dad67d0b08453b90abb09a1bb35464`.
The server had a 65,536-token context, Q8_0 K/V cache, Flash Attention, 512-token
batch and micro-batch, no host loading and greedy sampling. MTP used a draft
width of three with a zero acceptance threshold.

## The base Vulkan speed did not change

I started with one server per mode and forced two 800-token and two 3,000-token
answers from each release. These are median generation rates in tokens per
second; higher is better.

| Release | Plain 800 | MTP 800 | MTP gain | Plain 3,000 | MTP 3,000 | MTP gain |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.6.5 | 56.28 | **63.57** | +12.9% | 56.04 | **64.99** | +16.0% |
| 0.6.7 | 56.52 | **63.54** | +12.4% | 56.11 | **64.81** | +15.5% |
| 0.6.10 | 56.26 | **58.11** | +3.3% | 56.03 | **59.92** | +6.9% |

All 24 answers reached the requested length. None was empty, stopped early,
fell into a long repeated loop or showed the obvious corruption signatures I
check for.

The plain numbers are almost boring, which is useful here. Every build stayed
around 56 tokens/s. The ordinary Vulkan backend had not slowed down; the loss
was confined to MTP.

In this first run, 0.6.10 MTP was **8.6% slower at 800 tokens** and **7.6%
slower at 3,000 tokens** than 0.6.7. Its two measurements also moved around more:
roughly 3.8–4.2% variation, against 1.6–1.8% on 0.6.7. That made me suspicious
of the test before I blamed the new checkpoint work.

The full [served comparison data](/assets/data/strix-halo-vulkan-065-067-0610-mtp-2026-08-23.csv)
is available without the rounding used above.

## The first comparison was muddied by slot reuse

The server reused the common prompt prefix even when the request set
`cache_prompt` to false. Repeated greedy answers inside the same process were
not token-identical, in either plain or MTP mode. I did not want to turn that
mixed result into a precise claim about 0.6.10.

I reran 0.6.7 and 0.6.10 in ABBA order, starting a fresh server with an empty
RAM cache for every request and holding the seed fixed. This time the two plain
runs matched each other byte for byte, as did the two MTP runs, at both output
lengths.

| Release and mode | 800 tokens | Two-run CV | 3,000 tokens | Two-run CV |
| --- | ---: | ---: | ---: | ---: |
| 0.6.7 plain | 56.40 | 0.004% | 56.15 | 0.063% |
| 0.6.7 MTP | **64.31** | 0.012% | **67.39** | 0.125% |
| 0.6.10 plain | 56.54 | 0.245% | 56.04 | 0.151% |
| 0.6.10 MTP | 56.99 | 0.082% | 59.87 | 0.008% |

The cleaner repeat made the result worse, but much harder to dismiss. Vulkan
0.6.10 MTP was **11.4% slower at 800 tokens** and **11.2% slower at 3,000
tokens** than 0.6.7.

It was not simply receiving poor drafts. Acceptance was higher on 0.6.10:
53.4% against 49.9% at 800 tokens, and 58.7% against 54.7% at 3,000. The extra
checkpoint and replay work is the most credible explanation for the speed I
lost.

The [cold-start ABBA data](/assets/data/strix-halo-vulkan-067-0610-mtp-cold-2026-08-23.csv)
contains the exact rates, acceptance and repeatability fields.

There is a second result I would not overstate. Cold 0.6.10 MTP was repeatable,
but it did not generate the same answer as cold 0.6.10 without MTP. The first
different output token was 437; on 0.6.7 it was 220.

That does not show that checkpoint restoration failed. The replay commit notes
that Vulkan target logits can move with batch shape or memory layout. The
checkpoint is restoring the recurrent state after a rejected draft, not
promising that speculative and ordinary Vulkan requests will produce the same
complete answer.

Slot reuse is still a real concern because a production server does not restart
between turns. All three releases changed deterministic output after a slot was
reused, including plain 0.6.10. The cold repeat therefore did not close the
open inter-request state report; it only separated that problem from the MTP
speed comparison.

## DeepSeek gave me no reason to move

MTP was the reason for testing Qwen, but 0.6.10 also contains later backend
changes. I did not want to discover a DeepSeek regression after moving the
package.

I reran the Q4_0 K/V path at 32K, 64K and 128K, with F16 as a control. The
retained 0.6.5 and 0.6.7 results each contained two fresh launches. For 0.6.10
I ran the complete matrix and then repeated Q4_0 at 128K in another process. I
did not repeat Q8_0, so it is not part of this comparison.

Each cell below is prompt processing followed by decode, in tokens per second.

| Q4_0 depth | 0.6.5 prompt / decode | 0.6.7 prompt / decode | 0.6.10 prompt / decode | 0.6.10 change vs 0.6.7 |
| --- | ---: | ---: | ---: | ---: |
| 32K | 86.24 / 17.21 | 99.95 / 17.33 | 99.55 / 16.62 | -0.4% / **-4.1%** |
| 64K | 71.28 / 16.59 | 96.03 / 16.72 | 96.12 / 16.22 | +0.1% / **-3.0%** |
| 128K | 57.05 / 15.54 | 88.56 / 15.66 | 88.74 / 15.12 | +0.2% / **-3.5%** |

The large prefill improvement happened between 0.6.5 and 0.6.7, and 0.6.10
kept it. Against 0.6.5, Q4_0 prompt processing was 15.4% faster at 32K, 34.8%
at 64K and 55.5% at 128K. Against 0.6.7, it was effectively unchanged. The F16
control also stayed within 1.8% of both older builds except for 128K prompt
processing. That cell reached 91.76 tokens/s on 0.6.10, 2.34% above 0.6.5 and
1.71% above 0.6.7.

Decode moved the wrong way. Q4_0 fell by 4.1% at 32K, 3.0% at 64K and 3.5% at
128K compared with 0.6.7. The independent 128K repeat stayed close to the first
run—0.61% variation for prompt processing and 0.71% for decode—so I would not
write that loss off as a noisy launch.

I finished with a 2,048-token DeepSeek answer. Both 0.6.10 runs matched the
0.6.7 output byte for byte and passed the checks. Median decode was 18.24
tokens/s against 18.48 on 0.6.7, a 1.3% difference. There is no upgrade in that
number, and no reason to disturb the current DeepSeek route.

The [DeepSeek K/V matrix](/assets/data/strix-halo-vulkan-065-067-0610-deepseek-kv-2026-08-23.csv)
and [long-output runs](/assets/data/strix-halo-vulkan-065-067-0610-deepseek-long-2026-08-23.csv)
contain the unrounded results.

## Then I left Qwen running

The shorter tests told me what had changed. They did not tell me whether I
could keep the server alive behind Lemonade.

I held one 0.6.10 MTP process open for 1,803 seconds and cycled code, prose,
strict JSON-schema and tool-call requests over a common 8K prefix. After the
first request for each workload, the other 415 reported a cache hit.

| Workload | Requests | Median decode | Run CV | Median draft acceptance | Stable useful output |
| --- | ---: | ---: | ---: | ---: | --- |
| Code | 105 | 84.99 | 0.38% | 90.5% | Yes |
| Strict JSON schema | 105 | 90.65 | 0.29% | 97.5% | Yes |
| Prose | 105 | 55.50 | 0.83% | 56.1% | No: three variants |
| Tool call | 104 | 87.71 | 0.69% | 100.0% | Yes |

All **419/419 responses passed**. I cancelled 34 streams on purpose and every
recovery request worked. Fifty-two marker checks looked for text crossing from
one request into another; every one returned only its own marker. I found no
malformed structured response, server error, leaked marker or GPU fault. The
test process shut down cleanly and production Lemonade was still untouched.

Code, JSON and the useful part of the tool call stayed the same throughout the
run once I ignored the random tool-call ID. Greedy prose produced three valid
variants. That is not a service failure, but it is another reason not to call
slot reuse byte-exact.

The [soak summary](/assets/data/strix-halo-vulkan-0610-mtp-soak-2026-08-23.csv)
contains the per-workload rates, variation, acceptance and cache reuse. This was
a one-slot test. It says nothing about concurrent slots and does not close the
upstream state issue.

## What I would run now

I would use 0.6.10 for the next Qwen3.6 native-MTP canary. It completed the long
answers, survived the mixed soak and contains the checkpoint fix. I would keep
it at one slot, behind Lemonade, with the existing prefix cache and no separate
external inference port.

I would not pretend it is a faster release. On this machine, 0.6.7 is about 11%
quicker for cold MTP and still carries the quantised-KV prefill improvement over
0.6.5. I would not put it back on a genuinely long MTP route just to recover
that speed, because it does not contain the full replay fix.

DeepSeek stays where it is. Vulkan 0.6.10 did not produce a consistent F16 gain
or improve the long answer, and Q4_0 decode was 3–4% slower than 0.6.7. Release
0.6.5 has no remaining advantage in these results.

So this is not the usual upgrade story. Vulkan 0.6.10 fixes the problem that
could stop the request, and charges roughly 11% of Qwen's MTP speed for doing
it. For the first canary I would pay that cost. I would not make the same trade
for every model on the machine.

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
