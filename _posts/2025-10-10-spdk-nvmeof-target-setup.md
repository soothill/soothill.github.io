---
layout: post
title: "SPDK NVMe-oF Target Setup Guide for Ubuntu with RDMA"
seo_title: "SPDK NVMe-oF target with RDMA on Ubuntu"
date: 2025-10-10
last_modified_at: 2026-08-06
categories: [storage, spdk, nvme]
tags: [spdk, nvme-of, rdma, ubuntu, storage, high-performance]
author: Darren Soothill
description: "Build SPDK v26.05 and configure an NVMe over Fabrics target on Ubuntu with RDMA, explicit host access and a persistent JSON configuration."
keywords: "SPDK, NVMe-oF, RDMA, Ubuntu, Linux, storage configuration, high-performance"
---

This lab guide configures an SPDK NVMe over Fabrics target on Ubuntu with an RDMA transport, a disposable memory-backed block device and an explicitly authorised host. It pins SPDK `v26.05` so the commands and JSON schema have a reproducible version boundary.

## Introduction

The configuration uses RDMA (Remote Direct Memory Access) as the transport. The memory-backed example proves the software and network path without risking a real drive; adapting it to physical NVMe storage requires a separate maintenance plan.

**Scope:** this is a starting point for a controlled lab, not a production architecture. It assumes an RDMA-capable adapter and driver, a tested InfiniBand or RoCE fabric, and a client whose NVMe host NQN is known. On RoCE, validate lossless-network design, PFC/ECN policy, VLAN isolation and MTU end to end rather than treating one host setting as sufficient.

## 1. Prerequisites and System Setup

### Install Required Packages

```bash
sudo apt-get update

sudo apt-get install -y \
  build-essential \
  git \
  pkg-config \
  libaio-dev \
  libssl-dev \
  libnuma-dev \
  libpcap-dev \
  python3 \
  rdma-core \
  libibverbs-dev \
  librdmacm-dev \
  ibverbs-utils \
  infiniband-diags
```

### Load RDMA Kernel Modules

```bash
sudo modprobe rdma_cm
sudo modprobe ib_uverbs
sudo modprobe rdma_ucm
sudo modprobe ib_umad
```

### Enable RDMA Modules on Boot

```bash
cat << 'EOF' | sudo tee /etc/modules-load.d/rdma.conf
rdma_cm
ib_uverbs
rdma_ucm
ib_umad
EOF
```

### Configure Hugepages

SPDK uses hugepages for DMA-backed memory. Reserve them persistently and check that the allocation succeeded:

```bash
echo 'vm.nr_hugepages = 2048' | sudo tee /etc/sysctl.d/80-spdk-hugepages.conf
sudo sysctl --system
grep -E 'HugePages_Total|HugePages_Free|Hugepagesize' /proc/meminfo
```

**Important:** Adjust the hugepage count based on your system's RAM and requirements. Each 2MB hugepage requires 2MB of system memory.

## 2. Download and Build SPDK

### Clone SPDK Repository

```bash
sudo install -d -o "$USER" -g "$(id -gn)" /opt/spdk
git clone --branch v26.05 --depth 1 https://github.com/spdk/spdk /opt/spdk
cd /opt/spdk
git submodule update --init --recursive
git describe --tags --always
```

### Install SPDK Dependencies

```bash
cd /opt/spdk
sudo scripts/pkgdep.sh --rdma
```

Using SPDK's dependency script avoids writing directly into Ubuntu's externally managed system Python with `sudo pip`.

### Configure and Build

```bash
# Configure SPDK with RDMA support
./configure --with-rdma

# Build SPDK (using all available CPU cores)
make -j"$(nproc)"
```

Do not run `scripts/setup.sh` unqualified on a storage host: depending on its environment, it can bind supported PCIe devices to a userspace driver. The malloc-backed example needs the hugepage reservation above, not ownership of a physical NVMe controller.

## 3. Configuration

### JSON Configuration File

Create a declarative configuration file for the NVMe-oF target:

