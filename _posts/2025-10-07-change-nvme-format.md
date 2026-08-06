---
layout: post
title: "Changing an NVMe LBA Format Safely on Linux"
date: 2025-10-07
last_modified_at: 2026-08-06
categories: [storage, nvme]
tags: [nvme, storage, format, linux, block-size]
author: Darren Soothill
description: "A safety-first guide to inspecting and changing a supported NVMe LBA format, with separate notes on namespace management and secure erase."
keywords: "NVMe, format, block size, namespace, storage, Linux"
---

This guide explains how to inspect and change an NVMe namespace's logical block format on Linux. The examples are deliberately conservative: format and namespace-management commands are destructive, controller-specific operations that should be rehearsed on a disposable device before they are used on important storage.

## Overview

Some NVMe devices expose multiple LBA formats, such as 512-byte and 4096-byte logical blocks with different metadata layouts. Support varies by controller and namespace; many consumer drives do not support namespace management, and a familiar LBA format number on one device may mean something different on another.

Before formatting, inspect the controller's Format NVM Attributes (`fna`) in `nvme id-ctrl -H`. Some controllers apply a format to every namespace rather than only the device node supplied on the command line.

## Prerequisites

- NVMe device installed in your system
- Root or sudo access
- nvme-cli tools installed
- A verified backup and restore plan
- Confirmation that the target is not the boot device and is not mounted, in swap, LVM, RAID or another storage stack
- **WARNING:** formatting destroys the namespace's data and filesystem metadata

## Installation

### Install NVMe CLI Tools

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install nvme-cli
```

**RHEL/CentOS/Fedora:**
```bash
sudo dnf install nvme-cli
```

## Identifying Your NVMe Device

### List NVMe Devices

```bash
# List all NVMe devices
sudo nvme list

# Example output:
# Node             SN                   Model                Version  Namespace Usage        Format
# ---------------- -------------------- -------------------- -------- --------- ------------ ------
# /dev/nvme0n1     S123ABC456789        Samsung SSD 980 PRO  1.0      1         500.11  GB / 500.11  GB  512 B + 0 B
```

### Get Device Information

```bash
# Get detailed device info
sudo nvme id-ctrl /dev/nvme0

# Get namespace info
sudo nvme id-ns /dev/nvme0n1
```

## Viewing Supported Formats

### Check Available Formats

```bash
sudo nvme id-ns /dev/nvme0n1 -H | grep "LBA Format"
```

Example output:
```
LBA Format  0 : Metadata Size: 0   bytes - Data Size: 512 bytes - Relative Performance: 0x2 Good
LBA Format  1 : Metadata Size: 0   bytes - Data Size: 4096 bytes - Relative Performance: 0x1 Better
```

## Changing NVMe Format

### Backup Your Data

**CRITICAL:** back up the data and test the restore before formatting. Do not image a live, changing filesystem and assume the result is consistent. Unmount or otherwise quiesce every filesystem and storage layer first.

```bash
# Example raw image after every filesystem on the namespace is unmounted
sudo dd if=/dev/nvme0n1 of=/path/to/backup.img bs=4M status=progress
sync
```

A file-level backup or storage snapshot is often easier to validate and restore than a raw image. Whichever method you choose, keep the backup on a different device.

### Format Command Syntax

```bash
sudo nvme format /dev/nvme0n1 --lbaf=<format_id>
```

**Parameters:**
- `--lbaf=<id>`: LBA Format index (0, 1, 2, etc.)
- `--ses=0`: No secure erase
- `--ses=1`: User data erase
- `--ses=2`: Cryptographic erase

### Example: Change to 4KB Block Size

```bash
# Substitute the LBAF index that this device reports for 4096-byte data
sudo nvme format /dev/nvme0n1 --lbaf=1 --ses=1

# Verify the format
sudo nvme id-ns /dev/nvme0n1 -H | grep "in use"
```

### Example: Change to 512B Block Size

```bash
# Substitute the LBAF index that this device reports for 512-byte data
sudo nvme format /dev/nvme0n1 --lbaf=0 --ses=1
```

The indices above match only the sample output. Always derive the index from `nvme id-ns -H` on the actual namespace before running the command.

## Advanced: Namespace Management

### Delete Namespace

```bash
# Delete namespace 1
sudo nvme delete-ns /dev/nvme0 -n 1
```

### Create New Namespace

```bash
# Create namespace with specific block size
sudo nvme create-ns /dev/nvme0 --nsze=<size_in_blocks> --ncap=<capacity> --flbas=<format>

# Example: Create a 100GiB namespace with 4096-byte logical blocks
sudo nvme create-ns /dev/nvme0 --nsze=26214400 --ncap=26214400 --flbas=1
```

`26,214,400 × 4096` bytes is 100GiB (107.37GB), not 100GB. Confirm the selected `flbas` value and the controller's namespace-management capability before deleting an existing namespace.

### Attach Namespace

```bash
# Discover the controller identifiers, then attach using the required CNTLID
sudo nvme list-ctrl /dev/nvme0
sudo nvme attach-ns /dev/nvme0 -n 1 -c <controller_id>
```

## Verification

### Verify Format Change

```bash
# Check current format
sudo nvme id-ns /dev/nvme0n1 -H | grep -A5 "LBA Format"

