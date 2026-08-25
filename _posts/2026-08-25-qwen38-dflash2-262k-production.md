---
layout: post
title: "Qwen3.8 at 262K: fixing DFlash2 for production"
seo_title: "Qwen3.8 DFlash2 at 262K on AMD Strix Halo"
date: 2026-08-25 17:15:00 +0100
last_modified_at: 2026-08-25 17:15:00 +0100
permalink: /blog/2026/08/25/qwen38-dflash2-262k-production/
categories: [local-ai, engineering, benchmarks]
tags: [qwen3.8, dflash2, speculative-decoding, llama-cpp, vulkan, lemonade, strix-halo, long-context]
author: Darren Soothill
editorial_standard: soothill-human-v1
editorial_review_status: approved
editorial_reviewer: Darren Soothill
editorial_reviewed_at: 2026-08-25
series: "Local LLMs on Strix Halo"
series_order: 16
description: "I repaired Qwen3.8 DFlash2 state reuse and a deterministic Vulkan stall, then deployed separate fast and exact 262K routes with memory-aware eviction."
---

> **Test record:** I took a Qwen3.8-27B ROCmFPX Q4 deployment from native
> MTP through DFlash2 qualification and into Lemonade 11.7.0 on `evox3`, a
> 128GB Ryzen AI MAX+ 395 / Radeon 8060S workstation. The route is configured
> for a 262,144-token context. Making it safe required a recycled recurrent-state
> fix, a greedy/hybrid speculation guard, restoration of bounded rollback after
> a deterministic second-request Vulkan stall, a custom b10635 runtime, separate
> DFlash2 and no-sidecar Exact profiles, and pressure-aware model eviction. The
> repaired build completed a 259,012-token prompt plus 2,048 output tokens with
> no stall or GPU fault. DFlash2 was **34.6–43.8% faster than Exact** in the live
> short-to-32K tests, but **15.5–27.0% slower than the former MTP profile** for
> generation. Correctness, not a headline throughput win, is why I deployed it.

The attractive version of speculative decoding is simple: a small model drafts
several likely tokens, the target verifies them in one pass, and generation gets
faster without changing the answer.

Qwen3.8-27B made every clause in that sentence more complicated.

It is a hybrid model with recurrent linear-attention state as well as ordinary
attention. DFlash2 adds its own draft sidecar and verifies several proposed
tokens together. Lemonade also needs to keep a 262K-capable service responsive
without letting an idle second model consume the memory that a large KV cache
may need. The first implementation was fast enough to be interesting and wrong
enough not to deploy.

This is the record of the fixes that turned it into an operating route.

## The production shape I wanted

My earlier [23-deployment coding benchmark](/blog/2026/08/14/coding-model-benchmark-strix-halo/)
made Qwen3.8-27B a useful dense local model. The Q6 deployment reached 8/10 on
the executable task set; the ROCmFPX Q4 route was compelling for its compact
target and native speculative head. A later
[Vulkan-versus-ROCm comparison](/blog/2026/08/19/vulkan-064-rocm-714-strix-halo/)
also showed why the served request matters more than a bare kernel number.

The service goal was therefore:

```text
OpenAI-compatible client
          │
       model=llm
          │
  Lemonade collection router
          │
          ├── normal stochastic request ──> repaired DFlash2 profile
          │
          └── exact / deterministic request ──> no-sidecar Exact profile
```

Both profiles use the same Qwen3.8-27B ROCmFPX-MQ Q4 target and the same
262,144-token context allocation. The distinction is the decoding path:

| Public route | Speculation | Intended use |
| --- | --- | --- |
| `llm-fast` / `qwen38-fast` | DFlash2, `n_max=7`, `p_min=0.9` | normal coding, analysis and conversation |
| `llm-exact` / `qwen38-exact` | none | greedy, deterministic, verbatim and token-sensitive work |
| `llm` | collection router | general client entry point, selecting one of the profiles above |

An explicit `route_profile=exact` request takes a deterministic first-match
rule and bypasses semantic classification. Direct exact aliases remain the
strongest contract for a caller that cannot accept heuristic routing.

That split was not the first design. It was the result of the parity failure.

## Fix 1: make a recycled recurrent cell start at zero

The first DFlash2 qualification failed at the first content token. Bare decode
and DFlash2 produced readable text, but they did not produce the same token
stream under the greedy parity test.

