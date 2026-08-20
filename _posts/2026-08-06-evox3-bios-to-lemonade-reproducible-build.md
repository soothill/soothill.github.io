---
layout: post
title: "EVO-X3 from BIOS to Lemonade: the reproducible build"
seo_title: "EVO-X3 Ubuntu, GTT and Lemonade installation guide"
date: 2026-08-06
last_modified_at: 2026-08-06 09:50:00 +0100
permalink: /blog/2026/08/06/evox3-bios-to-lemonade-reproducible-build/
categories: [local-ai, linux, automation]
tags: [gmktec, evo-x3, strix-halo, ubuntu, rocm, gtt, lemonade, autoinstall]
author: Darren Soothill
series: "Local LLMs on Strix Halo"
series_order: 8
description: "A tested route from EVO-X3 firmware settings to a signed Ubuntu USB image, 120GiB dynamic GTT, SSH-key-only access, Lemonade and verified updates."
image: /assets/images/evox3-bios-to-llm-server.png
image_alt: "EVO X3 from BIOS to LLM server, showing 1GiB fixed UMA and a 120GiB dynamic GTT limit"
image_type: image/png
---

> **Release record:** this guide describes `evox3-llm-provisioner` 2026.08.06.2. The repository keeps tested versions separate from the moving stable channel, and it does not claim that every Lemonade backend is a ROCm 7.14 userspace runtime.

The first seven parts of this series answer a sequence of engineering questions: what the EVO-X3 hardware actually exposes, how ROCm and Vulkan behave, which quantizations are useful, what survives long context, and which DeepSeek profile can be defended with evidence. This part turns those findings into a product someone else can install.

