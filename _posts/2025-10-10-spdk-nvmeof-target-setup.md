---
layout: post
title: "SPDK NVMe-oF Target Setup Guide for Ubuntu with RDMA"
date: 2025-10-10
categories: [Storage, SPDK, NVMe]
tags: [spdk, nvme-of, rdma, ubuntu, storage, high-performance]
author: Darren Soothill
description: "Complete step-by-step guide to configure SPDK NVMe over Fabrics target on Ubuntu Linux with RDMA transport for high-performance storage."
keywords: "SPDK, NVMe-oF, RDMA, Ubuntu, Linux, storage configuration, high-performance"
---

Step-by-step guide to configure SPDK NVMe over Fabrics target on Ubuntu Linux with RDMA transport. Includes installation, configuration, systemd setup, and troubleshooting for high-performance storage.

## Introduction

This guide walks you through setting up an NVMe over Fabrics (NVMe-oF) target using the Storage Performance Development Kit (SPDK) on Ubuntu Linux. The configuration uses RDMA (Remote Direct Memory Access) as the transport protocol for high-performance, low-latency storage access.

**Note:** This guide assumes you have RDMA-capable network hardware (InfiniBand or RoCE) properly installed in your system.

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
  python3-pip \
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

SPDK requires hugepages for optimal performance:

```bash
echo 2048 | sudo tee /proc/sys/vm/nr_hugepages
```

**Important:** Adjust the hugepage count based on your system's RAM and requirements. Each 2MB hugepage requires 2MB of system memory.

## 2. Download and Build SPDK

### Clone SPDK Repository

```bash
cd /opt
sudo git clone https://github.com/spdk/spdk
cd spdk
sudo git submodule update --init
```

### Install Python Dependencies

```bash
sudo pip3 install -r scripts/pkgdep/requirements.txt
```

### Configure and Build

```bash
# Configure SPDK with RDMA support
sudo ./configure --with-rdma

# Build SPDK (using all available CPU cores)
sudo make -j$(nproc)

# Setup SPDK environment (hugepages and drivers)
sudo scripts/setup.sh
```

**Tip:** The build process may take 10-15 minutes depending on your system.

## 3. Configuration

### Option A: JSON Configuration File

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
            "allow_any_host": true,
            "serial_number": "SPDK00000000000001",
            "model_number": "SPDK_Controller1",
            "max_namespaces": 32
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

**Customization Required:** Replace `192.168.1.100` with your RDMA interface IP address.

### Using Real NVMe Devices

For production environments, replace malloc bdevs with actual NVMe devices:

```bash
# Find your NVMe device PCIe address
lspci | grep -i nvme

# Example: Attach NVMe device at PCIe address 0000:01:00.0
$SPDK_DIR/scripts/rpc.py -s $RPC_SOCK bdev_nvme_attach_controller \
  -b Nvme0 \
  -t PCIe \
  -a 0000:01:00.0
```

## 4. Systemd Service Configuration

### Create Service File

```bash
cat << 'EOF' | sudo tee /etc/systemd/system/spdk-nvmf-target.service
[Unit]
Description=SPDK NVMe-oF Target
After=network.target

[Service]
Type=simple
ExecStartPre=/opt/spdk/scripts/setup.sh
ExecStart=/opt/spdk/build/bin/nvmf_tgt -m 0x3 -s 512
ExecStartPost=/opt/spdk/setup_nvmf_target.sh
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

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
      mtu: 9000
      optional: true
EOF

sudo netplan apply
```

**Important:** Replace `ens1f0` with your actual RDMA interface name and adjust the IP address accordingly.

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
#!/bin/bash
RPC_SOCK="/var/tmp/spdk.sock"

echo "=== Block Devices ==="
/opt/spdk/scripts/rpc.py -s $RPC_SOCK bdev_get_bdevs

echo -e "\n=== NVMe-oF Subsystems ==="
/opt/spdk/scripts/rpc.py -s $RPC_SOCK nvmf_get_subsystems

echo -e "\n=== Transport Statistics ==="
/opt/spdk/scripts/rpc.py -s $RPC_SOCK nvmf_get_stats

echo -e "\n=== Connected Hosts ==="
/opt/spdk/scripts/rpc.py -s $RPC_SOCK nvmf_subsystem_get_qpairs
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
- Verify the target is listening: `netstat -an | grep 4420`

### Performance Issues

- Increase the number of hugepages
- Adjust CPU core mask in the service file
- Tune RDMA transport parameters in the configuration
- Enable MTU 9000 (jumbo frames) on RDMA interfaces

## Production Considerations

- **Security:** Change `allow_any_host: true` to specific host authentication for production
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
- [SPDK GitHub Repository](https://github.com/spdk/spdk)
- [NVMe Specifications](https://nvmexpress.org/)

---

© 2025 Darren Soothill. All rights reserved.
