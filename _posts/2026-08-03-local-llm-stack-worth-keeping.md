---
layout: post
title: "A local LLM stack worth keeping"
date: 2026-08-03 13:00:00 +0100
permalink: /blog/2026/08/03/local-llm-stack-worth-keeping/
categories: [local-ai, product, operations]
tags: [strix-halo, lemonade, llama-cpp, rocm, vulkan, local-llm]
author: Darren Soothill
series: "Local LLMs on Strix Halo"
series_order: 6
description: "The final Strix Halo stack: which hardware, Linux memory model, runtimes, models and operating controls I would keep after the benchmarks."
---

> **Decision record:** this recommendation is based on the EVO-X3 hardware audit, matched backend tests, eight-model size sweep and 101-minute 122B soak completed by 3 August 2026. The current stack is fast and stable in-session; one remaining operations gap — supervised boot persistence — is called out rather than silently declared finished.

A field note series should end with a decision.

The GMKtec EVO-X3 can load a 397B-class quant, run a 122B model across a nearly full 256K context and generate from a 30B coding model at up to 98 tokens per second. Those are satisfying demonstrations. They are not, on their own, a product.

As a Director of Product, the stack I want to keep is the one that makes the common path quick, the difficult path possible and the failure path understandable. It needs fewer clever components, not more. It needs a lifecycle owner, explicit backend choices, model roles, safe storage and enough instrumentation that I can explain a slow request without rebooting the box and hoping.

This is that stack — and the work still needed to make it operationally complete.

## The platform I would keep

The [hardware baseline](/blog/2026/08/03/gmktec-evo-x3-hardware-bios-nvme-baseline/) proved that the EVO-X3 is not only a capacity story.

| Layer | Keep | Why |
| --- | --- | --- |
| Compute | Ryzen AI Max+ 395: 16 Zen 5 cores, 40-CU Radeon 8060S | Enough CPU orchestration and integrated GPU compute in one 128GB memory domain |
| Memory | 128GB LPDDR5X-8000 | Makes 77GB four-bit models and large K/V caches practical |
| Linux GPU memory | Small fixed VRAM plus large GTT/GPUVM aperture | Avoids needlessly removing a huge fixed partition from general system memory |
| Storage | Gen4 ×4 NVMe; measured 7.00–7.05GB/s reads | Keeps model placement and switching from becoming the platform bottleneck |
| Operating system | Ubuntu 24.04.4 LTS | Known working userspace for this programme |
| Kernel | `6.17.0-40-generic`, as tested | A reproducible baseline, not a claim that it is the final supported kernel |
| Network exposure | Localhost by default | Prevents an unauthenticated model API from becoming a LAN service by accident |

The memory policy is worth repeating. The current machine reports 1GiB visible VRAM and a 120GiB GTT aperture. That is intentional and consistent with AMD's [Strix Halo Linux guidance](https://rocm.docs.amd.com/en/docs-7.2.0/how-to/system-optimization/strixhalo.html): keep the fixed BIOS allocation small and let GPUVM address shared system memory dynamically.

I would not set a fixed 64GB or 96GB graphics partition simply because a Windows setup guide recommends it. The Linux runtime has already demonstrated 122B inference and 256K context through GTT. A large fixed reservation reduces flexibility without repairing an unsupported kernel or backend.

The Lexar NQ790 is also good enough to keep. Its 7GB/s sustained read and 14.72-second direct read of a 102.32GB GGUF make storage a short part of model start-up, not a reason to replace the drive. A second NVMe would be for capacity, separation or resilience; the empty socket does not need filling for benchmark theatre.

## The software shape

The serving system should have one control plane and a small number of replaceable inference engines:

```text
local clients
     |
OpenAI-compatible API on 127.0.0.1
     |
Lemonade: model registry, load state, readiness and lifecycle
     |
     +-- llama.cpp ROCm   long prompts / one-user 122B
     +-- llama.cpp Vulkan decode-heavy or two-client work
     +-- vLLM GPTQ        qualified concurrent workloads
```