The first root cause was stale device state. When a recurrent sequence was
fully removed, its metadata was released, but the backing row on the GPU was
not necessarily erased. A later request could reuse that row as its nominal
zero state. Graph-local clearing was not ordered ahead of every Vulkan read, so
a fresh server could match the reference while a reused server inherited old
recurrent values.

The repair had three parts:

1. Separate dry-run slot planning from state mutation, so deciding where a
   sequence will go cannot partly alter the live cache.
2. Before graph submission, explicitly zero every R/S rollback plane belonging
   to a recycled destination row.
3. Add a full-reset/reuse regression that dirties a recurrent cell, removes the
   sequence, reuses the row, and compares its logits with a genuinely fresh
   context.

After that change the immediate mismatch disappeared. With unrestricted
DFlash2 selection, the first cross-path split moved from the first content
token to token 324. That was progress, but not parity.

## Fix 2: admit that batched verification is not exact greedy decode

The remaining divergence was not another dirty buffer. Qwen3.8's recurrent
scan is sensitive to the shape in which target tokens are evaluated. Verifying
several draft tokens together changes the floating-point reduction order from
canonical one-token-at-a-time decoding. Near an argmax tie, that can select a
different next token even when the draft has not introduced a semantically bad
answer.

Raising DFlash2's selector threshold to `p_min=0.9` helped. A 330-token
diagnostic matched exactly, and later free-form splits moved to tokens 415–607.
It did not create a proof of equality. Confidence filtering reduces how often
the speculative path is used; it cannot make two numerically different graph
shapes identical.

I also tried the usual controls: disabling asynchronous Vulkan execution,
graph optimisation and fusion, then serialising submissions. The branch still
changed near token 430, while generation fell to about 9.4–9.5 tokens per
second. The slower path did not buy the promised invariant, so I rejected it.

The final code disables speculation automatically for greedy requests on
recurrent and hybrid targets. The production architecture goes further: exact
traffic uses a context that never loads the draft sidecar. This avoids both the
batched verification path and the 3.2–3.7GiB memory cost observed from loading
DFlash2 at the 262K configuration.

The important distinction is that the greedy guard is a safety net. It is not
the preferred exact route.

## Fix 3: put bounded rollback back after the “memory saving” stalled

The first parity patch tried to remove DFlash and DSpark from the set of methods
that allocate recurrent rollback planes. That restored a simpler target graph
for greedy fallback and reduced loaded GPU-addressable memory by about 1.03GiB.
It also introduced the most serious regression in the project.

The first stochastic request completed. The second processed its full prompt,
reached the 100-generated-token timing report and then stopped making progress.
The failure reproduced in two fresh server processes. Lemonade and the health
endpoint remained responsive, and the kernel reported no GPU reset. At cleanup,
the Vulkan path reported a host compute-buffer size mismatch.

Without bounded rollback planes, every partially rejected DFlash draft was
saved and restored through a full recurrent checkpoint copied via host memory.
Repeated full checkpoint cycles eventually left the Vulkan target waiting on
the GPU queue.

The final repair restored DFlash and DSpark to `need_n_rs_seq()`. They now
allocate `draft.n_max` bounded rollback snapshots, just like the other draft
methods that need recurrent replay. I retained the recycled-cell zeroing and
the greedy/hybrid guard, then added model-resolution assertions that DFlash and
DSpark always request a non-zero rollback count equal to their configured
maximum draft length.

That deliberately gives back the 1.03GiB saving. It is the right trade. Seven
bounded planes used 25.170GiB of loaded GTT rather than 24.141GiB for the
stalled full-checkpoint build. Memory should be reclaimed by an eviction
policy, not by replacing the stable rollback mechanism with a path that hangs.

## Fix 4: build a runtime that supports both ROCmFPX and DFlash2

The stock Strix Halo v0.6.11 executable could not load the ROCmFPX custom
tensors. An earlier compatible b10621 backend could run the target and its
native MTP head, but it did not contain the complete DFlash2 and recurrent-state
repair.

I built an isolated source combination instead:

- Laurent's ROCmFPX `llama.cpp` base at `16f0799a`;
- the DFlash2 pull-request head at `f7aadef0`;
- merge base `b576dc7dc`;
- the recurrent-state reuse, greedy guard and bounded-rollback fixes described
  above; and
- the Strix Halo Vulkan v0.6.11 userspace driver.

