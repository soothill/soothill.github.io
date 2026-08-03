---
layout: post
title: "ROCm on Strix Halo, without the folklore"
seo_title: "ROCm on Strix Halo: setup and recovery"
date: 2026-08-03 09:00:00 +0100
last_modified_at: 2026-08-03 18:00:00 +0100
permalink: /blog/2026/08/03/rocm-on-strix-halo-without-folklore/
categories: [local-ai, linux, software]
tags: [rocm, strix-halo, gfx1151, llama-cpp, lemonade, linux]
author: Darren Soothill
series: "Local LLMs on Strix Halo"
series_order: 2
description: "A measured Linux setup for ROCm on the Ryzen AI Max+ 395: memory, build provenance, model lifecycle, failure modes and a recovery runbook."
---

> **Test record:** this article describes the software state running on my EVO-X3 on 3 August 2026. ROCm `7.14.60850`, the Lemonade lifecycle service and its `llama.cpp` child were inspected on the machine itself. The installed build is a development snapshot, not a promise that every ROCm release supports every Strix Halo configuration.

The first article in this series established the [EVO-X3 hardware, firmware and NVMe baseline](/blog/2026/08/03/gmktec-evo-x3-hardware-bios-nvme-baseline/). The next product question is software support.

“ROCm works” is not a useful answer on its own. It could mean the installer completed, `rocminfo` printed a device, one prompt returned a token or a service survived a week of actual use. Those are different acceptance criteria.

As a Director of Product, this is where I become wary of capability theatre. A technically impressive path is not yet a product path. It needs an install boundary, observable provenance, a repeatable load contract and a route back when an experiment wedges the GPU. This note records that complete path for Strix Halo on Linux, including the places where it is still less tidy than I want it to be.

## The working baseline

The configuration below is the one used for the later benchmark articles. It is a tested configuration, not a universal recommendation assembled from forum posts.

| Layer | State on this EVO-X3 |
| --- | --- |
| Operating system | Ubuntu 24.04.4 LTS |
| Kernel | `6.17.0-40-generic` |
| Firmware | AMI `EVO-X3_V1.01`, 17 June 2026 |
| GPU target | `gfx1151`, Radeon 8060S |
| ROCm root | `/opt/rocm-7.14.0` |
| HIP compiler | `7.14.60850-0000000`, AMD clang 23 development build |
| Host memory | 128GB LPDDR5X; 124GiB visible to Linux |
| AMDGPU memory view | 1GiB visible VRAM; 120GiB GTT aperture |
| Lifecycle layer | Patched Lemonade `11.5.1`, bound to `127.0.0.1:19071` |
| Inference child | `llama-server`, bound to `127.0.0.1:8001` |
| Current model | Qwen3-Coder 30B-A3B Instruct, `Q4_K_S`, 32,768-token runtime context |

AMD's current [Strix Halo system-optimisation guide](https://rocm.docs.amd.com/en/docs-7.2.0/how-to/system-optimization/strixhalo.html) explains the Linux memory model: GPUVM allows the GPU to address system memory through GTT. Its practical recommendation is a small fixed BIOS VRAM allocation and a large TTM/GTT limit, rather than treating the machine like a Windows system with a permanently assigned 64GB or 96GB graphics partition.

That distinction matters. Linux reporting only 1GiB of visible VRAM does **not** mean this machine can load only a 1GiB model. The active backend is using the much larger shared-memory path. On this machine, `/sys` exposes a 120GiB GTT aperture and a 122B model can run fully resident. The runtime and kernel still have to support that path correctly; a large number in a BIOS menu cannot substitute for that support.