[Lemonade](https://lemonade-server.ai/docs/guide/configuration/) earns its place by owning model lifecycle rather than by sitting invisibly in front of another server. It gives clients one surface while allowing the backend to change with the workload. The parent process must own the inference child. A detached benchmark server should never become the accidental production service.

`llama.cpp` remains the default engine. It is the most versatile fit for GGUF, produced the best single-client 122B result and supports both backend paths I have measured. ROCm and Vulkan builds should be versioned side by side rather than rebuilt over one another.

vLLM is a specialist path, not the default. The GPTQ configuration produced a 1.773-second two-client time to first token and essentially tied `llama.cpp` ROCm's two-client aggregate throughput. That makes it useful for concurrency and scheduling experiments. Its Strix Halo path is still experimental, and my fused-MoE optimisation could reset the GPU. Only the stable stock kernel belongs in a qualified service.

## The default model should be smaller than the machine

The everyday model on this box is Qwen3-Coder 30B-A3B Instruct `Q4_K_S`, served with a 32,768-token context. Its file is 17.46GB. The model leaves roughly 100GiB of system memory available in the observed steady state, so the machine remains a computer rather than turning into a single fragile allocation.

That is a feature. It provides:

- 73.65 tok/s measured ROCm generation with stronger prompt processing;
- 97.73 tok/s measured Vulkan generation for decode-heavy coding work;
- enough context for normal repository tasks;
- fast recovery and model switching;
- headroom for indexing, test runs, browsers and another local service.

The [size sweep](/blog/2026/08/03/finding-the-useful-quant-strix-halo/) suggests a compact model portfolio:

| Role | Model tier | Product intent |
| --- | --- | --- |
| Instant helper | 0.8B–4B | Extraction, classification and tightly bounded transformations |
| Everyday general model | 35B-A3B class | High interaction rate with a larger expert pool |
| Everyday coding model | Qwen3-Coder 30B-A3B | Fast local code discussion and edits |
| Deliberate expert | 122B-A10B four-bit | Hard analysis, review and very long documents |
| Research boundary | 397B-A17B `IQ1_M` | Fit and systems research until task quality is proven |

I would not automatically route every prompt to 122B. The 122B service generated at 13.3–13.8 tok/s in the demanding served tests. That is entirely usable when the task merits it and needlessly slow when a focused small model can return a correct schema in a fraction of the time.

The router can start as a user choice. Automatic routing should only follow once task-level quality evidence exists; a speculative classifier can add latency and make failures harder to explain.

## Backend selection should be a policy

The [ROCm-versus-Vulkan result](/blog/2026/08/03/llamacpp-vulkan-vs-rocm-strix-halo/) did not produce one permanent winner. I would encode the measured behaviour into a small policy:

| Request shape | Default path |
| --- | --- |
| Large prompt, short response | `llama.cpp` ROCm |
| Qwen3-Coder with a long completion | `llama.cpp` Vulkan |
| 122B, one local interactive client | `llama.cpp` ROCm |
| 122B, two clients prioritising aggregate decode | `llama.cpp` Vulkan |
| Qualified multi-client path prioritising first token | vLLM GPTQ |

The policy is a starting point, not a hard-coded truth. Each new model architecture gets the same matched prompt and generation test before it inherits a backend. The revisions, model hash, context, cache precision, batch settings and power state travel with the result.

That metadata is part of the product. Without it, a future update can improve prompt processing, regress generation and still appear to be “about the same” in casual use.

## The operating contract

The current service is bound to localhost, has telemetry disabled and correctly manages one `llama-server` child under the Lemonade process. The model is loaded, pinned and responding. The software stack itself is described in [ROCm on Strix Halo, without the folklore](/blog/2026/08/03/rocm-on-strix-halo-without-folklore/).

It is not yet reboot-safe. The packaged `lemond.service` is inactive and the working patched daemon is an isolated user process. I would not hide that gap behind the word “deployed”. The configuration is the stack worth keeping; supervised service ownership is the final piece required before I call the installation operational.

The service definition needs to guarantee:

1. one lifecycle owner and no detached `tmux` backend;
2. start-up after `/dev/kfd`, the render device and model filesystem are ready;
3. localhost binding unless an authenticated, TLS-terminating gateway is intentionally added;
4. bounded restart behaviour after a GPU failure;
5. separate liveness and model-readiness checks;
6. persistent logs for the lifecycle process, backend and kernel;
7. a declarative default model with a hash, not merely the most recent path;
8. graceful unload before an experimental runtime takes ownership of the GPU.

The minimum useful health record is:

```text
service version and source revision
backend binary and linked ROCm/Vulkan libraries
model identity, size and checksum
loaded context and cache precision
process ownership and listening addresses
available memory, GTT use, swap and temperature
last deterministic request result
kernel GPU warnings and reset count
```

For upgrades, I would use a small release gate: one deterministic answer, a 20-request stability run, the matched kernel benchmark and a shorter memory slope test. The [101-minute soak](/blog/2026/08/03/qwen35-122b-256k-long-session-test/) belongs before a new 122B or long-context configuration becomes the default, not before every patch release.

## What I would leave out

The ability to add another engine is not a reason to do it.

I would leave the NPU out of the default LLM path for now. It is interesting hardware, but the measured production stack is GPU-based and the NPU software path has not cleared the same model, quality, context and reliability gates.

A hybrid NPU/GPU prototype has measured **7.39% faster** than its GPU-only control. That is promising and still provisional: final qualification on the current 128GB UMA configuration remains outstanding. It belongs in a development branch, not in a diagram presented as the recommended stack.

I would also leave the native fused-MoE vLLM experiment disabled. Passing a numerical unit test is not enough when repeated requests can reset the GPU. The serialised safe variant ran at only 7.05 tok/s, below the stable paths already available.

Finally, I would not expose the OpenAI-compatible port directly to the local network. “Local model” does not make prompt history, source code or tool credentials non-sensitive. If remote access becomes a requirement, authentication, TLS, rate limits and explicit network policy become part of the feature.

## The product verdict

The EVO-X3 is a credible local-AI workstation because its unusual memory capacity is matched by a fast NVMe path and two usable GPU backends. ROCm is the better prompt processor in the measured models. Vulkan can be the better decoder. A 35B mixture-of-experts model is a more compelling everyday proposition than a smaller dense 27B. A 122B four-bit model remains stable at nearly 256K context for more than 100 minutes. None of those findings requires the 397B model to become the default.

The stack I would keep is therefore intentionally plain:

- Ubuntu and the qualified AMDGPU/ROCm combination;
- a small fixed VRAM allocation with the large Linux GTT path;
- Lemonade as the single lifecycle and API owner;
- versioned `llama.cpp` ROCm and Vulkan backends;
- Qwen3-Coder 30B as the responsive daily service;
- Qwen3.5 122B as an explicit expert and long-context service;
- vLLM only where its concurrency and TTFT advantage has been qualified;
- models and benchmark evidence on the measured Gen4 NVMe filesystem;
- supervised boot persistence, health checks and recovery as release requirements.

That final bullet is not infrastructure housekeeping after the product work. It is the product work. Local inference becomes genuinely useful when the hardware, model and runtime stop being a demonstration and start behaving like a dependable appliance.

*Sources checked 3 August 2026: [AMD Strix Halo system optimisation](https://rocm.docs.amd.com/en/docs-7.2.0/how-to/system-optimization/strixhalo.html), [`llama.cpp`](https://github.com/ggml-org/llama.cpp), [Lemonade configuration](https://lemonade-server.ai/docs/guide/configuration/), [Lemonade `llama.cpp` backends](https://lemonade-server.ai/docs/guide/configuration/llamacpp/) and [Lemonade's experimental vLLM backend](https://lemonade-server.ai/docs/guide/configuration/vllm/). Recommendations are derived from the measured EVO-X3 results documented throughout this series.*
