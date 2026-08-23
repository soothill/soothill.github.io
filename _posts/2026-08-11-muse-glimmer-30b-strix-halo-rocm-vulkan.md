---
layout: post
title: "Muse Glimmer 30B on Strix Halo: Vulkan passed the 8K test"
seo_title: "Muse Glimmer 30B on Strix Halo: ROCm vs Vulkan"
date: 2026-08-11 12:38:41 +0100
last_modified_at: 2026-08-11 12:38:41 +0100
permalink: /blog/2026/08/11/muse-glimmer-30b-strix-halo-rocm-vulkan/
categories: [local-ai, benchmarks, engineering]
tags: [muse-glimmer, llama-cpp, rocm, vulkan, strix-halo, dflash, speculative-decoding, multimodal]
author: Darren Soothill
editorial_standard: soothill-human-v1
editorial_review_status: approved
editorial_reviewer: Darren Soothill
editorial_reviewed_at: 2026-08-23
series: "Local LLMs on Strix Halo"
series_order: 12
description: "Muse Glimmer 30B reaches 42 tok/s with DFlash on ROCm, but an 8K correctness test makes Vulkan the safer Strix Halo deployment."
---

> **Test record:** I qualified [Muse Glimmer 30B](https://huggingface.co/meta-models/Muse-Glimmer-30B-GGUF)
> on a 128GB GMKtec EVO-X3 with a Ryzen AI MAX+ 395 / Radeon 8060S
> (`gfx1151`). I built the same [`llama.cpp` b10362 commit](https://github.com/ggml-org/llama.cpp/commit/4801e3c567d5131dd41b387df5f2d4b1370d92be)
> for ROCm 7.14 and Vulkan. ROCm processed a 2,048-token prompt at **434.59
> tok/s** and reached **42.38 tok/s** on a favourable DFlash workload. Vulkan
> was much slower at prompt processing, but it was the only backend to pass the
> fresh 8K passkey test. I kept Vulkan without speculative decoding for the
> correctness-first service and retained ROCm plus DFlash as a short-context
> speed profile.

For the first half of this test, ROCm looked like the easy choice. It was roughly twice as fast as Vulkan at prompt processing on the dynamic quant, and DFlash could push a favourable generation task beyond 40 tokens/s.

Then I moved the passkey beyond roughly 4,000 tokens. ROCm stopped returning the right value; Vulkan returned it exactly at 8,000 tokens. That one failure changed the deployment decision.

Muse Glimmer is a dense 29.6B-parameter multimodal model with tool calling, a 131,072-token context window and a separate DFlash draft model. Both published quants and the vision projector fit comfortably in the EVO-X3's 128GB unified memory. Fit was not the problem. The test was about how much speed I could use without narrowing the model's working context by accident.

## The numbers that shaped the decision

| Requirement | Retained configuration | Result |
|---|---|---|
| Highest prompt-processing rate | ROCm, dynamic quant, no HIP graphs | **434.59 tok/s** at pp2048 |
| Highest target-only baseline decode | Vulkan, 17GB quant | **12.96 tok/s** at tg128 |
| Highest favourable speculative result | ROCm, 17GB quant, DFlash `n-max=15` | **42.38 tok/s** mean |
| More representative ROCm DFlash set | ROCm, 17GB quant, three 512-token tasks | **23.46 tok/s** mean |
| Qualified longer-context route | Vulkan, dynamic quant, no DFlash | exact 8K passkey returned |
| Vision and tool use | dynamic quant with projector / Jinja tool parser | both returned correct structured results |

The distinction between “highest favourable result” and “representative set” is deliberate. Speculative decoding accelerates accepted draft tokens; its benefit changes with the prompt and output. A single arithmetic loop is useful for tuning the ceiling, but it is not an honest forecast for coding, explanation and operational writing.

## The exact build I tested

The test host was the same `evox3` workstation used throughout this series:

| Component | Tested state |
|---|---|
| Host | GMKtec EVO-X3, Ryzen AI MAX+ 395, Radeon 8060S (`gfx1151`), 128GB installed / 124GiB visible |
| Operating system | Ubuntu 24.04, kernel `6.17.0-40` |
| ROCm | 7.14.0 |
| `llama.cpp` | b10362, commit `4801e3c567d5131dd41b387df5f2d4b1370d92be` |
| Model revision | `a0532f7263ee67f1e0a5f5c5fdcd50dd62fc9aa4` |
| Attention | flash attention enabled |
| Prompt batch / micro-batch | 8,192 / 2,048 |
| Parallel slots | one |

I tested both model quants published in the official repository rather than treating the filename as provenance:

| Artefact | Size | SHA-256 | Model-card quality note |
|---|---:|---|---:|
| `muse-glimmer-30B-kquant-17gb.gguf` | 16.76GB | `7e9b74b7c8875e9e265695df9613bf6290f2392e479ce740495a129019c488d8` | about 1.0% degradation |
| `muse-glimmer-30B-kquant-dynamic.gguf` | 19.65GB | `513109c8319115f69eb09fb7b118c97c8167d15bc014fd7670d2e30489bf106c` | about 0.2% degradation |
| `mmproj-kquant.gguf` | 1.40GB | `f48b452316f9b213758e8659444029b961a24a07f99a1abb2a9f88b06f7c00c6` | vision projector |
| `dflash-kquant.gguf` | 1.63GB | `27d9a805fa29b943cfb6ad4843367cd4eaaaf06bd452d8cc3e00a2cd18a677bc` | DFlash drafter |

The dynamic quant is the quality-first choice because this machine has ample capacity. The 17GB quant remains useful for a speed profile: it decoded 17% faster than dynamic under the ROCm target-only baseline and leaves more memory for other services.

Muse Glimmer support landed through [`llama.cpp` PR #26841](https://github.com/ggml-org/llama.cpp/pull/26841). The model card requires b10353 or newer; using b10362 keeps the model architecture, chat parser, vision path and DFlash integration on one exact source revision for both backends.

## Building both backends

The ROCm build targets the APU explicitly and disables HIP graphs, because the graph-enabled control was fractionally slower in every retained benchmark:

```bash
cmake -S . -B build-rocm \
  -DGGML_HIP=ON \
  -DGGML_HIP_GRAPHS=OFF \
  -DAMDGPU_TARGETS=gfx1151 \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build-rocm --config Release -j
```

The Vulkan build uses the same source tree and release mode:

```bash
cmake -S . -B build-vulkan \
  -DGGML_VULKAN=ON \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build-vulkan --config Release -j
```

The common benchmark shape was pp2048 and tg128, repeated three times with all layers on the GPU, flash attention enabled, an 8,192-token batch and 2,048-token micro-batch. Model loading was excluded from the timed result.

## ROCm won prefill; Vulkan narrowly won baseline decode

| Quant | Backend | HIP graphs | pp2048 | tg128 |
|---|---|---:|---:|---:|
| 17GB | ROCm 7.14 | off | **427.94 ± 2.64** | 12.428 ± 0.003 |
| 17GB | ROCm 7.14 | on | 424.57 | 12.416 |
| 17GB | Vulkan | n/a | 240.51 | **12.961** |
| dynamic | ROCm 7.14 | off | **434.59 ± 1.79** | 10.594 ± 0.001 |
| dynamic | ROCm 7.14 | on | 433.54 | 10.577 |
| dynamic | Vulkan | n/a | 216.12 | **10.779** |

ROCm was 78% faster than Vulkan in 17GB-quant prompt processing and just over twice as fast with the dynamic quant. Vulkan reversed the target-only generation result, but only narrowly: 4.3% on the 17GB quant and 1.8% on dynamic.

HIP graphs did not create a useful ROCm win. Disabling them improved prompt processing by 0.8% on the 17GB quant and 0.2% on dynamic; generation changed by around one tenth of one percent. I retained the simpler graph-disabled build rather than adding a moving part for a negative result.

These are microbenchmarks, not complete chat-request rates. They isolate prompt processing and autoregressive generation so the backend differences are visible; the later correctness and feature tests decide whether a configuration is deployable.

## DFlash made ROCm much faster on the right output

The official DFlash model is not plug-and-play with the current GGUF metadata. Its `muse-glimmer.attention.sliding_window_pattern` is encoded as an array of booleans, while the current DFlash binding expects the scalar pattern. That mismatch is tracked in [`llama.cpp` issue #26894](https://github.com/ggml-org/llama.cpp/issues/26894) and can terminate model loading with a `vector::_M_range_check` exception.

The non-destructive workaround is an explicit metadata override:

```text
--override-kv muse-glimmer.attention.sliding_window_pattern=int:4
```

That scalar represents the published local/local/local/global attention cycle. DFlash also needs an explicit speculation type in this build:

```text
-md dflash-kquant.gguf
--spec-type draft-dflash
--spec-draft-n-max 15
-ngld 99
```

The last tuning control was decisive. The default maximum of three draft tokens left most of the opportunity unused. Seven was slower on the coding control, while 15 matched the DFlash block shape and won clearly.

| ROCm 17GB workload | DFlash maximum | Generation rate | Draft counters where retained |
|---|---:|---:|---|
| target-only tg128 baseline | off | 12.428 tok/s | n/a |
| favourable integer set, three runs | 3 | 19.84 tok/s mean | not retained |
| favourable integer set, three runs | **15** | **42.38 tok/s mean** | not retained |
| 512-token coding task | 15 | 34.85 tok/s | 411 accepted / 1,480 drafted |
| 512-token B-tree explanation | 15 | 17.38 tok/s | 309 / 2,996 |
| 512-token PostgreSQL checklist | 15 | 18.14 tok/s | 318 / 2,823 |

The three representative 512-token tasks averaged **23.46 tok/s**, 1.89 times the target-only baseline. The favourable integer set averaged 42.38 tok/s, 3.41 times baseline. Both are true; only the first is a reasonable planning number for mixed work.

Dynamic plus DFlash showed the same shape. A favourable integer run reached 43.87 tok/s, coding reached 31.03 and the B-tree explanation reached 17.68. With seed 123, the speculative and target-only paths also returned identical final content for an exact addition check: `12345 + 67890 = 80,235.`

This is the strongest ROCm performance result in the study. I still did not make it the default, because it only helps inside the context range that returns the right answer.

## The context test changed the deployment decision

I inserted a unique passkey at the start of progressively longer prompts and asked for that exact value at the end. Each important boundary was repeated from a fresh server so the result did not depend on a reused slot cache.

| Backend and mode | Approximate prompt tokens | Result |
|---|---:|---|
| ROCm, dynamic, no DFlash | 1,086 | pass |
| ROCm, dynamic, no DFlash | 2,586 | pass |
| ROCm, dynamic, no DFlash | 4,086 | pass |
| ROCm, dynamic, no DFlash | 6,037 | repeated output followed by parser HTTP 500 |
| ROCm, dynamic, no DFlash | 8,086 | failed to retrieve passkey |
| ROCm, dynamic, no DFlash | 32,089 | failed to retrieve passkey |
| Vulkan, dynamic, no DFlash | 8,000 | **exact passkey returned** |
| Vulkan, dynamic, DFlash 15 | 8,000 | **exact passkey returned** |

The ROCm slot really had a 131,072-token context and processed the full prompt; this was not a server-side truncation. Turning flash attention off did not repair the 8K result. The override is also equivalent to the model's repeated local/local/local/global metadata, so the evidence does not point to a changed attention pattern.

I am describing this narrowly as a **current b10362 / ROCm 7.14 / `gfx1151` long-context correctness regression**. The test does not prove a universal ROCm fault or identify the kernel responsible. It does establish a deployment boundary on this exact machine: I will not expose the ROCm route as a long-context endpoint until a newer build passes the same retrieval gate.

Vulkan returned `HALO-MUSE-VULKAN-8000` exactly without speculation. At that depth it processed the prompt at 198.59 tok/s and generated at 10.71 tok/s. DFlash also returned its passkey, but generation fell to 6.96 tok/s because acceptance was poor. On a favourable short integer task, Vulkan DFlash improved dynamic generation by only about 15%. Those controls make the Vulkan choice straightforward: run the target model alone.

I tested 8K retrieval, not the model's full advertised 131K window. The server can be configured for 131,072 tokens, but that is capacity rather than a published correctness claim. I would qualify 16K, 32K, 64K and 128K before promising the full window to users.

## Vision and tool calling

The model's non-text features worked on the same source revision.

With `mmproj-kquant.gguf`, Muse Glimmer correctly identified a supplied GitHub icon. Loading the first image increased GPU-visible GTT by about 346MiB. I then compared two 10,016-token prefill controls before and after the image: 390.52 and 400.91 tok/s. That does **not** reproduce the first-image prefill collapse reported for CUDA in [`llama.cpp` issue #26873](https://github.com/ggml-org/llama.cpp/issues/26873), although the extra retained memory was visible.

The Jinja tool path also returned a valid OpenAI-compatible `tool_calls` response for a weather lookup, with the expected `get_weather` function and `{"city":"Paris"}` arguments. Reasoning appeared separately from final content, and the ordinary arithmetic smoke test returned 391 for 17 × 23.

Those feature checks matter because a fast text-only benchmark does not prove that the model's actual product surface—images, reasoning and structured tools—survives the selected build.

## What I would deploy

### Correctness-first service

The default is the dynamic quant on Vulkan, without DFlash. This command exposes only loopback, keeps one slot, and caps the qualified endpoint at 8K:

```bash
./build-vulkan/bin/llama-server \
  -m muse-glimmer-30B-kquant-dynamic.gguf \
  --mmproj mmproj-kquant.gguf \
  -ngl 99 -fa on \
  -c 8192 -np 1 \
  -b 8192 -ub 2048 \
  --load-mode none --no-host --fit off \
  --jinja --temp 1.0 --top-p 0.95 --top-k 64 \
  --host 127.0.0.1 --port 18090
```

The model supports a 131,072-token context, so the context can be raised after each longer retrieval and multi-turn compaction gate passes. Keeping `-np 1` avoids silently dividing the configured context across slots. A public or LAN-facing service also needs authentication and a deliberate network policy; loopback is the safe baseline.

### Fast short-context service

For workloads capped at 4K, the 17GB ROCm quant plus DFlash is the useful speed profile:

```bash
./build-rocm/bin/llama-server \
  -m muse-glimmer-30B-kquant-17gb.gguf \
  -md dflash-kquant.gguf \
  --spec-type draft-dflash \
  --spec-draft-n-max 15 \
  --override-kv muse-glimmer.attention.sliding_window_pattern=int:4 \
  -ngl 99 -ngld 99 -fa on \
  -c 4096 -np 1 \
  -b 8192 -ub 2048 \
  --load-mode none --no-host --fit off \
  --jinja --temp 1.0 --top-p 0.95 --top-k 64 \
  --host 127.0.0.1 --port 18091
```

The context cap is a safety control derived from the observed boundary, not a property of the model. I would remove it only when that exact ROCm build passes the same 8K and longer tests.

## The two profiles I kept

ROCm is the quicker option in the shallow, well-tested lane. Its dynamic-quant prefill was twice as fast as Vulkan, and DFlash lifted the mixed 512-token set from a 12.43 tok/s target-only baseline to 23.46 tok/s. On favourable output it exceeded 40 tok/s.

I kept Vulkan as the default because it returned the exact 8K passkey where the current ROCm path did not. It is slower at prompt processing and only slightly faster at target-only decode. DFlash adds too little on Vulkan—and can make generation substantially slower when acceptance is poor—so the correctness-first route uses the dynamic target model by itself.

That leaves two profiles with deliberately different limits:

- **Vulkan / dynamic / no DFlash** for multimodal and tool-capable service up to the currently qualified 8K context.
- **ROCm / 17GB / DFlash 15** for deliberately short workloads where throughput matters more than the extra quantisation quality.

The complete retained measurements are available as [CSV](/assets/data/muse-glimmer-strix-halo-2026-08-11.csv). The production DeepSeek service was unloaded for the isolated tests and restored afterwards; the benchmark server was not left competing for unified memory.

*Benchmark date: 11 August 2026. All figures were measured locally on the same EVO-X3. No backend failure is represented as zero throughput, speculative results are labelled separately from target-only generation, and the 8K Vulkan pass is not presented as a 131K qualification.*
