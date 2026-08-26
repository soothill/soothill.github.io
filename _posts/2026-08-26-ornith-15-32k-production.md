---
layout: post
title: "Ornith 1.5 on Strix Halo: the 32K production profile"
seo_title: "Ornith 1.5 35B Vulkan performance on Strix Halo"
date: 2026-08-26 04:21:44 +0100
last_modified_at: 2026-08-26 04:21:44 +0100
permalink: /blog/2026/08/26/ornith-15-32k-production/
categories: [local-ai, engineering, benchmarks]
tags: [ornith, llama-cpp, vulkan, mtp, lemonade, strix-halo, prompt-caching]
author: Darren Soothill
editorial_standard: soothill-human-v1
editorial_review_status: approved
editorial_reviewer: Darren Soothill
editorial_reviewed_at: 2026-08-26
series: "Local LLMs on Strix Halo"
series_order: 17
description: "I qualified a patched Vulkan build for Ornith 1.5 35B on Strix Halo, lifting 32K prefill by 31% and passing two 30-minute production soaks."
---

> **Test record:** I compared two Vulkan `llama.cpp` builds with the same
> 27.2GiB Ornith-1.5-35B Q6_K file on `evox3`, my 128GB Ryzen AI MAX+ 395 / Radeon
> 8060S workstation. The safety-patched b10641 build increased prompt processing
> by **47.5% at zero depth**, **33.2% at 16K** and **31.2% at 32K** when I used a
> 2,048-token physical batch. It then passed two separate 30-minute soaks: one
> against `llama-server` directly and one through Lemonade 11.7.0. Each run
> completed 150 structured responses, 150 isolation checks, 150 prompt-cache
> pairs, 150 cancellation recoveries and three 31K-prompt long outputs. I
> deployed it as an explicit 32K fast profile, not as the default model.

Ornith is now on the production service on `evox3`. It is not the default
model, and it is not pretending to have a qualified 262K context.

That distinction matters. [Ornith-1.5-35B-A3B](https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B)
is a 35B mixture-of-experts model with roughly 3B parameters active for each
token. It has always been quick on this machine. My earlier developer test put
it at 52.3 generated tokens per second and a mean of 5.9 seconds per task,
against 9.5 tokens per second and 36.2 seconds for a dense Qwen3.8 Q6 control.
The compromise was first-pass correctness: Ornith passed 14 of 20 tasks and
Qwen passed 18.

So the useful production role was already fairly clear. Ornith could be the
fast coding and agent option, while Qwen remained the safer default for an
awkward first answer. What I did not yet have was a build and launch profile I
was prepared to leave behind Lemonade.

## The physical batch changed the result

