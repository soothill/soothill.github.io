---
layout: post
title: "GMKtec EVO-X3: the hardware, BIOS and NVMe baseline"
seo_title: "GMKtec EVO-X3: BIOS and NVMe performance"
date: 2026-08-03
last_modified_at: 2026-08-03 18:00:00 +0100
permalink: /blog/2026/08/03/gmktec-evo-x3-hardware-bios-nvme-baseline/
categories: [hardware, local-ai, storage]
tags: [gmktec, evo-x3, strix-halo, ryzen-ai-max, bios, nvme, pcie-4]
author: Darren Soothill
series: "Local LLMs on Strix Halo"
series_order: 1
description: "A product-led examination of my Linux-based GMKtec EVO-X3: Strix Halo hardware, its provable firmware state and measured NVMe performance."
---

> **Test record:** measurements were taken on my EVO-X3 on 3 August 2026. The benchmark used a filesystem-backed test file, never a raw NVMe namespace, and the 64GiB file was removed when testing finished.

As a Director of Product, I spend a great deal of time turning technical capability into a decision someone can act on. That work starts with an awkward distinction: what a product *could* do, what a specification sheet says it can do and what it repeatedly delivers are three different things.

The GMKtec EVO-X3 is my starting point for exploring local large language models on AMD Strix Halo. It is an unusually dense desktop: 16 Zen 5 CPU cores, a 40-compute-unit integrated GPU and 128GB of fast, unified memory in a slim metal chassis. That combination is the headline. The product experience, however, will be decided by less glamorous details — firmware, power profiles, thermal behaviour, storage topology and the time it takes to move a model from NVMe into memory.

This first note establishes the machine and the measurement contract for everything that follows. It is deliberately hardware-first. Before comparing runtimes or quoting tokens per second, I want to know exactly what the platform is, which firmware state it is running and whether its NVMe path delivers what the PCIe 4.0 ×4 label implies.

## The test machine, recorded rather than assumed

GMKtec sells the EVO-X3 with 128GB of soldered LPDDR5X memory and either 2TB or 4TB of factory storage. The SSD manufacturer, controller and NAND matter more than the capacity printed on the order page, so the shipped drive should not be described until the controller identifies it.

| Component | This unit | Evidence |
| --- | --- | --- |
| System | GMKtec EVO-X3 | Chassis and firmware identity |
| Processor | AMD Ryzen AI Max+ 395 | Fixed platform specification |
| Memory | 128GB LPDDR5X-8000, non-upgradeable | Fixed EVO-X3 configuration |
| Factory SSD | Lexar SSD NQ790 4TB, firmware `22788` | NVMe identify data; serial omitted |
| Second M.2 slot | Unpopulated | Linux PCIe and block-device inventory |
| BIOS | `EVO-X3_V1.01`, dated 17 June 2026 | Linux DMI data |
| Operating system | Ubuntu 24.04.4 LTS, kernel `6.17.0-40-generic` | OS and kernel inventory |
| CPU policy | `amd-pstate-epp`, performance governor | Linux CPU frequency policy |
| GPU memory view | 1GiB visible VRAM; 120GiB GTT aperture | AMDGPU sysfs counters |

That table is not administrative overhead. Without it, a storage result cannot be reproduced and a later software update cannot be separated from a firmware or SSD change.

## What the EVO-X3 hardware actually is

At its centre is AMD's [Ryzen AI Max+ 395](https://www.amd.com/en/products/processors/laptop/ryzen/ai-300-series/amd-ryzen-ai-max-plus-395.html), formerly codenamed Strix Halo. It is a three-die FP11 package built on TSMC's 4nm process. The CPU side provides 16 Zen 5 cores and 32 threads, a 3.0GHz base clock, boost frequency up to 5.1GHz, 16MB of L2 cache and 64MB of L3. AMD specifies a 55W default TDP and a configurable range of 45–120W; the system maker still decides how that capability is exposed and cooled.

