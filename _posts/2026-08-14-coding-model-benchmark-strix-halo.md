---
layout: post
title: "19 coding models on Strix Halo: what I would run"
seo_title: "Coding model benchmark on Strix Halo: 19 models"
date: 2026-08-14 10:00:00 +0100
last_modified_at: 2026-08-14 10:00:00 +0100
permalink: /blog/2026/08/14/coding-model-benchmark-strix-halo/
categories: [local-ai, benchmarks, engineering]
tags: [coding-models, strix-halo, llama-cpp, rocm, lemonade, qwen, gpt-oss, nemotron]
author: Darren Soothill
series: "Local LLMs on Strix Halo"
series_order: 10
description: "I ran 19 local coding models through 190 executable tasks on a 128GB Strix Halo workstation, comparing accuracy, latency and context limits."
---

> **Test record:** I ran 19 locally installed model deployments through ten
> executable coding tasks on `evox3`, a 128GB GMKtec EVO-X3 with a Ryzen AI
> MAX+ 395 and Radeon 8060S. All **190/190 model-task requests completed**.
> `gpt-oss-120b` led accuracy at **9/10**. Qwen AgentWorld reached **8/10 in
> 7.2 seconds per task**, making it the strongest interactive result. The
> published context ceilings ranged from 131,072 to 1,048,576 tokens, but every
> comparable coding result used the same 32,768-token context. The model with
> the longest context was not the best coder, and the fastest decoder was not
> the most accurate.

A local model can fit in memory, advertise a million-token context and produce
tokens quickly, yet still be the wrong model for everyday coding.

Those are three separate product questions:

1. Does the first answer actually work?
2. How long does the useful answer take?
3. How much context can the model and this runtime realistically hold?

I had benchmarked parts of this portfolio while bringing several new models
online. I reran the complete matrix in one controlled pass after fixing the
special runtime paths for Nemotron Puzzle and DeepSeek V4 Flash. That produced
a cleaner result: one profile, 19 deployments, 190 executable answers and an
automatic return to the production model afterwards.

The deployment decision did not change. The evidence behind it became much
better.

## The short answer

| Role | Model | Result | Why I would use it |
| --- | --- | ---: | --- |
| Interactive default | Qwen AgentWorld 35B-A3B Q6_K | 8/10; 7.2s/task | Best latency at the 80% quality tier; production-configured at 262K context |
| Accuracy tier | gpt-oss-120b MXFP4 | 9/10; 21.2s/task | Only model to pass nine tasks; use for difficult work and final review |
| Fast draft | Qwen3-Coder 30B-A3B Q4_K_S | 5/10; 4.0s/task | Fastest completed answers, but the quality loss is large |
| Long-context candidate to retain | Nemotron Puzzle 75B-A9B Q4_K_M | 6/10; 14.6s/task | Stable repaired runtime and a publisher-supported 1M ceiling that still needs local long-context qualification |
| Do not use as the default | Qwopus3.6-27B preview Q6_K | 5/10; 165.4s/task | Less accurate and more than nine times slower than base Qwen3.6-27B |

`gpt-oss-120b` is the quality winner. AgentWorld is the product winner for the
common path. That distinction matters more than declaring one universal
champion.

## What the benchmark measured

The suite uses ten first-response tasks covering interval merging, dependency
graphs, nested configuration updates, robust JSONL processing, bounded async
concurrency, HTTP retry semantics, SQL window queries, path traversal defence,
transactional inventory reconciliation and lazy iteration.

A response passes only when its extracted code passes every hidden executable
test for that task. Generated code runs as a non-root user in a read-only Docker
container with networking disabled, capabilities dropped and CPU, memory,
process and wall-time limits.

Every row used:

- 32,768 context tokens;
- a 2,048-token output ceiling;
- temperature 0;
- top-p 1 and presence penalty 0;
- thinking disabled;
- one first response, with no repair turn.

The score is therefore a small diagnostic pass@1, not a claim to reproduce
SWE-bench or a complete repository agent. It is deliberately strict and easy
to audit: either the code passed or it did not.

## All 19 results, including maximum context

The context column is the maximum the publisher advertises or supports for the
base model. It is **not** the context used by this coding run. Native and
extended limits are shown separately where the publisher requires YaRN or
another override.