The new candidate came from Laurent Zuijdwijk's
[b10641 `llama.cpp` release](https://github.com/LaurentZuijdwijk/llama.cpp/releases/tag/b10641).
The supplied Linux binary needed newer system libraries than this host, so I
built the source locally against the Vulkan stack already qualified on the
machine.

I kept the model, driver, flash-attention setting and Q8_0 K/V cache fixed. The
control was my existing safety-patched b10635 Vulkan build. Each benchmark cell
contains three samples. The zero-depth matrix was repeated in an A-B-B-A launch
order so a warm machine or simple run order could not explain the difference.

| Prompt position | Physical batch | b10635 prompt tok/s | Patched b10641 prompt tok/s | Change |
| --- | ---: | ---: | ---: | ---: |
| Start of context | 512 | 931.33 | 995.17 | +6.9% |
| Start of context | 2,048 | 930.07 | 1,371.99 | **+47.5%** |
| 16K depth | 2,048 | 744.09 | 991.16 | **+33.2%** |
| 32K depth | 2,048 | 542.79 | 712.13 | **+31.2%** |

At a 512-token physical batch, b10641 was a normal incremental improvement.
At 2,048 it was a different result. The older build gained nothing from making
the physical batch wider at zero depth; b10641 processed the same 2,048-token
prompt at about 1,372 rather than 930 tokens per second.

The advantage survived a filled cache. Inside b10641, moving from a 512- to a
2,048-token physical batch increased prompt processing by 28.3% at 16K and
10.9% at 32K. That is why the production recipe uses `batch=2048` and
`ubatch=2048`. Copying the new binary while leaving the old 512-token
micro-batch would discard much of the improvement I was trying to deploy.

I did not reproduce the release author's absolute 1,616–1,648 tokens per second.
Those figures used a smaller Q4_K_M model, while my retained production quant
is Q6_K. The matched result on my own weights is the useful comparison here.

## I did not deploy the fork untouched

The first b10641 build exposed a more important problem in a different model.
Sequential Qwen3.8 requests began repeating text from an earlier prompt. The
headline token rate looked excellent because the server was generating the
wrong text very quickly.

My production Qwen runtime already contained two relevant protections: it
zeroed recycled recurrent state before a new request used it, and it disabled
recurrent or hybrid speculation during greedy sampling. I ported those changes
to b10641 before treating the Ornith measurements as a deployment candidate.

The final build passed the Qwen, Nemotron-H and DeepSeek V4 rollback, split
replay and full reset/reuse tests with a maximum logits difference of zero. Its
model-resolution test also passed. Ornith is not using Qwen's recurrent path,
but I did not want a second production binary carrying a known request-reuse
fault merely because this particular model avoided it.

That safety port is part of the runtime described in this article. A stock
b10641 binary is not the same production artefact.

## The profile I actually deployed

The server sits behind Lemonade 11.7.0 on the existing port 13305. Clients can
select it as `ornith`, `ornith35` or by its full model name. Lemonade starts a
loopback-only backend; there is no second externally exposed inference port.

| Setting | Production value |
| --- | --- |
| Model | Ornith-1.5-35B-A3B Q6_K, 27.2GiB |
| Runtime | safety-patched b10641, commit `28a3e60` |
| Vulkan userspace driver | Strix Halo v0.6.11 |
| Context | 32,768 tokens |
| Batch / physical batch | 2,048 / 2,048 |
| K/V cache | Q8_0 / Q8_0 |
| Flash Attention | enabled |
| Request slots | 1 |
| Host prompt cache | 8GiB |
| Speculation | adaptive native MTP, 2–4 draft tokens |
| Idle KV-cache downsize | 120 seconds |
| Full idle eviction | 900 seconds |

The significant Lemonade arguments are:

```text
--ctx-size 32768
--batch-size 2048 --ubatch-size 2048
--cache-type-k q8_0 --cache-type-v q8_0
--cache-ram 8192 --cache-idle-slots --cache-prompt
--flash-attn on --parallel 1
--spec-type draft-mtp --spec-draft-adaptive
--spec-draft-n-min 2 --spec-draft-n-max 4 --spec-draft-p-min 0
```

I kept one slot. The multi-slot integrated-GPU response-isolation fault is not
something a fast prefill result makes irrelevant, and this workload is intended
for one interactive agent at a time. Lemonade may keep two different LLMs
loaded, but each llama.cpp backend in this route has one request slot.

The profile is also unpinned. After two idle minutes Lemonade can discard its
KV state; after 15 minutes it can unload the model. The alias remains available
and the next request loads it normally. This lets Ornith and Qwen coexist
without turning an optional fast model into a permanent 27GiB reservation.

## The second soak was deliberately repetitive

The first 30-minute run talked directly to the patched `llama-server`. It
proved that the model, cache and speculative path were stable. I then repeated
the same workload through a private Lemonade 11.7.0 instance using the exact
registry, alias and launcher intended for production.

| Measurement | Direct server | Through Lemonade |
| --- | ---: | ---: |
| Elapsed time | 1,807.39s | 1,806.23s |
| Structured JSON | 150/150 valid | 150/150 valid |
| Isolation checks | 150/150 passed | 150/150 passed |
| Cache fill/hit pairs | 150/150 passed | 150/150 passed |
| Cancel and recover | 150/150 passed | 150/150 passed |
| 31K prompt + 768 output | 3/3 passed | 3/3 passed |
| Structured generation | 67.47 tok/s | 67.38 tok/s |
| Long-prose generation | 49.82 tok/s | 49.57 tok/s |
| Server errors / GPU faults | 0 / 0 | 0 / 0 |

Lemonade changed structured generation by -0.13% and long generation by
-0.50%. Those are noise-sized differences. The integration layer did not give
back the model speed established by the direct test.

Each structured request had to return a JSON object containing every integer
from 0 to 127. The isolation request carried a new marker and failed if text
from an older request appeared. Every cache pair repeated a 4,117-token prompt;
the warm request reused at least 4,113 tokens and returned the same output as
the fill request.

The cancellation step opened a 4,096-token stream, read six chunks, closed the
connection and then asked for a new marker. All 150 recovery requests completed
without inheriting text from the cancelled stream. That matters more to me
than another short decode sample because agents cancel work routinely.

## MTP still helped when acceptance fell

The structured workload was friendly to native MTP. Median draft acceptance
was 53.9% through Lemonade, and generation held at 67.38 tokens per second.
The long prose prompts were harder: acceptance fell to 38.5%, while generation
settled at 49.57 tokens per second.

That lower-acceptance case is the one I wanted to see survive. A speculative
profile that is only quick when the answer is repetitive can look very good in
a JSON demonstration and disappoint on ordinary prose. Here the long task
still completed all 768 requested output tokens three times, with no repeated
loop, early ending or server fault.

This does not prove that adaptive MTP wins on every Ornith request. The soak
was a lifecycle and stability gate, not a fixed-versus-adaptive A/B benchmark.
It shows that the selected policy remained useful and correct on both a
high-acceptance structured task and a materially lower-acceptance prose task.

## Why production stops at 32K

The GGUF metadata advertises a 262,144-token architectural window. Lemonade's
catalogue therefore displays 262K even though the running process is explicitly
started with `--ctx-size 32768`.

That is intentional. I measured the 2,048-token physical batch at 16K and 32K.
I did not qualify it at 64K, where the fork warns that the wide physical batch
can trigger a Vulkan ring timeout. The safer 512-token physical batch remains
available for a later long-context profile, but it would give up part of the
prefill improvement documented here.

I would rather operate one honest 32K profile than publish the model's maximum
window beside settings I have not tested. Extending it needs a separate 64K
and 128K matrix, followed by the same cache, cancellation and long-output soak.

## Where Ornith now fits

Qwen remains the default route. The earlier developer set found more correct
first answers from Qwen, especially around validation, state reconciliation
and streaming boundaries. None of the new prefill work changes that result.

Ornith is now the explicit fast option for work where an agent can compile,
test and repair its answer. It is particularly attractive when the prompt is
large enough for the new 2,048-token physical batch to matter. The production
aliases make that choice visible rather than quietly changing the behaviour of
the general `llm` route.

I kept the final arrangement because it has a narrow, defensible claim:

- the Q6 model and patched b10641 build are materially faster at prompt
  processing than the matched b10635 control;
- the exact Lemonade profile passed two independent 30-minute lifecycle runs;
- 32K is the tested context boundary for the wide physical batch; and
- Qwen still owns the default route because this work did not repeat or reverse
  the developer-quality comparison.

The complete [prefill samples](/assets/data/ornith15-b10641-prefill-2026-08-26.csv),
[soak summary](/assets/data/ornith15-b10641-soak-2026-08-26.csv) and
[deployment manifest](/assets/data/ornith15-b10641-production-manifest-2026-08-26.json)
retain the unrounded measurements, model and runtime hashes, launch settings
and evidence boundaries used for this decision.