```bash
cat << 'EOF' | sudo tee /opt/spdk/nvmf_target.json
{
  "subsystems": [
    {
      "subsystem": "bdev",
      "config": [
        {
          "method": "bdev_malloc_create",
          "params": {
            "name": "Malloc0",
            "num_blocks": 131072,
            "block_size": 4096
          }
        }
      ]
    },
    {
      "subsystem": "nvmf",
      "config": [
        {
          "method": "nvmf_create_transport",
          "params": {
            "trtype": "RDMA",
            "max_queue_depth": 128,
            "max_qpairs_per_ctrlr": 64,
            "in_capsule_data_size": 4096,
            "max_io_size": 131072,
            "io_unit_size": 131072,
            "max_aq_depth": 128,
            "num_shared_buffers": 4095,
            "buf_cache_size": 64
          }
        },
        {
          "method": "nvmf_create_subsystem",
          "params": {
            "nqn": "nqn.2024-10.io.spdk:cnode1",
            "allow_any_host": false,
            "serial_number": "SPDK00000000000001",
            "model_number": "SPDK_Controller1",
            "max_namespaces": 32
          }
        },
        {
          "method": "nvmf_subsystem_add_host",
          "params": {
            "nqn": "nqn.2024-10.io.spdk:cnode1",
            "host": "nqn.2014-08.org.nvmexpress:uuid:REPLACE-WITH-CLIENT-HOST-NQN"
          }
        },
        {
          "method": "nvmf_subsystem_add_ns",
          "params": {
            "nqn": "nqn.2024-10.io.spdk:cnode1",
            "namespace": {
              "nsid": 1,
              "bdev_name": "Malloc0"
            }
          }
        },
        {
          "method": "nvmf_subsystem_add_listener",
          "params": {
            "nqn": "nqn.2024-10.io.spdk:cnode1",
            "listen_address": {
              "trtype": "RDMA",
              "adrfam": "IPv4",
              "traddr": "192.168.1.100",
              "trsvcid": "4420"
            }
          }
        }
      ]
    }
  ]
}
EOF
```

**Customisation required:** replace `192.168.1.100` with the RDMA interface address and replace the sample host NQN with the exact value from `/etc/nvme/hostnqn` on the client. Generate a unique subsystem NQN for your environment rather than reusing the example unchanged.

### Using Real NVMe Devices

Do not export a controller that the target host is mounting or otherwise using; concurrent host and SPDK access can corrupt data. In a maintenance window, identify the controller by PCI address, back up its data, stop every consumer and bind only that validated controller to SPDK. Then replace the `bdev_malloc_create` entry in the JSON with a version-matched `bdev_nvme_attach_controller` entry and change the namespace's `bdev_name` to the resulting namespace bdev, normally `Nvme0n1`.

```bash
# Record stable device and PCI identities before changing driver ownership
sudo nvme list
lspci -Dnn | grep -i 'non-volatile memory'

# Review which devices SPDK would claim before applying a driver change
cd /opt/spdk
sudo scripts/setup.sh status

# Example only: bind exactly one validated controller and leave hugepages unchanged
sudo env PCI_ALLOWED="0000:01:00.0" SKIP_HUGE=yes scripts/setup.sh
```

The corresponding bdev entry in `nvmf_target.json` is:

```json
{
  "method": "bdev_nvme_attach_controller",
  "params": {
    "trtype": "pcie",
    "name": "Nvme0",
    "traddr": "0000:01:00.0"
  }
}
```

