---
layout: post
title: "S3 benchmarking with parallel ranged downloads"
seo_title: "S3 ranged-download benchmarking with s3bench"
date: 2026-02-22
last_modified_at: 2026-08-06
categories: [storage, benchmarking, s3, aws]
tags: [s3, benchmarking, multipart, throughput, aws, minio, go]
author: Darren Soothill
editorial_standard: soothill-human-v1
editorial_review_status: approved
editorial_reviewer: Darren Soothill
editorial_reviewed_at: 2026-08-17
description: "Benchmark parallel S3 ranged-download performance with s3bench, a Go tool for measuring throughput against AWS S3 and compatible object stores."
---

I built **s3bench** to answer a narrow question: how does an S3 endpoint behave when one large object is fetched through concurrent HTTP range requests? It controls the chunk size and concurrency, then records the throughput and latency of that access pattern.

That result is not a general score for AWS S3, MinIO, Ceph or any other backend. The client, network, object shape, endpoint, cache state and output mode are all part of the measurement.

## Why Parallel Range Requests Matter

S3 defines a Multipart Upload API, but there is no equivalent “multipart download” API. For downloads, s3bench sends concurrent `GetObject` requests with HTTP `Range` headers. Instead of reading a 10GiB object as a single stream, it can:

1. Split the object into chunks using HTTP `Range` headers
2. Download multiple chunks concurrently
3. Write the chunks in order when `--output` is used, or discard them when measuring the transfer path alone

This approach can improve throughput for large objects and high-latency paths. It is not guaranteed to do so: the optimum depends on the endpoint, link, client CPU and service limits.

## How s3bench Works

The tool does five things:

1. **HeadObject** - Determines the object size
2. **Chunk Division** - Splits the object into configurable byte-range chunks
3. **Concurrent Download** - Dispatches goroutines to fetch chunks in parallel using `Range` headers
4. **Live Progress** - Shows real-time transfer rates (updated every 200ms)
5. **Detailed Reporting** - Reports throughput, time-to-first-byte, and latency percentiles

## Get s3bench

