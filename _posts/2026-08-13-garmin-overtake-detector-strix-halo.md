---
layout: post
title: "Finding cycle overtakes in 136 hours of Garmin video"
seo_title: "Garmin overtake detection on AMD Strix Halo"
date: 2026-08-13 00:30:00 +0100
last_modified_at: 2026-08-14 14:00:00 +0100
permalink: /blog/2026/08/13/garmin-overtake-detector-strix-halo/
categories: [local-ai, engineering, cycling]
tags: [computer-vision, rocm, strix-halo, garmin, yolo, ffmpeg, nfs, cycling]
author: Darren Soothill
description: "I built a resilient Strix Halo pipeline that turns 136 hours of paired Garmin cycling footage into synchronized, reviewable vehicle-pass clips on the GPU."
---

I had 135.84 hours of cycling video split across a Garmin Varia Vue on the
front of the bike and a Varia RCT715 at the rear. The useful moments were tiny:
a vehicle approaching from behind, passing, and then appearing ahead. Finding
them by scrubbing through every recording was not a realistic plan.

The result is an open-source pipeline that processes both cameras, identifies
likely passes and creates one 2560x720 clip for each defensible match. The
front view is on the left, the rear view is on the right, and a normal clip
runs from 20 seconds before the rear event to 25 seconds after it.