Change the namespace `bdev_name` from `Malloc0` to `Nvme0n1` after confirming the name returned by SPDK. The [SPDK system-configuration documentation](https://spdk.io/doc/system_configuration.html) describes device binding. Keep `PCI_ALLOWED` explicit; if it is empty, `setup.sh` can bind every compatible device. A physical-device deployment must also repeat the allowlisted binding before the service starts after each reboot.

## 4. Systemd Service Configuration

### Create Service File

```bash
cat << 'EOF' | sudo tee /etc/systemd/system/spdk-nvmf-target.service
[Unit]
Description=SPDK NVMe-oF Target
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
ExecStart=/opt/spdk/build/bin/nvmf_tgt -m 0x3 -s 512 -c /opt/spdk/nvmf_target.json
LimitMEMLOCK=infinity
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

If a physical controller is later added, use a reviewed, device-specific preparation step before this service starts; do not replace it with a command that can claim every compatible NVMe controller.

### Enable and Start Service

```bash
# Reload systemd configuration
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable spdk-nvmf-target.service

# Start the service
sudo systemctl start spdk-nvmf-target.service

# Check service status
sudo systemctl status spdk-nvmf-target.service
```

## 5. Network Configuration

### Configure RDMA Interface

Set up your RDMA-capable network interface using Netplan:

```bash
cat << 'EOF' | sudo tee /etc/netplan/60-rdma.yaml
network:
  version: 2
  ethernets:
    ens1f0:  # Replace with your RDMA interface name
      addresses:
        - 192.168.1.100/24
      mtu: 9000  # Use only when the complete path has been configured and tested at this MTU
      optional: true
EOF

sudo netplan apply
```

**Important:** replace `ens1f0` with the verified RDMA interface and adjust the address. An MTU of 9000 is optional and works only when the host, switches and client use a compatible end-to-end MTU; otherwise retain the network's proven value.

### Verify RDMA Setup

```bash
# List RDMA devices
ibv_devices

# Display detailed RDMA device information
ibv_devinfo

# Check RDMA link status
ibstat
```

## 6. Client Connection

### Install NVMe-CLI on Client

On the initiator/client host, install nvme-cli:

```bash
sudo apt-get install -y nvme-cli
```

### Discover NVMe-oF Targets

```bash
sudo nvme discover -t rdma -a 192.168.1.100 -s 4420
```

### Connect to Target

```bash
sudo nvme connect -t rdma \
  -n nqn.2024-10.io.spdk:cnode1 \
  -a 192.168.1.100 \
  -s 4420
```

### Verify Connection

```bash
# List all NVMe devices
sudo nvme list

# Show NVMe-oF connections
sudo nvme list-subsys
```

### Disconnect from Target

```bash
sudo nvme disconnect -n nqn.2024-10.io.spdk:cnode1
```

## 7. Monitoring and Management

### Create Monitoring Script

```bash
cat << 'EOF' > /opt/spdk/monitor_target.sh
#!/usr/bin/env bash
set -euo pipefail
RPC_SOCK="/var/tmp/spdk.sock"

echo "=== Block Devices ==="
/opt/spdk/scripts/rpc.py -s "$RPC_SOCK" bdev_get_bdevs

printf '\n=== NVMe-oF Subsystems ===\n'
/opt/spdk/scripts/rpc.py -s "$RPC_SOCK" nvmf_get_subsystems

printf '\n=== Transport Statistics ===\n'
/opt/spdk/scripts/rpc.py -s "$RPC_SOCK" nvmf_get_stats

printf '\n=== Connected Hosts ===\n'
/opt/spdk/scripts/rpc.py -s "$RPC_SOCK" nvmf_subsystem_get_qpairs \
  nqn.2024-10.io.spdk:cnode1
EOF

chmod +x /opt/spdk/monitor_target.sh
```

### Common Management Commands

**List all block devices:**
```bash
/opt/spdk/scripts/rpc.py -s /var/tmp/spdk.sock bdev_get_bdevs
```

**List NVMe-oF subsystems:**
```bash
/opt/spdk/scripts/rpc.py -s /var/tmp/spdk.sock nvmf_get_subsystems
```

**View I/O statistics:**
```bash
/opt/spdk/scripts/rpc.py -s /var/tmp/spdk.sock nvmf_get_stats
```

## Troubleshooting

### SPDK Target Won't Start

- Check if hugepages are configured: `cat /proc/meminfo | grep Huge`
- Verify RDMA modules are loaded: `lsmod | grep rdma`
- Check system logs: `sudo journalctl -u spdk-nvmf-target.service`

### Client Cannot Connect

- Verify RDMA connectivity: `ibstat`
- Check firewall rules allow RDMA traffic
- Ensure IP addresses match between configuration and network setup
- Query `nvmf_get_subsystems`, then run `nvme discover` from the authorised client; a TCP socket listing is not an authoritative check for an RDMA listener

### Performance Issues

- Increase the number of hugepages
- Adjust CPU core mask in the service file
- Tune RDMA transport parameters in the configuration
- Tune queue depth, CPU placement and transport parameters one change at a time against a recorded workload
- For RoCE, validate end-to-end MTU and the fabric's congestion and loss-management configuration

## Production Considerations

- **Access:** Keep `allow_any_host` disabled and authorise only known host NQNs; add authentication where the chosen transport, SPDK release and threat model support it
- **Storage:** Use real NVMe devices instead of malloc bdevs
- **Performance:** Adjust CPU masks and memory allocation based on workload
- **Network:** Ensure dedicated RDMA network with proper MTU settings
- **Monitoring:** Implement proper logging and alerting for the service

## Key Parameters to Customize

- **IP Address:** 192.168.1.100 → Your RDMA interface IP
- **Interface Name:** ens1f0 → Your RDMA NIC name
- **NQN:** nqn.2024-10.io.spdk:cnode1 → Your unique identifier
- **CPU Mask:** -m 0x3 → Adjust based on your CPU topology
- **Memory:** -s 512 → Adjust based on your system RAM

## Additional Resources

- [SPDK Documentation](https://spdk.io/doc/)
- [SPDK NVMe-oF Target Guide](https://spdk.io/doc/nvmf.html)
- [SPDK application options and JSON configuration](https://spdk.io/doc/app_overview.html)
- [SPDK GitHub Repository](https://github.com/spdk/spdk)
- [NVMe Specifications](https://nvmexpress.org/)