**GitHub repository:** [soothill/s3bench](https://github.com/soothill/s3bench)

You can:

- **Clone the repository**:
  ```bash
  git clone https://github.com/soothill/s3bench.git
  ```

- **Download releases**: Visit the [release page](https://github.com/soothill/s3bench/releases) for pre-built binaries

- **Browse the source code**: The behaviour described here was checked against commit [`49344ec`](https://github.com/soothill/s3bench/tree/49344ec0ce2ce533256ddef8e78c7b157a54068a)

## Installing Go

s3bench requires **Go 1.22 or later**. Here's how to install Go on different platforms:

### Linux

Ubuntu or Debian:

```bash
sudo apt update
sudo apt install golang-go
go version
```

Fedora, RHEL or CentOS Stream:

```bash
sudo dnf install golang
go version
```

Arch Linux:

```bash
sudo pacman -S go
go version
```

If the distribution package is older than Go 1.22, use the signed archive and instructions from the official [Go downloads page](https://go.dev/dl/).

### macOS

With Homebrew:

```bash
brew install go
go version
```

The official macOS package is also available from [go.dev/dl](https://go.dev/dl/).

### Windows

Use the official Windows installer from [go.dev/dl](https://go.dev/dl/). After installation, open a new PowerShell window and verify the toolchain:

```powershell
go version
```

## Building from Source

Once Go is installed:

```bash
cd s3bench
go mod tidy
go build -o s3bench .
```

## Basic Usage

```bash
./s3bench \
  --bucket my-bucket \
  --key path/to/large-file.bin \
  --chunk-size 64MB \
  --concurrency 16 \
  --discard
```

Use `--discard` when the question is specifically about the network and object-store path; it prevents local disk I/O from becoming the bottleneck. Use `--output` when the end-to-end download path, including the destination filesystem, is what matters.

## Key Features

### Chunk Size Presets

Instead of remembering byte values, use intuitive presets:

| Preset | Size |
|--------|------|
| XS | 1 MiB |
| S | 4 MiB |
| M | 8 MiB |
| L | 64 MiB |
| XL | 256 MiB |
| XXL | 1 GiB |

```bash
./s3bench --chunk-size L --bucket mybucket --key bigfile.bin --discard
```

### Concurrency Sweep

Use a concurrency sweep to find where this particular path stops gaining throughput. Pass several worker counts in one run:

```bash
./s3bench \
  --bucket my-bucket \
  --key path/to/large-file.bin \
  --chunk-size 64MB \
  --concurrency 4,8,16,32,64 \
  --runs 3 \
  --discard
```

This produces a comparison report:

```
╔══════════════════════════════════════════════════════════╗
║              Concurrency Sweep Comparison               ║
╚══════════════════════════════════════════════════════════╝

  Workers     Runs    Min MB/s  Mean MB/s   Max MB/s
  -------     ----    --------  ---------   --------
           4     3       412.1      438.7      461.3
           8     3       781.4      823.9      856.2
          16     3      1102.5     1163.8     1201.4
          32     3      1367.9     1401.5     1423.0 <-- best
          64     3      1389.2     1398.1     1412.7
```

The tool currently labels binary units as `MB` and `GB`; its calculations divide by powers of two, so those values are MiB/s and GiB/s in IEC terminology.

### S3-Compatible Storage

Works with MinIO, Ceph, and any S3-compatible endpoint:

```bash
./s3bench \
  --endpoint http://minio.local:9000 \
  --bucket testbucket \
  --key bigfile.bin \
  --access-key-id minioadmin \
  --secret-access-key minioadmin \
  --region us-east-1 \
  --chunk-size 64MB \
  --concurrency 8,16,32 \
  --runs 3 \
  --discard
```

## Detailed Output

### Per-Run Summary

```
=== Run 1 ===
  Object:       s3://my-bucket/path/to/large-file.bin
  Object size:  10.00 GB
  Chunk size:   64.00 MB  (160 chunks)
  Concurrency:  16 workers

  Results:
    Total time:        8.432 s
    Total bytes:       10.00 GB
    Throughput:        1184.3 MB/s  (1.157 GB/s)
    Time to 1st byte:  42.3 ms

  Chunk latency (per-chunk download time):
    Min:   341.2 ms
    Max:   892.7 ms
    Mean:  526.4 ms
    P50:   512.1 ms
    P95:   781.3 ms
    P99:   856.4 ms
```

### JSON Output

For scripting and automation:

```bash
./s3bench --bucket b --key k --concurrency 8,16,32 --discard --json \
  | jq '.[] | {workers: .Concurrency, mean_mb_s: .Aggregate.mean_throughput_mb_s}'
```

**Known interface caveat:** in commit `49344ec`, duration fields such as `total_time_ms` and `ttfb_ms` are serialised from Go's `time.Duration` without conversion. Their numeric values are nanoseconds despite the `_ms` suffix. Convert them before use—for example, divide by `1,000,000` for milliseconds—and pin the tool revision in automated reports until the schema is corrected.

## How I would run the comparison

Use these as starting points, then retain the settings and conditions with the result:

### 1. Sweep concurrency
Run `--concurrency 4,8,16,32,64` to locate the plateau. A plateau shows that some part of the measured path has saturated; it does not identify the bottleneck by itself.

### 2. Balance Chunk Size and Concurrency
- **Smaller chunks + more workers** = more connection overhead
- **Larger chunks + fewer workers** = potential worker idle time
- **Starting point**: try `--chunk-size L --concurrency 16`, then sweep in both directions

### 3. Use Multiple Runs and Record the Conditions
Use `--runs 3` or more and report the spread, not only the best result. A slower first run might reflect DNS, connection setup, TLS, a client-side cache or an object-store cache; do not attribute it to storage without evidence.

### 4. Match the Output Mode to the Question
Use `--discard` for network and object-store throughput. Use `--output` when validating the complete path to local storage, and verify the resulting object separately if integrity is part of the test.

### 5. Test from the Right Location
Results are only meaningful when measured from where your workload actually runs. For example:
- EC2 instance in the same region as the bucket (for AWS)
- Same network segment as your MinIO deployment
- Avoid a laptop over VPN unless that path is the workload you intend to measure

## All Command-Line Options

| Flag | Default | Description |
|------|---------|-------------|
| `--bucket` | *(required)* | S3 bucket name |
| `--key` | *(required)* | S3 object key to download |
| `--chunk-size` | `64MB` | Size of each byte-range read |
| `--concurrency` | `8` | Parallel workers (single or comma-separated) |
| `--runs` | `1` | Repetitions per concurrency level |
| `--profile` | `impossible` | AWS named profile |
| `--access-key-id` | `""` | Override access key |
| `--secret-access-key` | `""` | Override secret key |
| `--region` | `us-east-1` | AWS region |
| `--endpoint` | `""` | Custom S3-compatible endpoint |
| `--discard` | `false` | Discard downloaded bytes |
| `--output` | `""` | Write to file instead |
| `--json` | `false` | JSON output |

## What the result can and cannot say

Parallel ranged GETs are one useful way to exercise high-throughput object access. They can show where throughput plateaus for a recorded object, client, endpoint, chunk size and worker count. They cannot, on their own, identify whether the limiting component is the client, network or storage backend, and they do not represent small-object or whole-object streaming workloads.

Use the same object shape, output mode and client location when comparing systems or releases. Report the spread across repeated runs rather than only the best result, and keep the tool revision with the data. The source, current documentation and release status are in the [s3bench GitHub repository](https://github.com/soothill/s3bench); it is published under the MIT licence.
