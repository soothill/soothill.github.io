---
layout: post
title: "S3 Benchmarking: Multipart Upload & Download Testing with s3bench"
date: 2026-02-22
categories: [storage, benchmarking, s3, aws]
tags: [s3, benchmarking, multipart, throughput, aws, minio, go]
author: Darren Soothill
description: "A comprehensive guide to benchmarking S3 multipart download performance using s3bench - a Go tool for measuring throughput against AWS S3 and S3-compatible storage systems."
---

When working with object storage at scale, understanding your throughput characteristics is critical. Whether you're using AWS S3, MinIO, Ceph, or any S3-compatible storage, multipart operations are the key to achieving high performance. In this post, I'll introduce **s3bench**, a command-line tool I've developed for benchmarking download throughput with configurable concurrency and chunk sizes.

## Why Multipart Operations Matter

S3 multipart downloads (and uploads) allow you to parallelize data transfer across multiple connections. Instead of downloading a 10GB file as a single stream, you can:

1. Split the object into chunks using HTTP `Range` headers
2. Download multiple chunks concurrently
3. Reassemble the complete file

This approach can dramatically improve throughput, especially for large objects and high-latency connections.

## How s3bench Works

The tool follows a straightforward but effective approach:

1. **HeadObject** - Determines the object size
2. **Chunk Division** - Splits the object into configurable byte-range chunks
3. **Concurrent Download** - Dispatches goroutines to fetch chunks in parallel using `Range` headers
4. **Live Progress** - Shows real-time transfer rates (updated every 200ms)
5. **Detailed Reporting** - Reports throughput, time-to-first-byte, and latency percentiles

## Building s3bench

Requires [Go 1.22+](https://go.dev/dl/):

```bash
git clone https://github.com/soothill/s3bench.git
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

The `--discard` flag is crucial for pure throughput benchmarking—it prevents local disk I/O from becoming the bottleneck.

## Key Features

### Chunk Size Presets

Instead of remembering byte values, use intuitive presets:

| Preset | Size |
|--------|------|
| XS | 1 MB |
| S | 4 MB |
| M | 8 MB |
| L | 64 MB |
| XL | 256 MB |
| XXL | 1 GB |

```bash
./s3bench --chunk-size L --bucket mybucket --key bigfile.bin --discard
```

### Concurrency Sweep

The most powerful feature for finding optimal settings. Pass multiple concurrency values to automatically benchmark each:

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

## Tuning Recommendations

Based on extensive testing, here are my recommendations:

### 1. Use Concurrency Sweep
Run `--concurrency 4,8,16,32,64` to find your saturation point. Throughput will plateau when you've hit your network or storage ceiling.

### 2. Balance Chunk Size and Concurrency
- **Smaller chunks + more workers** = more connection overhead
- **Larger chunks + fewer workers** = potential worker idle time
- **Sweet spot**: Start with `--chunk-size L --concurrency 16` and sweep from there

### 3. Multiple Runs for Accuracy
Use `--runs 3` or more. The first run often shows slower results due to cold caches on the storage side.

### 4. Always Use Discard Mode for Throughput Testing
When measuring network/storage throughput, use `--discard` to eliminate local disk I/O as a variable.

### 5. Test from the Right Location
Results are only meaningful when measured from where your workload actually runs. For example:
- EC2 instance in the same region as the bucket (for AWS)
- Same network segment as your MinIO deployment
- Not from your laptop over VPN!

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

## Conclusion

Multipart operations are essential for high-performance object storage access. With s3bench, you can:

- Find optimal concurrency settings
- Compare different storage backends
- Validate network infrastructure
- Benchmark before and after optimizations

The tool is open source under the MIT license. Check out the [GitHub repository](https://github.com/soothill/s3bench) for the full source code and documentation.

Happy benchmarking!