The production binary identifies as `llama.cpp 0.2.0-dev`, build 10635,
revision `b576dc7dc`. I pinned the
[DFlash2 sidecar](https://huggingface.co/z-lab/Qwen3.8-27B-DFlash2-GGUF) at
revision `2d9571f8ce46d5644596542897499006f36f5668` and verified its SHA-256
before qualification. The focused Vulkan gate passed **2,767/2,767** CPU
reference comparisons across matrix multiplication, top-k, row selection,
RoPE, concatenation, contiguous copies, addition and multiplication.

This version work produced no magic package upgrade. It produced a known source
combination that could load the actual target, run the sidecar and retain the
fixes under test. That is a more useful definition of “latest” for a production
route than the highest release number alone.

## Fix 5: tune the profile, then test the answer

The final DFlash2 profile uses:

```text
context              262,144
batch / micro-batch  2,048 / 256
K/V cache            Q8_0 / Q8_0
Flash Attention      enabled
slots                1
DFlash maximum       7 tokens
DFlash p_min          0.9
host prompt cache     8GiB
```

`n_max=7` and `p_min=0.9` were the production compromise. The confidence floor
kept low-probability draft branches out of the normal path; seven-token bounded
rollback supported useful draft spans without returning to the unsafe
full-checkpoint route. Exact uses the same target settings but `spec-type=none`.

I did not qualify this configuration with throughput alone. The gate included
structured JSON, verbatim copying, long free-form prose, repeated server-slot
reuse, sequential stochastic requests, greedy requests with zero draft
activity, rollback replay and a nearly full context.

| Gate | Result |
| --- | --- |
| Focused Vulkan operations | 2,767/2,767 passed |
| Sequential stochastic reuse | 10/10 requests completed, zero stalls |
| Guarded greedy sequence | 3/3 completed, zero drafted tokens |
| Recurrent rollback tests | zero maximum logits difference |
| Near-full context | 259,012 prompt + 2,048 output tokens completed |
| Kernel fault capture | no matching reset, timeout or page fault |

The ten-request stochastic sequence produced a 304.39 token/s median prompt
rate and 17.83 token/s median generation rate. Against the clean pre-repair
build, generation was 2.66% lower and wall time 0.99% higher. Those are not
material differences.

The near-full run occupied 261,060 visible tokens inside the 262,144-token
allocation. The fixed arm processed the prompt at 100.361 tokens/s, generated
at 10.131 tokens/s and completed in 2,783.02 seconds. Against the clean
stochastic baseline, that was +0.67% prompt processing, -2.35% generation and
-0.45% wall time. Both arms produced the same output hash, and the former
deterministic stall did not return.

## Fix 6: keep two models ready without promising that both stay resident

A 262K context is already a meaningful memory allocation. Several models in
the wider portfolio advertise windows near one million tokens. Keeping every
weight set and every idle KV cache resident would turn “ready” into a capacity
failure.

Lemonade therefore allows two loaded LLM processes, but both Qwen profiles are
unpinned and participate in automatic eviction:

| Policy | Production value |
| --- | ---: |
| Maximum loaded LLMs | 2 |
| Idle KV-cache downsize | 120 seconds |
| Full idle model eviction | 900 seconds |
| Global pressure threshold | 70% |
| Qwen eviction weight | 2.0 |

The warmer loads Qwen when Lemonade starts, but it does not fight the eviction
manager. After two idle minutes, Lemonade erases KV state while leaving the
backend alive. After 15 minutes—or sooner if the global memory-pressure rule
requires it—the whole unpinned model can leave memory. The next routed request
loads it normally. An active or streaming request is never selected for
eviction.

With DFlash2 and Exact both resident, the observed combined GTT high-water was
48.38GiB. The system still had about 68GiB available. That is comfortable for
this pair and intentionally not a promise that both processes survive when a
large live KV cache needs the space.

## Fix 7: expose the distinction through the routing engine

The final integration changed more than one launch command. Lemonade 11.7.0
needed two registered profiles, stable aliases, a model collection, an explicit
exact rule, a startup warmer, the two-model residency limit, and a backend
selector pinned to the repaired binary. I also retained byte-for-byte backups
of the pre-change registry, aliases, recipe options and service wrapper, plus a
quiescence-checked rollback driver.

Production verification covered four paths:

- direct DFlash2 alias;
- direct Exact alias;
- general `llm` selection to DFlash2; and
- `llm` with the explicit exact metadata override.

Both backends reported ready, alive and configured for 262K. The DFlash command
contained `draft-dflash`, `n_max=7` and `p_min=0.9`; Exact contained
`spec-type none` and no draft model. Loopback, LAN and Tailscale health all
remained good, and the production configuration hashes matched before and
after the live benchmark.

## What the deployed benchmark says

I then compared the former MTP profile, repaired DFlash2 and no-speculation
Exact on the live service. The 512- and 8K-prompt cases used three
counterbalanced repetitions per profile; 32K used one long repetition. Every
request produced a forced 512-token completion and passed the output checks.

| Prompt workload | Legacy MTP | DFlash2 | Exact | DFlash2 vs MTP | DFlash2 vs Exact |
| --- | ---: | ---: | ---: | ---: | ---: |
| 512 tokens | 25.82 tok/s | 18.85 tok/s | 13.11 tok/s | **-27.0%** | **+43.8%** |
| 8,200 tokens | 22.69 tok/s | 17.44 tok/s | 12.96 tok/s | **-23.1%** | **+34.6%** |
| 32,768 tokens | 20.60 tok/s | 17.41 tok/s | 12.32 tok/s | **-15.5%** | **+41.3%** |

The MTP comparison used the new fixed binary, so it isolates the decoding
profile rather than replaying the complete old server stack. It is still a
clear result: DFlash2 is not the raw token-rate winner. At 32K, prompt
processing dominated and MTP versus DFlash2 was effectively tied at 245.28
versus 245.91 prompt tokens/s, so complete request time differed by only 2.7%.

DFlash2's acceptance rate was much higher than MTP's—about 88–92% rather than
45–51%—but acceptance is not a throughput metric by itself. The DFlash draft,
verification and rollback work cost more per accepted span on this hardware.

The complete rounded dataset is available as
[CSV](/assets/data/qwen38-dflash2-production-benchmark-2026-08-25.csv).

## The router is now the obvious latency target

One more result emerged after the model comparison. A six-sample test compared
the direct `llm-fast` alias with the generic `llm` collection for the same
64-token response.

| Path | Median wall time | Added time |
| --- | ---: | ---: |
| Direct DFlash2 | 4.31s | reference |
| Generic `llm` router | 8.60s | **+4.29s** |

The logs make the cause unambiguous. The collection temporarily uses Qwen as a
routing helper and generates a 49-token route decision before forwarding the
user request. That decision took about 5.43 seconds cold and 3.94 seconds after
its prefix was cached. The eventual response generated at a similar rate; the
extra time belongs to selection.

For a long prompt this fixed cost is diluted. For an interactive short request,
doubling end-to-end time is material. The next optimisation should therefore
make ordinary `llm` traffic take a deterministic default-to-DFlash2 rule while
retaining the existing exact override. Semantic LLM classification should be
reserved for cases that actually need it.

That change is a recommendation from this benchmark, not something I have
silently counted in the published production result.

## What I would operate

I would keep the deployed split:

- repaired DFlash2 for normal stochastic work;
- no-sidecar Exact for greedy, deterministic and token-sensitive work;
- two unpinned profiles with idle KV downsizing and pressure eviction;
- bounded recurrent rollback, despite its 1.03GiB cost;
- the greedy/hybrid speculation guard as defence in depth; and
- a rollback-ready, hash-pinned b10635 runtime.

I would not revert to MTP just because it won the token-rate table. Its speed
does not close the parity boundary that motivated the separate exact path. If
MTP returns as a third non-exact option, it should first pass its own parity and
slot-reuse gate under the sampling modes clients will actually use.

The broader lesson is that speculative decoding is a systems feature, not a
single flag. The draft model, target graph shape, recurrent state lifetime,
rollback method, cache allocation, sampling policy, router and eviction manager
all participate in the answer.

The useful production result is not “DFlash2 made Qwen faster.” It is narrower
and more defensible: DFlash2 now gives the normal route a 35–44% generation
advantage over the safe Exact baseline, survives a nearly full 262K context,
and can release its memory when a larger live context needs it. The former MTP
route is faster. The repaired route is the one whose correctness boundary I can
explain and operate.

*Benchmark and deployment date: 25 August 2026. Lemonade 11.7.0; repaired
`llama.cpp` b10635 at `b576dc7dc`; Strix Halo Vulkan v0.6.11; Qwen3.8-27B
ROCmFPX-MQ Q4 target; DFlash2 sidecar revision
`2d9571f8ce46d5644596542897499006f36f5668`. The DFlash2 implementation under
test originated in [`llama.cpp` pull request #27342](https://github.com/ggml-org/llama.cpp/pull/27342).
All figures come from retained same-host qualification and production evidence.*