The code, installation scripts, systemd services, NFS setup and operating
notes are now in the
[Garmin Overtake Detector repository](https://github.com/soothill/garmin-overtake-detector).
It contains no ride footage, GPS data or private deployment configuration.

## The pipeline I ended up with

The final system is more than an object detector. It is an unattended batch
workflow with five distinct stages:

```text
read-only NFS archive
        │
        ├── front detector ──┐
        └── rear detector  ──┤  ROCm + YOLOv8s + BoT-SORT
                             │
                     vehicle handoff matching
                             │
                 three concurrent FFmpeg workers
                             │
                validated front-left / rear-right clips
                             │
                     optional Plex mirror
```

YOLOv8s finds cars, motorcycles, buses and trucks. BoT-SORT gives each vehicle
a short track, and trajectory rules decide whether that track looks like a
pass. A rear candidate should grow as it approaches and leave through the
expected part of the picture; its front counterpart should appear and recede.
Cross traffic, very short tracks and motion in the wrong direction are
rejected.

The front and rear detectors run at the same time. Composition no longer waits
for the whole archive either: as soon as both camera results for one date have
validated, one of three composition workers can start making clips. That
overlap matters when a ride produces hundreds of candidates.

## Matching the same second was not enough

The hardest fault looked correct at first. Both camera views showed the same
burned-in time, yet the vehicles did not match.

The cameras' clocks had a stable bias, and missing sections in a daily file
could also change the relationship between media time and clock time. Forcing
both views to display the same second therefore aligned two clock readings,
not necessarily the same physical moment. One verified pass needed a
14-second difference between the displayed camera clocks.

The corrected `vehicle_handoff_clock_v2` method works at event level:

1. OCR reads the burned-in time near rear disappearances and front appearances.
2. The matcher estimates the stable bias between the two camera clocks.
3. It compares the ordered vehicle-event sequences, with a maximum 1.5-second
   residual after accounting for that bias.
4. Each accepted pair receives its own media-timeline offset, so a missing
   recording section does not shift the rest of the ride.
5. An ambiguous rear event is left unmatched rather than joined to the wrong
   front vehicle.

This was the most important lesson from the project: timestamp agreement is
only evidence of synchronisation when the clocks themselves have been
calibrated. The physical handoff is the thing that needs to agree.

## GPU, NPU or Hailo?

The EVO-X3 has a Ryzen AI MAX+ 395, Radeon 8060S graphics and an NPU, so the
NPU initially looked like the power-efficient choice. I tested that assumption
with one 95-minute recording from each camera: 3.168 source hours in total.
Every backend decoded at five frames per second, resized to the same 640x640
model input, used 0.20 confidence and 0.50 IoU, then ran the same tracker and
trajectory rules. Clip encoding was outside the timer.

| Platform | Model | Wall time | Real-time factor | Measured energy | Candidate events |
|---|---|---:|---:|---:|---:|
| Radeon 8060S GPU | YOLOv8s FP16 | 12.26 min | 15.719x | 14.93Wh APU package | 153 |
| Ryzen AI NPU | same-source YOLOv8s XINT8 | 28.07 min | 6.774x | 41.42Wh APU package | 167 |
| Hailo-8L | YOLOv8s HEF | 63.35 min | 3.001x | 4.81Wh Pi PMIC rails | 176 |

The GPU and NPU numbers are directly comparable: the same EVO-X3, source pair,
client-cache precondition, clean idle gate and APU package measurement. The GPU
finished 56.32% sooner and used 63.95% less gross package energy. For this
end-to-end workload the GPU was both the speed and energy-efficiency winner.

The Hailo number needs different language. Its 4.81Wh covers internal Raspberry
Pi PMIC output rails, not the same system boundary as the EVO-X3 package. It is
a useful directional result, but I would need the same external wall meter on
all hosts before publishing a three-way energy ranking.

The first NPU result had used AMD's available quantized YOLOv8m graph. That was
useful as a deployable baseline, but it was not a fair model comparison. I
therefore exported the exact `yolov8s.pt` weights used by the GPU, calibrated
them on 128 held-out Garmin frames, quantized the detector body to XINT8 with
AMD Quark and reran the complete pair through the Vitis AI execution provider.
The GPU and NPU now have hash-proven common source weights. The Hailo graph is
also YOLOv8s, although its vendor HEF does not expose the original training
weight hash.

The result was counter-intuitive. AMD SMI reported only 1.92W mean direct NPU
power, yet the whole APU package averaged 88.54W. CPU-core power averaged about
79.28W. The compiled subgraph was using the low-power accelerator, but video
decode, tensor handling, floating-point box decoding, non-maximum suppression
and tracking around it kept the CPU busy. The old vendor graph had consumed
less package energy, while the more comparable standard YOLO export made much
better detections and consumed more.

Peak TOPS and accelerator-only watts therefore did not describe end-to-end
efficiency. The next NPU experiment is not simply a smaller quantization scale;
it is a compiler-friendly raw-head export that moves or removes CPU fallback
and data-layout conversion.

The production path therefore remains PyTorch on ROCm with FFmpeg/VAAPI. This
is a workload-specific choice, not a claim that the NPU is never useful. A
smaller, fully supported graph or a low-duty live workload could produce a
different result.

## Detection rate matters as much as energy

An accelerator should not look efficient simply because its model finds less
work. There is no human-labelled ground truth for this benchmark pair, so I
used a deliberately modest proxy: an event enters the consensus set when at
least two of the three platforms report it within two seconds.

The same-model run produced 154 consensus event clusters. Hailo found 149
(96.75%), the NPU 146 (94.81%) and the GPU 142 (92.21%). Replacing the earlier
NPU YOLOv8m deployment with same-source YOLOv8s raised NPU consensus coverage
from 78.67% to 94.81%—a 16.14 percentage-point gain. Raw NPU detections rose
from 33,913 to 86,704 and candidate events from 126 to 167.

The other side is candidate confirmation: 92.81% for GPU, 87.43% for NPU and
84.66% for Hailo. The extra NPU and Hailo candidates may represent better
recall, more false positives or tracks split differently; agreement alone
cannot decide that. Those disagreements are the first frames I would label.

The original common numerical threshold was not a common operating point:
median maximum event confidence had been about 0.93 on GPU, 0.53 on the older
NPU graph and 0.91 on Hailo. Same-source XINT8 moved the NPU median to about
0.94. That closes an important comparability gap, but it still is not labelled
precision or recall. The defensible route is to label representative day,
night, rain and occlusion cases, use camera-domain quantization calibration,
and select a separate threshold for each backend that meets one held-out recall
target.

## What the measured run produced

The retained archive contained 66 authoritative camera files—36 front and 30
rear—covering 135.84 source hours. Detection consumed 16.493 aggregate worker
hours.

| Measure | Result |
|---|---:|
| Source video | 135.84 hours |
| Camera files | 66 |
| Aggregate detector time | 16.493 worker-hours |
| Detector throughput | 8.236x real time |
| Work per source hour | 7.285 worker-minutes |
| Synchronized front/rear clips | 633 |
| Defensible rear-only clips retained after review | 651 |
| Buffered NFS sequential read | about 117 MB/s |

Those event counts describe this archive, camera position and rule set. They
are not a general precision or recall score. In particular, a rear-only clip
can still contain a real passing vehicle when the front camera did not record a
usable counterpart. The review stage retained those cases instead of inventing
a match.

The network was not the single-worker bottleneck. Even three active composition
workers used only a fraction of the gigabit path in the observed run. Running
front and rear detection concurrently reduced elapsed time while leaving headroom
for composition and the output mirror.

## Making a long batch survive failure

The first useful version could process a file. The version I would trust with
136 unattended hours also needed to explain what happened after a failure.

The hardened runner now has:

- preflight checks for the read-only source mount, GPU, telemetry and free disk;
- independent front and rear status plus per-file progress heartbeats;
- a five-minute watchdog for stuck work;
- atomic reports, so an interrupted write cannot masquerade as completion;
- validation evidence for every camera result and every combined date;
- archived failed attempts and a three-failure limit for the current method;
- resumable processing that preserves already validated work;
- locked reports when several composition workers finish together;
- a 100 GiB free-space floor; and
- publication rules that allow only validated clips into the Plex mirror.

The source archive is mounted read-only and appears inside containers as
`/videos:ro`. Outputs, temporary files and reports live elsewhere. That
separation is enforced by preflight rather than left as a convention.

## Reproducing it

The tested host is Ubuntu 24.04 with ROCm 7.14 support for `gfx1151`. Clone the
project into the recommended path:

```bash
git clone https://github.com/soothill/garmin-overtake-detector.git \
  "$HOME/garmin-overtake-detector"
cd "$HOME/garmin-overtake-detector"
```

Install the host dependencies, then install the user services and build the
container:

```bash
./scripts/install-host-dependencies-ubuntu.sh
# Log out and in after the Docker group change.
./install.sh
```

The expected source layout is deliberately simple:

```text
/mnt/garmin/
├── varia-vue/YYYY-MM-DD/*.mp4
└── rct715/YYYY-MM-DD/*.mp4
```

An example environment file, NFS server and client installers, GPU preflight,
batch services, validation tools, tests and troubleshooting guide are included.
After configuring the paths, start the batch with:

```bash
./preflight-evox3.sh
systemctl --user start garmin-overtakes-gpu-all.service
journalctl --user -fu garmin-overtakes-gpu-all.service
```

The container build pins the tested ROCm, PyTorch, Ultralytics, OpenCV and
tracking components. It was rebuilt from a clean copy and tested against the
Radeon 8060S before publication.

## Limits and responsible use

This is an evidence-review tool, not a calibrated passing-distance instrument.
A monocular bounding box does not provide a defensible distance in metres
without camera calibration and geometry. It also does not decide whether a
pass was lawful or dangerous.

Road footage may expose faces, number plates, homes, locations and timestamps.
Keep source recordings private, set an appropriate retention period, restrict
access to the output library and check the law that applies where the camera
was used. The public repository deliberately excludes every production
manifest, image and clip.

## What I would improve next

The most valuable next step is a labelled evaluation set drawn from varied
weather, light, traffic and camera positions. That would turn useful archive
counts into measured precision and recall. Camera calibration could support a
separate distance-estimation experiment, while plate and face redaction would
make retained evidence safer to handle.

For now, the project has done the job I wanted: turn an unmanageable archive
into short, traceable clips without modifying the original recordings, and
make the complete route reproducible for somebody else's Strix Halo system.

---

© 2026 Darren Soothill. All rights reserved.