There is also a release boundary. AMD publishes a `gfx1151` payload in its [ROCm installer documentation](https://rocm.docs.amd.com/en/develop/install/rocm.html), but the support table and required kernel fixes are version-specific. This system's ROCm build and kernel combination has passed my workloads. I would not turn that observation into a claim that an arbitrary distribution kernel, packaged runtime or older stable release will behave identically.

## Qualification starts with provenance

The fastest way to lose a benchmark is to forget which backend supplied it. I capture the software identity before any performance run:

```bash
uname -r
lsb_release -ds

/opt/rocm-7.14.0/bin/rocminfo | sed -n '/Name:.*gfx1151/,+8p'
/opt/rocm-7.14.0/bin/hipcc --version

stat -c '%n %s bytes' /path/to/model.gguf
sha256sum /path/to/model.gguf

pgrep -af 'lemond|llama-server'
ldd /proc/$(pgrep -n llama-server)/exe | grep -E 'hip|hsa|amdhip'
```

The model hash is part of the test record, not decoration. Two files with similar display names can use different quantisation layouts or metadata. Likewise, a binary called `llama-server` may be a Vulkan build, a ROCm build or a CPU-only build. The process tree and linked libraries settle the question.

Device access is a separate gate:

```bash
id
ls -l /dev/kfd /dev/dri/renderD*
```

The service account needs the relevant render/video permissions. Passing `rocminfo` as an interactive user does not prove that the system service can open the same devices.

For a direct build, the official [`llama.cpp` build guide](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md) is the source of truth. The useful principle is to declare the backend and target explicitly, then keep the resulting binary separate from the Vulkan build:

```bash
cmake -S . -B build-rocm \
  -DGGML_HIP=ON \
  -DGPU_TARGETS=gfx1151 \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build-rocm --config Release -j 16

cmake -S . -B build-vulkan \
  -DGGML_VULKAN=ON \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build-vulkan --config Release -j 16
```

Pin the `llama.cpp` commit with the result. A backend name without a source revision is not enough to reproduce a changing kernel implementation.

## The serving boundary

I use [Lemonade](https://lemonade-server.ai/docs/guide/configuration/) as the lifecycle and API layer, with `llama.cpp` doing the inference work. That division is important:

```text
client -> Lemonade API -> managed llama-server -> ROCm/HIP -> gfx1151
```

Lemonade owns model selection, loading, readiness and the OpenAI-compatible surface. `llama-server` owns the compute graph and GPU kernels. The parent-child relationship gives the service one source of truth. Launching another backend in a detached shell may work for a benchmark, but it creates a second owner for ports, memory and model state.

The current Qwen3-Coder service uses one slot and the following material settings:

```text
context          32,768
GPU layers       all available
flash attention  on
batch / ubatch   2,048 / 512
K/V cache        f16 / f16
memory mapping   off
parallel slots   1
CPU threads      6, pinned to mask 0x3f
```

The six CPU threads are not an attempt to make inference CPU-heavy. They keep prompt preparation and orchestration on a compact group of cores while the GPU handles the model. `--no-mmap` makes allocation behaviour more explicit for this shared-memory platform. Those choices are tested settings for this model; they should not be copied blindly to a small dense model or a multi-user server.

The health checks are deliberately boring:

```bash
curl --fail --silent http://127.0.0.1:19071/api/v1/health
curl --fail --silent http://127.0.0.1:19071/api/v1/models
ss -ltnp | grep -E ':19071|:8001'
```

Then I send one deterministic prompt through the same API that a client will use. A backend can be listening while its model is still loading, and a model can be loaded while the public API is pointing at the wrong process. Each layer needs its own signal.

## What failed, and why that is part of the result

Most setup accounts edit out the recovery work. That removes the part another operator most needs.

During the wider programme I tested an experimental fused-MoE path in vLLM. Its numerical checks passed, but sustained requests could reset the GPU. A fully serialised version was stable and slow. That is a valuable engineering result, but it is not a production backend.

The reset also exposed an operations problem. A standalone `llama-server` left in a detached `tmux` session can survive after the experiment that created it has ended. It may continue holding shared memory or a port while Lemonade reports a different lifecycle state. The fix is not “kill every process with llama in its name”. The fix is to identify ownership first.

My recovery sequence is:

1. Stop the experimental client and collect its final log; do not immediately destroy the evidence.
2. Inspect GPU state, listening ports and the complete process tree.
3. Identify whether each inference process belongs to Lemonade, systemd or an interactive shell.
4. Stop only the orphaned or failed owner, then confirm that its child exits.
5. Check that the required ports are free and GPU memory has returned.
6. Start one lifecycle owner, load one known model and wait for ready state.
7. Verify the child's executable and linked backend libraries.
8. Run a deterministic API request, followed by a short repeated-request gate.

In compact form:

```bash
ps -eo pid,ppid,lstart,cmd --forest | grep -E 'lemond|llama-server|vllm'
ss -ltnp | grep -E ':19071|:8001'
cat /sys/class/drm/card1/device/mem_info_gtt_used 2>/dev/null
journalctl -k --since '-15 minutes' | grep -iE 'amdgpu|xgmi|reset|fault'
```

The exact DRM card number is machine-specific, so it must be discovered rather than assumed. After a reset, I also check that the GPU is back in its normal automatic performance state; benchmark-only clock or power settings should never leak into the everyday service.

## What I would change before calling it operational

The measured stack is healthy and currently serving Qwen3-Coder locally, but its service ownership is not yet the final shape I want. The packaged `lemond.service` is inactive; the working patched daemon is an isolated user process. It is bound to localhost, which is the right exposure by default, but it will not automatically reappear after a reboot.

That leaves a clear, bounded operations task:

- install the patched lifecycle service under one supervised unit;
- make model and backend configuration declarative;
- start only after the GPU device and model filesystem are available;
- set conservative restart limits so a GPU-reset loop cannot thrash the host;
- preserve logs and expose a readiness check;
- restore the selected model intentionally, rather than relying on a stale child process.

I would also keep ROCm and Vulkan builds side by side. ROCm is not automatically faster at every phase of every model, as the [next benchmark](/blog/2026/08/03/llamacpp-vulkan-vs-rocm-strix-halo/) shows. A recoverable product can select between known backends without rebuilding the machine around each result.

## The useful definition of “working”

ROCm is working on this Strix Halo system in the sense that matters: a known build can load models far larger than the nominal VRAM figure, sustain repeatable inference, expose a local API and recover to a known state after an experimental failure.

The caveats are equally real. This is a development stack, the kernel and ROCm combination is part of the qualification, and the current daemon still needs durable service ownership. The right conclusion is neither “unsupported, therefore impossible” nor “one prompt worked, therefore solved”.

The product conclusion is more useful: **ROCm on Strix Halo is a viable local-inference path when the build provenance, shared-memory model and lifecycle contract are treated as part of the product.**

*Sources checked 3 August 2026: [AMD Strix Halo system optimisation](https://rocm.docs.amd.com/en/docs-7.2.0/how-to/system-optimization/strixhalo.html), [AMD ROCm installer documentation](https://rocm.docs.amd.com/en/develop/install/rocm.html), the official [`llama.cpp` build guide](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md), [Lemonade configuration](https://lemonade-server.ai/docs/guide/configuration/) and [Lemonade's `llama.cpp` backend guide](https://lemonade-server.ai/docs/guide/configuration/llamacpp/). Observed versions and service state come from the EVO-X3 itself.*