The complete automation and runbook are now in the separate [EVO X3 LLM provisioner repository](https://github.com/soothill/evox3-llm-provisioner). It covers the path from firmware to a bootable Ubuntu image, then keeps the machine patched and its configuration on a tested update channel.

## Start with the memory model, not a 96GB label

The most important firmware decision is counter-intuitive: select the smallest UMA frame-buffer or dedicated-graphics reservation the BIOS offers—typically Auto, 512MiB or 1GiB. Do not make a permanent 96GiB GPU / 32GiB CPU split.

Strix Halo's CPU and Radeon 8060S physically share the same LPDDR5X memory. AMD's current [Strix Halo optimization guide](https://rocm.docs.amd.com/en/docs-7.2.0/how-to/system-optimization/strixhalo.html) explains that GTT controls how much system RAM a user process may map into a GPU virtual address space. It is a dynamic mapping limit, not a second physical pool. A large firmware carve-out removes memory from Linux whether a model uses it or not.

The qualified outcome on my 128GiB EVO-X3 is:

| Memory view | Qualified value |
| --- | ---: |
| Fixed VRAM / UMA | Approximately 1GiB |
| Host-visible memory | Approximately 124–125GiB |
| TTM page limit | `31457280` 4KiB pages |
| Dynamic GTT | 120GiB |

The installer writes `options ttm pages_limit=31457280` to its own managed modprobe file and regenerates initramfs. It refuses a conflicting `pages_limit` definition and never adds the deprecated `amdgpu.gttsize` option.

That layout was not chosen from theory alone. The DeepSeek V4 Flash target needs one 97,161MiB managed allocation, and the target plus its optional draft model occupy more than 105GiB before context and runtime allocations. The fixed 96/32 layout cannot run that monolithic profile and leaves the OS dangerously constrained.

## The USB image remains safe enough to share

The image builder follows Ubuntu's Noble channel instead of baking one point-release filename into the project. It downloads Ubuntu's `SHA256SUMS` and detached signature, verifies them with the Ubuntu archive keyring, selects the newest listed 24.04 live-server image, and verifies the ISO before modifying it.

The resulting USB contains the complete versioned provisioner and a NoCloud autoinstall seed. It automates the repeatable parts but leaves two decisions interactive:

1. network configuration, when DHCP is not enough;
2. the target NVMe device that will be erased.

A reusable image must not guess the second one.

The builder also asks where SSH public keys should come from. It can read a GitHub username, an HTTPS key URL, or a local file. If no key is embedded, the installed machine opens a first-boot console wizard with the same choices plus pasted keys. The operator password is locked and password SSH remains disabled.

The build and write path is deliberately short:

```bash
sudo apt install curl gpgv python3 ubuntu-keyring xorriso
./scripts/build-autoinstall-iso.sh --github YOUR_GITHUB_USER
sudo ./scripts/write-usb.sh \
  dist/evox3-ubuntu-autoinstall.iso /dev/sdX
```

The USB writer displays device size, model, serial and transport, refuses the current system disk, and requires the exact whole-device path to be typed before it writes anything.

## Ubuntu needs a property check, not merely a kernel number

After installation, the machine performs a full Ubuntu 24.04 upgrade and installs `linux-oem-24.04`. The kernel choice matters because ROCm backends on `gfx1151` need KFD to export Context Wave Save/Restore sizes. Lemonade's current [gfx1151 kernel guidance](https://lemonade-server.ai/gfx1151_linux.html) names the two properties: `cwsr_size` and `ctl_stack_size`.

The provisioner tests those sysfs properties after reboot. A version string alone is weaker evidence because Ubuntu can backport the fix. It also rejects an installed `amdgpu-dkms` package: the separate DKMS module can shadow the corrected inbox `amdgpu` driver and break GPU discovery.

Only after the kernel and GTT checks pass does the second boot install Lemonade and its ROCm backend.

## Lemonade supports gfx1151; that is not the same as “all ROCm 7.14”

This deserves a precise answer because my latest custom work has used a host ROCm 7.14 stack.

Lemonade does now support Strix Halo natively. Its `llamacpp:rocm` backend recognises `gfx1151`, and its experimental `vllm:rocm` path has a per-architecture `gfx1151` bundle. Those managed assets nevertheless carry their own ROCm versions.

At this release boundary:

| Path | Runtime line | Position in the build |
| --- | --- | --- |
| Lemonade stable llama.cpp | b10236 with TheRock ROCm 7.13 | Default |
| Lemonade vLLM | vLLM 0.20.1 with ROCm 7.12 | Optional and experimental |
| My custom llama.cpp path | b10083 and selected patched builds on host ROCm 7.14 | Advanced retained profile |
| My qualified upstream vLLM path | vLLM 0.26 wheel carrying ROCm 7.2.3 compute libraries on the 7.14 host driver | Standalone advanced profile |

Lemonade deliberately reuses a system ROCm tree only when its expected major and minor runtime match. A host `/opt/rocm` 7.14 installation therefore does not magically turn a managed 7.13 or 7.12 asset into a 7.14 build.

The public installer uses Lemonade's managed stable runtime by default. The repository separately records the exact custom 7.14 pins, checksums and promotion boundaries so the updater can advance them honestly when Lemonade publishes and validates an equivalent native bundle.

## Failed upgrades become controls

The build carries more than successful numbers. Two recent llama.cpp canaries revealed why update qualification needs a realistic request sequence.

Unmodified b10216 and b10290 could answer a short Qwen3-Coder request correctly, process a new uncached 8,191-token prompt, and then return the *previous* short answer. A fresh-process smoke had missed it. The root cause was a write-after-read race around device-owned pinned host input buffers on the integrated HIP path.

The general custom backend therefore remains b10083. Qwen3-Coder alone may use b10290 only with the narrow upstream PR 25863 host-buffer fix, which passed the sequential short-to-8K test, long decode, 4,775 focused ROCm backend operations and the throughput gate. “Newest” is not a release criterion when stateful correctness fails.

Other evidence became operating policy:

- Lemonade is bound to localhost, LAN broadcast and telemetry are disabled, and remote access uses an SSH tunnel.
- `max_loaded_models=1` is a safety control. A real DeepSeek/Phi overlap exhausted 128GiB and the kernel killed both runtimes.
- Qwen-specific KV cache, CPU masks, sparse routing and speculation settings are not applied globally.
- 32K and 64K context are comfortable; 128K is an exclusive, swap-active workload; 192K crossed the available-memory safety floor.
- DeepSeek's accuracy profile keeps exact prefill, all six routed experts and target-only decode. Sparse/four-expert/DSpark configurations remain explicit speed-versus-quality experiments.

## The update channel is small enough to audit

Every installed machine checks one `stable.env` manifest in the GitHub repository. The updater parses it as restricted data rather than sourcing it as shell code. It verifies schema, channel, upgrade direction, minimum updater version, payload path, SHA-256 and the exact version inside the tagged release archive.

Releases live under `/opt/evox3/releases/VERSION`; the `current` symlink changes only after a complete copy. A successful refresh updates Ubuntu, reapplies the GTT/initramfs contract, upgrades Lemonade and its selected managed backends, and reapplies the performance service. Host-local choices remain in `/etc/evox3/config.env`.

The weekly timer runs in a maintenance window because a runtime update can restart Lemonade and unload a model. It can be disabled where another maintenance process owns that decision.

## The useful deliverable is the contract

The USB image is convenient, but the real deliverable is the boundary it enforces:

- firmware leaves physical memory available to Linux;
- GTT makes that memory dynamically addressable by the GPU;
- the kernel proves the required KFD properties;
- Lemonade owns normal model and backend lifecycle;
- custom ROCm 7.14 work remains versioned rather than masquerading as a managed default;
- failed canaries remain visible and block unsafe promotion;
- updates are repeatable, checked and reversible at the release-directory level.

That is the difference between documenting one workstation and producing a system another person can install, understand and keep current. The [repository README](https://github.com/soothill/evox3-llm-provisioner#readme) starts at the BIOS checklist and follows the same path all the way through `sudo evox3-verify`.