# Check logical and physical sector sizes
sudo blockdev --getss /dev/nvme0n1
sudo blockdev --getpbsz /dev/nvme0n1

# Verify device is ready
sudo nvme list
```

### Test Through a Disposable File

After recreating and mounting a filesystem, test through a disposable file. Writing directly to `/dev/nvme0n1` would overwrite the partition table or filesystem metadata.

```bash
# Example only: substitute the actual test mount point
sudo dd if=/dev/zero of=/mnt/nvme-test/format-check.bin \
  bs=1M count=100 conv=fsync status=progress

# Read test
sudo dd if=/mnt/nvme-test/format-check.bin of=/dev/null \
  bs=1M status=progress

sudo rm -- /mnt/nvme-test/format-check.bin
```

## Troubleshooting

### Format Command Fails

**Issue:** Format command returns error

**Solutions:**
```bash
# Check if device is mounted (unmount if necessary)
mount | grep nvme0n1
sudo umount /dev/nvme0n1

# Check if device is in use
lsof | grep nvme0n1
fuser -v /dev/nvme0n1

# Ensure no LVM/RAID is using the device
sudo pvs
sudo mdadm --detail --scan
```

### Namespace Issues

**Issue:** Cannot delete or modify namespace

**Solutions:**
```bash
# Discover the controller ID, then detach the namespace from that controller
sudo nvme list-ctrl /dev/nvme0
sudo nvme detach-ns /dev/nvme0 -n 1 -c <controller_id>

# Then delete
sudo nvme delete-ns /dev/nvme0 -n 1

# Reset this controller if the command's recovery guidance requires it
sudo nvme reset /dev/nvme0

# A subsystem reset is a distinct, wider operation; use it only when required
sudo nvme subsystem-reset /dev/nvme0
```

Do not treat the two reset commands as interchangeable. A subsystem reset can affect every controller in the NVMe subsystem.

### Performance After Format

**Issue:** Poor performance after changing format

**Check alignment:**
```bash
# Check filesystem alignment
sudo parted /dev/nvme0n1 align-check optimal 1

# Recreate filesystem with proper alignment
sudo mkfs.ext4 -b 4096 /dev/nvme0n1
```

## Best Practices

1. **Always backup data** before any format operation
2. **Verify supported formats** using `nvme id-ns` before formatting
3. **Choose the LBA format for the workload and compatibility requirements**; 4096-byte LBAs are not universally faster
4. **Create normally aligned partitions and filesystems** after the format change
5. **Test after formatting** to ensure stability
6. **Document your configuration** for future reference

## Common Use Cases

### Converting Legacy 512B to 4KB

```bash
# 1. Backup data
sudo dd if=/dev/nvme0n1 of=/backup/nvme-backup.img bs=4M

# 2. Use the verified LBAF index for this device; 1 is only an example
sudo nvme format /dev/nvme0n1 --lbaf=1 --ses=1

# 3. Create aligned partition
sudo parted /dev/nvme0n1 --align optimal mklabel gpt
sudo parted /dev/nvme0n1 --align optimal mkpart primary 0% 100%

# 4. Create filesystem with 4KB blocks
sudo mkfs.ext4 -b 4096 /dev/nvme0n1p1
```

### Secure Erase and Reformat

```bash
# Cryptographic erase and format to 4KB
sudo nvme format /dev/nvme0n1 --lbaf=1 --ses=2

# Confirm the command completed successfully, then re-read namespace state
sudo nvme id-ns /dev/nvme0n1 -H
```

The SMART `percentage_used` field is an endurance indicator; it does not prove that a cryptographic erase occurred. A successful format completion is controller-reported evidence, not an independent audit of media sanitisation. Use your organisation's approved sanitisation and verification procedure when assurance matters.

## Important Warnings

- **Data loss:** Formatting destroys all data on the device.
- **No undo:** Format operations cannot be reversed.
- **Device compatibility:** Not all devices support all formats.
- **Namespace support:** Many consumer controllers do not support creating, deleting or attaching namespaces.
- **System disruption:** Never format a device in use by the system.

## Additional Resources

- [NVMe CLI Documentation](https://github.com/linux-nvme/nvme-cli)
- [NVMe Specification](https://nvmexpress.org/specifications/)
- [`blockdev` manual](https://man7.org/linux/man-pages/man8/blockdev.8.html)

## Summary

Changing an NVMe LBA format is a destructive maintenance operation that requires careful attention to:
- Backing up data
- Verifying supported formats
- Proper secure erase selection
- Post-format verification

Always test the new configuration thoroughly before putting the device into production use.