| Model deployment | Maximum supported context | Accuracy | Wall s/task | Decode tok/s |
| --- | ---: | ---: | ---: | ---: |
| [gpt-oss-120b MXFP4](https://developers.openai.com/api/docs/models/gpt-oss-120b) | 131,072 | **9/10** | 21.2 | 50.2 |
| [Qwen AgentWorld 35B-A3B Q6_K](https://huggingface.co/Qwen/Qwen-AgentWorld-35B-A3B) | 262,144 | **8/10** | **7.2** | 50.7 |
| [Qwen3.6-27B Q6_K MTP](https://huggingface.co/Qwen/Qwen3.6-27B) | 262,144 native; 1,010,000 YaRN | **8/10** | 17.9 | 20.7 |
| [Qwen3.5-122B-A10B GGUF](https://huggingface.co/Qwen/Qwen3.5-122B-A10B) | 262,144 native; 1,010,000 YaRN | 7/10 | 14.1 | 20.8 |
| [Qwen3.5-122B-A10B GPTQ/vLLM](https://huggingface.co/Qwen/Qwen3.5-122B-A10B) | 262,144 native; 1,010,000 YaRN | 7/10 | 21.2 | — |
| [Gemma 4 31B QAT Q4_0](https://huggingface.co/google/gemma-4-31B-it) | 262,144 | 7/10 | 22.8 | 11.4 |
| [Qwen3.6-35B-A3B UD-Q6_K MTP](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) | 262,144 native; 1,010,000 YaRN | 6/10 | **7.3** | 59.5 |
| [Nemotron Puzzle 75B-A9B Q4_K_M](https://huggingface.co/nvidia/NVIDIA-Nemotron-Labs-3-Puzzle-75B-A9B-NVFP4) | 1,048,576; default config 262,144 | 6/10 | 14.6 | 18.0 |
| [Devstral Small 2 24B Q4_K_M](https://huggingface.co/mistralai/Devstral-Small-2-24B-Instruct-2512) | 262,144 advertised | 6/10 | 15.9 | 15.0 |
| [Devstral Small 2 24B Q6_K](https://huggingface.co/mistralai/Devstral-Small-2-24B-Instruct-2512) | 262,144 advertised | 6/10 | 20.0 | 11.5 |
| [Mistral Medium 3.5 128B Q4_K_M](https://huggingface.co/mistralai/Mistral-Medium-3.5-128B) | 262,144 | 6/10 | 70.4 | 3.0 |
| [Qwen3-Coder 30B-A3B Q4_K_S](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct) | 262,144 native; about 1M YaRN | 5/10 | **4.0** | **67.5** |
| [Qwen3-Coder 30B-A3B Q4_K_M](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct) | 262,144 native; about 1M YaRN | 5/10 | 4.1 | 65.9 |
| [Nemotron 3.5 Lightning 30B-A3B Q8_0](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16) | 1,048,576 | 5/10 | 5.6 | 50.9 |
| [Qwen3-Coder-Next Q5_K_M](https://huggingface.co/Qwen/Qwen3-Coder-Next) | 262,144 | 5/10 | 10.0 | 43.7 |
| [Qwopus3.6-27B preview Q6_K](https://huggingface.co/Jackrong/Qwopus3.6-27B-v1-preview-GGUF) | 262,144 native; 1,010,000 YaRN | 5/10 | 165.4 | 9.6 |
| [DeepSeek V4 Flash ROCmFP3 mixed](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash-0731) | 1,048,576 | 4/10 | 45.5 | — |
| [DeepSeek Coder V2 MLA-IQ3_M](https://huggingface.co/deepseek-ai/DeepSeek-Coder-V2-Instruct) | 131,072 advertised | 3/10 | 22.5 | 13.8 |
| [Qwen3.5-0.8B FP16/vLLM](https://huggingface.co/Qwen/Qwen3.5-0.8B) | 262,144 | 0/10 | 14.3 | — |

There are two source discrepancies worth keeping visible. DeepSeek advertises
DeepSeek Coder V2 as 128K, while its Hugging Face configuration and the local
registration declare 163,840 positions. Devstral Small 2 is advertised and
launched by Mistral at 262,144, while its current text configuration declares
393,216. I use the conservative publisher-advertised ceiling in the table
rather than converting a larger configuration field into an untested promise.

The [machine-readable result table](/assets/data/evox3-coding-model-benchmark-2026-08-14.csv)
contains the exact unrounded measurements, installed sizes and native/maximum
context fields.

## Accuracy and decode rate did not move together

The fastest decoder was Qwen3-Coder 30B-A3B Q4_K_S at 67.5 tokens per second.
It passed only five tasks. Qwen3.6-35B-A3B reached 59.5 tokens per second and
passed six. Nemotron Lightning reached 50.9 and also passed five.

`gpt-oss-120b` decoded at 50.2 tokens per second—slower on paper than all three
of those models—and passed nine tasks. Its wall time was still 21.2 seconds per
task because it emitted an average of 1,020 output tokens. AgentWorld decoded
at a similar 50.7 tokens per second but emitted 342, returning in 7.2 seconds.

That is why decode throughput alone is a poor interactive product metric. A
model that writes three times as much can have the same token rate and feel
three times slower. A model that emits a short wrong answer can look excellent
on a throughput chart.

For the normal coding loop I would take AgentWorld's 8/10 at 7.2 seconds. For a
hard review where another correct task matters more than fourteen additional
seconds, I would explicitly load gpt-oss.

## The backend and quant still matter

The two Qwen3.5-122B deployments used the same base model and both scored 7/10.
The GGUF/llama.cpp route finished in 14.1 seconds per task and loaded in 34.6
seconds. GPTQ/vLLM needed 21.2 seconds per task and 100.1 seconds to load. On
this machine, GGUF is the better single-user 122B path.

Devstral made the quantisation decision even clearer. Q4_K_M and Q6_K passed
the same six tasks with the same pass pattern. Q4 used 4.67GiB less installed
storage, decoded at 15.0 rather than 11.5 tokens per second and finished about
four seconds sooner. The larger quant bought nothing measurable in this suite.

The two original Qwen3-Coder quants also tied at 5/10. Q4_K_S was slightly
faster and smaller. Once correctness is tied, the operational choice becomes
easy.

## Maximum context is a capability claim, not a free feature

The table contains several million-token models. That does not mean I tested a
million-token coding prompt on every one of them, or that a 128GB workstation
can allocate each advertised window with the chosen cache precision and still
remain useful.

There are at least four different numbers that often get collapsed into
“context length”:

1. the model's native trained or configured window;
2. a publisher-supported extension using YaRN or another RoPE override;
3. the context the serving runtime is configured to allocate;
4. the number of input and output tokens a specific test actually consumes.

This benchmark used 32,768 for number three and much less for number four.
AgentWorld separately reproduced its 8/10 result with the server allocated at
262,144, which supports keeping that production configuration. It was not a
262K-filled prompt test.

Qwen's 1,010,000-token modes require explicit YaRN configuration. Nemotron
Puzzle supports 1M even though its default Hugging Face configuration is 256K.
NVIDIA's Nemotron Lightning card makes the hardware qualification explicit:
the model supports 1M, while a single 80GB H100 BF16 recipe is limited to 256K
by memory. The model ceiling and the deployable ceiling are not always the same
thing.

I would therefore treat context as a workload-specific qualification. Load the
intended cache precision, fill the actual prompt range, measure prompt
processing and memory, verify retrieval quality near the end of the window,
then run a soak. A successful server start at `--ctx-size 1048576` is only the
first check.

## The two repaired models now belong in the comparison

Nemotron Puzzle and DeepSeek V4 Flash initially failed for different reasons.

Puzzle's GGUF contains per-layer expert widths and top-k values plus an embedded
two-layer MTP head. The general llama.cpp build expected scalar expert
metadata. I built the exact Puzzle/MTP revision pinned by the quantisation
manifest and routed only that model to it. Puzzle then completed the full suite
twice with the same 6/10 pass pattern.

DeepSeek V4 Flash uses a custom ROCmFP3 mixed tensor format that general
llama.cpp does not understand. The existing qualified Lucebox backend could
load it, so Lemonade now dispatches that filename to the specialised runtime.
It completed all ten requests, scoring 5/10 in the first repaired run and 4/10
in the full repeat. The runtime problem is fixed; the task-level variance and
45.5-second latency still make it a poor default for this workload.

This is the right separation of concerns. “It loads” is a runtime result. “It
passed four tasks” is a model result. Both belong in the record.

## The repeat was reassuringly boring

Seventeen of the eighteen models with a previous complete ten-task result
reproduced their accuracy exactly. DeepSeek V4 Flash was the only movement,
losing the `retry_after` task. Qwopus had previously been stopped after a
partial result; this time it completed at 5/10.

Qwopus also demonstrated why completing the row mattered. It averaged 1,573
output tokens and 165.4 seconds per task. Base Qwen3.6-27B passed eight tasks in
17.9 seconds. The preview's advertised long context is real metadata, but it
does not rescue the observed coding product.

All 19 models loaded, all 190 task requests completed, the evaluator reference
implementation passed, and the benchmark automatically restored AgentWorld at
its 262,144-token production context. There was one llama-server process left:
the intended production backend.

## What I would operate

The portfolio I would keep is smaller than the benchmark matrix:

- **Qwen AgentWorld 35B-A3B Q6_K** as the interactive default;
- **gpt-oss-120b MXFP4** as the explicit accuracy and review tier;
- **Qwen3-Coder 30B-A3B Q4_K_S** only when rapid drafting is worth a large
  measured quality trade-off;
- **Qwen3.5-122B GGUF** for Qwen-specific 122B work and long-context
  qualification;
- **Nemotron Puzzle** as a retained specialist while its isolated runtime is
  required;
- every other row as evaluation inventory rather than an automatically routed
  production choice.

I would not make the million-token number the routing policy. I would route on
the actual task: interactive edit, difficult verification, long document or
model-specific evaluation. Context, correctness and response time remain
separate controls.

The useful outcome of testing 19 deployments is not that the workstation should
serve all 19. It is knowing which two deserve to be easy to reach—and why.

*Sources checked 14 August 2026: the linked publisher model cards and current
Hugging Face configurations for Qwen, OpenAI gpt-oss, NVIDIA Nemotron, Google
Gemma, Mistral, DeepSeek and Qwopus. Context ceilings are publisher/configuration
claims unless explicitly described as an EVO-X3 test. Benchmark figures come
from the single deterministic 19-model rerun completed on 14 August 2026.*
