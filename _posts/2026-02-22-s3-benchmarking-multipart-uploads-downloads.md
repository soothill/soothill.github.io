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

## Get s3bench

**GitHub Repository**: [https://github.com/soothill/s3bench](https://github.com/soothill/s3bench)

You can:

- **Clone the repository**:
  ```bash
  git clone https://github.com/soothill/s3bench.git
  ```

- **Download releases**: Visit [https://github.com/soothill/s3bench/releases](https://github.com/soothill/s3bench/releases) for pre-built binaries

- **Browse the source code**: [https://github.com/soothill/s3bench](https://github.com/soothill/s3bench)

## Installing Go

s3bench requires **Go 1.22 or later**. Here's how to install Go on different platforms:

<div class="platform-selector" style="margin: 1.5rem 0;">
<button class="platform-btn active" onclick="showPlatform('linux')" style="background: linear-gradient(135deg, var(--primary), var(--secondary)); color: white; border: none; padding: 0.5rem 1rem; border-radius: 8px 0 0 8px; cursor: pointer; font-weight: 600;">Linux</button>
<button class="platform-btn" onclick="showPlatform('macos')" style="background: var(--border); color: var(--text-primary); border: none; padding: 0.5rem 1rem; cursor: pointer; font-weight: 600;">macOS</button>
<button class="platform-btn" onclick="showPlatform('windows')" style="background: var(--border); color: var(--text-primary); border: none; padding: 0.5rem 1rem; border-radius: 0 8px 8px 0; cursor: pointer; font-weight: 600;">Windows</button>
</div>

<div id="platform-linux" class="platform-content" style="background: var(--bg-darker); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem;">
<h4 style="color: var(--primary-light); margin-top: 0;">🐧 Linux Installation</h4>

<h5 style="margin-top: 1rem;">Ubuntu/Debian</h5>
<pre><code># Download and install Go 1.22
wget https://go.dev/dl/go1.22.0.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.22.0.linux-amd64.tar.gz

# Add to PATH
echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
source ~/.bashrc

# Verify installation
go version</code></pre>

<h5 style="margin-top: 1rem;">Fedora/RHEL/CentOS</h5>
<pre><code># Using dnf
sudo dnf install golang

# Or manually:
wget https://go.dev/dl/go1.22.0.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.22.0.linux-amd64.tar.gz
echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
source ~/.bashrc</code></pre>

<h5 style="margin-top: 1rem;">Arch Linux</h5>
<pre><code>sudo pacman -S go</code></pre>
</div>

<div id="platform-macos" class="platform-content" style="display: none; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem;">
<h4 style="color: var(--primary-light); margin-top: 0;">🍎 macOS Installation</h4>

<h5 style="margin-top: 1rem;">Using Homebrew (Recommended)</h5>
<pre><code># Install via Homebrew
brew install go

# Verify installation
go version</code></pre>

<h5 style="margin-top: 1rem;">Manual Installation</h5>
<pre><code># Download from https://go.dev/dl/
# Or use curl:
curl -OL https://go.dev/dl/go1.22.0.darwin-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.22.0.darwin-amd64.tar.gz

# Add to PATH (zsh)
echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.zshrc
source ~/.zshrc</code></pre>
</div>

<div id="platform-windows" class="platform-content" style="display: none; background: var(--bg-darker); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem;">
<h4 style="color: var(--primary-light); margin-top: 0;">🪟 Windows Installation</h4>

<h5 style="margin-top: 1rem;">Using Chocolatey</h5>
<pre><code># Install via Chocolatey
choco install golang

# Verify installation
go version</code></pre>

<h5 style="margin-top: 1rem;">Using Scoop</h5>
<pre><code># Install via Scoop
scoop install go

# Verify installation
go version</code></pre>

<h5 style="margin-top: 1rem;">Manual Installation</h5>
<pre><code># Download the MSI installer from:
# https://go.dev/dl/go1.22.0.windows-amd64.msi

# Run the installer and follow prompts
# Go will be added to PATH automatically

# Open PowerShell and verify:
go version</code></pre>
</div>

<script>
function showPlatform(platform) {
    // Hide all platform content
    document.querySelectorAll('.platform-content').forEach(el => {
        el.style.display = 'none';
    });
    
    // Show selected platform
    document.getElementById('platform-' + platform).style.display = 'block';
    
    // Update button styles
    document.querySelectorAll('.platform-btn').forEach(btn => {
        btn.style.background = 'var(--border)';
        btn.style.color = 'var(--text-primary)';
        btn.style.borderRadius = '0';
    });
    
    // Highlight active button
    event.target.style.background = 'linear-gradient(135deg, var(--primary), var(--secondary))';
    event.target.style.color = 'white';
    
    // Set border radius based on position
    const buttons = document.querySelectorAll('.platform-btn');
    buttons[0].style.borderRadius = '8px 0 0 8px';
    buttons[buttons.length - 1].style.borderRadius = '0 8px 8px 0';
}
</script>

<style>
.platform-content h5 {
    margin-bottom: 0.5rem;
}
.platform-content pre {
    margin-bottom: 1rem;
}
</style>

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