The graphics side is the Radeon 8060S: 40 RDNA 3.5 compute units running at up to 2.9GHz. It is integrated, but it is not a small laptop iGPU in the conventional sense. It sits beside a 256-bit LPDDR5X-8000 memory interface with a published bandwidth of [256GB/s](https://www.amd.com/en/products/processors/desktops/ryzen/ryzen-ai-halo/ryzen-ai-max-plus-395.html). The 128GB pool is shared by CPU and GPU, and AMD says as much as 96GB can be assigned as graphics memory through [Variable Graphics Memory](https://www.amd.com/en/blogs/2025/amd-ryzen-ai-max-395-processor-breakthrough-ai-.html).

That memory arrangement is why this platform is interesting for local models. A discrete GPU generally has a faster but fixed pool of VRAM. Strix Halo trades some bandwidth for a much larger shared addressable pool. It can keep models resident that would otherwise require a costly accelerator or partial CPU offload. Capacity answers *can it fit?*; bandwidth and software support answer *is it useful?*

There is also an XDNA 2 NPU rated at 50 TOPS. AMD quotes up to 126 aggregate TOPS across the system. That aggregate is a capability label, not an LLM throughput result: different engines, precisions and software paths cannot be collapsed into a useful tokens-per-second prediction. The later runtime tests will identify which part of the silicon is doing the work.

### EVO-X3 platform specification

The current [GMKtec EVO-X3 specification](https://www.gmktec.com/products/gmktec-evo-x3-ai-mini-pc-amd-ryzen-ai-max-395) lists:

| Area | Specification |
| --- | --- |
| Memory | 128GB onboard LPDDR5X-8000; not upgradeable |
| Internal storage | Two M.2 2280 PCIe 4.0 ×4 NVMe slots; 16TB stated maximum across two 8TB drives |
| External PCIe | Rear OCuLink, PCIe 4.0 ×4; not hot-pluggable |
| Displays | HDMI 2.1 and USB4 Type-C; up to two physical display outputs on this chassis |
| Networking | Realtek RTL8125BG 2.5GbE, Wi-Fi 7 via RZ717 / MT7925, Bluetooth 5.4 |
| Front I/O | USB-A 5Gbps, USB-A 480Mbps, 3.5mm combination audio and power button |
| Rear I/O | USB4 40Gbps, USB-A 10Gbps, HDMI 2.1, OCuLink, 2.5GbE and DC input |
| Cooling | Triple heat pipes; GMKtec's specification table lists three cooling fans |
| Power profiles | Silent 54W, Balanced 85W and Performance with a stated 140W peak |
| Power input | 19.5V at 11.8A — approximately 230W at the adapter output |
| Chassis | CNC metal, 353 × 186 × 41mm without the stand; approximately 2.3kg |
| Operating systems | Windows 11 Pro, Ubuntu and Linux listed by GMKtec |

The physical design matters. This is closer to a narrow desktop workstation than a palm-sized mini PC. The additional volume gives GMKtec room for the cooling system and two 2280-length drives, both of which matter under sustained local-AI and storage workloads.

## The storage topology needs proving

The label on each slot is PCIe 4.0 ×4. PCIe 4.0 runs at 16 gigatransfers per second per lane and uses 128b/130b encoding. Four lanes therefore provide a payload rate of approximately **7.88GB/s, or 7.34GiB/s, before PCIe, NVMe, filesystem and application overhead**.

That is a link ceiling, not a promised SSD result. The controller, NAND type, drive capacity, firmware, free space, temperature and write-cache state will decide the actual number. Sequential writes can look excellent while the pseudo-SLC cache is available and then fall sharply during a sustained transfer. Random 4KiB latency at queue depth one may tell us more about everyday responsiveness than an artificially deep queue.

Two slots also do not automatically mean twice the result. AMD lists 16 usable PCIe 4.0 lanes for the processor, while this machine exposes two ×4 M.2 connections and a ×4 OCuLink port. The firmware and board topology decide how those endpoints are rooted and whether anything is shared. Linux proves the populated path; settling the aggregate question will require a second drive in a later test.

For a local LLM, storage has a specific job. It governs installation, model download, model switching, dataset and embedding work, and the time taken to load weights into memory. Once a model is resident, NVMe bandwidth should not be confused with generation speed: inference is then dominated by compute, memory bandwidth and runtime behaviour.

A 70GB model crossing a perfect 7.88GB/s link has a transfer-only lower bound of roughly nine seconds. A real load must be slower because the drive cannot deliver the encoded line rate and the runtime still has to map, allocate and initialise the model. That is the useful question for this platform: not whether a benchmark screenshot reaches a large number, but how quickly the machine becomes ready to work.

## BIOS and Linux baseline: what the machine can prove

The EVO-X3 is new enough that GMKtec's [support centre](https://www.gmktec.com/pages/drivers-and-software) does not yet publish an EVO-X3 BIOS guide. Linux can verify the outcome of several firmware choices, but it cannot reconstruct a missing before-and-after change log. I therefore separate settings the running machine proves from settings that would require photographs of the BIOS menus.

| Firmware area | Observed state | What it means |
| --- | --- | --- |
| BIOS | American Megatrends `EVO-X3_V1.01`, 17 June 2026 | The exact firmware baseline for every result in this article |
| Secure Boot | Disabled | A definite current firmware state; this is not presented as a performance optimisation |
| SVM / IOMMU | AMD-V present; 30 IOMMU groups active | Virtualisation and device isolation are functioning in the running kernel |
| NVMe mode | One independent NVMe namespace; no firmware RAID layer visible | The SSD is measured directly through the Linux NVMe driver |
| CPU power policy | AMD P-state EPP active; Linux governor set to `performance` | An OS-observable policy, not proof of which GMKtec chassis mode is selected |
| UMA / graphics memory | 1GiB visible VRAM and 120GiB GTT | Linux is using a large shared-memory aperture rather than a fixed 96GB Windows VGM allocation |
| Kernel overrides | No AMDGPU memory-size option in the kernel command line | The memory view is not being forced by a boot parameter |
| Above 4G / ReBAR | Not exposed with sufficient evidence to record | No BIOS switch is inferred from a working GPU driver |
| Fan / chassis mode | Not exposed through ACPI `platform_profile` | Silent, Balanced or Performance cannot be identified reliably from Linux alone |

The memory result is the important Linux-specific finding. AMD's 96GB VGM figure describes a fixed graphics-memory option commonly exposed on Windows. This machine reports only 1GiB as visible VRAM, while AMDGPU exposes a 120GiB graphics translation table aperture into shared system memory. A runtime can therefore work with far more than the nominal VRAM figure, but it must support the Linux AMDGPU memory path correctly. That is a software question for the next article, not a reason to label the machine as having only 1GB of useful GPU memory.

There are two product principles behind this record. First, a maximum-performance configuration and the configuration I would live with every day may be different — both deserve a result. Second, a setting should not be claimed because an older machine or forum post uses it. Every change needs an observable purpose and a reproducible state.

## Inventory the NVMe path before benchmarking it

On Linux, the following read-only commands capture the identity, firmware, PCIe negotiation and — where the account has sufficient privileges — health data for each drive. Device names must be checked before substituting them into a command.

```bash
sudo dmidecode --type bios
uname -a
lsblk -o NAME,MODEL,SERIAL,SIZE,FSTYPE,MOUNTPOINTS
sudo nvme list -v
sudo nvme id-ctrl /dev/nvme0
sudo nvme smart-log /dev/nvme0
lspci -tv

for controller in /sys/class/nvme/nvme*; do
  printf '%s: ' "$(basename "$controller")"
  cat "$controller/device/current_link_speed" \
      "$controller/device/current_link_width"
done
```

The populated slot is at PCI address `0000:64:00.0`, downstream of the processor's `00:02.5` root port. It negotiated **16.0GT/s at width ×4**, exactly the Gen4 link the specification promises. The second M.2 slot is empty, so this test proves the populated path but cannot yet compare the two sockets or measure simultaneous two-drive bandwidth.

The NVMe model string is `Lexar SSD NQ790 4TB`; the PCI ID database describes the Shenzhen Longsys controller as an NM790-class, DRAM-less device. Linux sees one 4.00TB namespace formatted with 512-byte logical blocks. The root filesystem is ext4, 39% used at the time of testing, with approximately 2.1TB available. The active block scheduler is `none`, which is normal for a modern NVMe path.

The remote account did not have passwordless `sudo`, so I did not retrieve the privileged NVMe SMART log and make no claim here about percentage used or overall drive-health status. That limitation does not affect the direct-I/O throughput, latency or temperature measurements below.

## A safe, repeatable NVMe test

The benchmark ran from mains power with the Linux CPU governor set to `performance`. System load was below 0.25 before the first full run. I built the official `fio-3.42` release in temporary storage rather than altering the system package set.

The test used **one named file inside my home filesystem**, never a raw block device. Direct I/O bypassed the page cache, while the existing ext4 filesystem kept the test recoverable. The 64GiB file represented less than 2% of free space and was removed immediately after the final run.

```bash
# Confirm the intended filesystem and available capacity.
findmnt "$HOME"
df -h "$HOME"

# One 64GiB sequential write pass creates the test file.
fio --name=seq-write \
  --filename="$HOME/.evox3-nvme-benchmark.bin" \
  --size=64G --rw=write --bs=1M \
  --ioengine=io_uring --iodepth=32 --direct=1 \
  --group_reporting

# A sustained direct sequential read of the same file.
fio --name=seq-read \
  --filename="$HOME/.evox3-nvme-benchmark.bin" \
  --size=64G --rw=read --bs=1M \
  --ioengine=io_uring --iodepth=32 --direct=1 --readonly \
  --time_based=1 --runtime=60 --ramp_time=5 \
  --group_reporting

# Queue-depth-one random reads: closer to interactive storage behaviour.
fio --name=rand-read-qd1 \
  --filename="$HOME/.evox3-nvme-benchmark.bin" \
  --size=64G --rw=randread --bs=4K \
  --ioengine=io_uring --iodepth=1 --direct=1 --readonly \
  --randrepeat=0 --time_based=1 --runtime=60 --ramp_time=5 \
  --group_reporting
```

The [`fio-3.42` documentation](https://github.com/axboe/fio/blob/fio-3.42/HOWTO.rst) defines `direct=1` as non-buffered I/O and `io_uring` as Linux native asynchronous I/O. Each result was saved as JSON alongside the exact job options. That matters because a queue-depth-one latency figure and a deep-queue throughput figure describe different products, even when both are labelled “4K random read”.

The sequential write test writes 64GiB and therefore consumes a small part of the SSD's finite write endurance. The file can be deleted after the test once its exact path has been checked:

```bash
rm -- "$HOME/.evox3-nvme-benchmark.bin"
```

For a future slot comparison, the cleanest test is the same SSD, filesystem and software image in each socket. That isolates the board path from differences between two drive models. Power must be disconnected before moving the drive, and the drive should return to the same starting temperature before each run.

## What the NVMe actually delivered

| Measurement | Result | Test context |
| --- | ---: | --- |
| SSD / firmware | Lexar SSD NQ790 4TB / `22788` | Single populated M.2 socket |
| Negotiated PCIe link | 16.0GT/s ×4 | PCIe 4.0 ×4 confirmed in sysfs |
| Sequential read | 7.00GB/s | 1MiB blocks, QD32, 60 seconds, 420GB read |
| Sequential read, thermal repeat | 7.05GB/s | 1MiB blocks, QD32, 60 seconds, 423GB read |
| Sequential write, first 64GiB | 4.36GB/s | 1MiB blocks, QD32, one pass |
| Random 4KiB read, QD1 | 10.1k IOPS / 41.5MB/s | 97.1µs mean, 288.8µs p99 |
| Random 4KiB read, QD32 | 231k IOPS / 948MB/s | One job; 136.7µs mean, 469.0µs p99 |
| Cooled / peak composite temperature | 44.9°C / 80.9°C | One-second samples over the final 27 seconds of the thermal repeat |
| 102.32GB DeepSeek GGUF direct read | 14.72 seconds / 6.95GB/s | 4MiB blocks, QD8, storage-only model-read lower bound |

The read result is the headline: 7.00–7.05GB/s is roughly 89% of the encoded PCIe payload ceiling calculated earlier. More importantly, the repeat stayed slightly above the first run while the composite sensor reached 80.9°C. The drive reports a 94.9°C critical threshold, and there is no throughput evidence of thermal throttling in this 60-second test.

The write number needs tighter language. **4.36GB/s is the average across the first 64GiB**, not a claim about post-cache steady-state performance. A 4TB DRAM-less drive can use a substantial dynamic SLC cache; exhausting it would require a much larger write and would add little to the local-model question. The result is useful for ordinary large-file placement, but it is not an endurance qualification.

Queue depth changes the story. At QD1 the drive delivered 10.1k IOPS with 97µs mean latency — the better proxy for interactive filesystem work. At QD32 it reached 231k IOPS, but system CPU time rose materially and latency increased because more requests were deliberately kept in flight. Neither synthetic random result predicts token generation.

The model-shaped read is more useful. A real 102.32GB DeepSeek GGUF already on the system crossed the storage path in 14.72 seconds at 6.95GB/s. That is a storage-only lower bound: an inference runtime still has to map the file, allocate shared GPU memory, parse metadata and initialise its compute graph before the first token. The later runtime article will measure that end-to-end interval.

The empty second socket remains the one untested part of GMKtec's storage claim. The current result proves that one EVO-X3 path can sustain a high-end Gen4 read rate; it does not prove simultaneous 14GB/s aggregate bandwidth or that both physical sockets are equivalent.

## What this baseline unlocks

This is the first layer of the Strix Halo series. It turns the EVO-X3 from a list of impressive components into a known test system. Once the BIOS state, power profile and storage path are fixed, later comparisons — ROCm against Vulkan, model size against usable context, peak speed against an hour of sustained work — have something solid underneath them.

That is also the product lesson. Hardware does not become a product because its components are individually fast. It becomes a product when the defaults are explainable, the setup is recoverable and the performance survives the workload people bought it to run.

Continue with [ROCm on Strix Halo, without the folklore](/blog/2026/08/03/rocm-on-strix-halo-without-folklore/), which qualifies the Linux software path and records how the machine recovers when an experimental backend fails.

*Sources checked 3 August 2026: [GMKtec EVO-X3 specification](https://www.gmktec.com/products/gmktec-evo-x3-ai-mini-pc-amd-ryzen-ai-max-395), [AMD Ryzen AI Max+ 395 specification](https://www.amd.com/en/products/processors/laptop/ryzen/ai-300-series/amd-ryzen-ai-max-plus-395.html), [AMD Variable Graphics Memory overview](https://www.amd.com/en/blogs/2025/amd-ryzen-ai-max-395-processor-breakthrough-ai-.html), and the official [`fio` source and documentation](https://github.com/axboe/fio). Vendor performance claims are treated as claims until reproduced; the results above were measured directly on this unit with `fio-3.42`.*
