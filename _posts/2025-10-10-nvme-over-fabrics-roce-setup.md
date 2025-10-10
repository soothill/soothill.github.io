---
layout: post
title: "NVMe-oF with RoCE Configuration Guide - Ubuntu Server"
date: 2025-10-10
categories: [Storage, NVMe, Linux]
tags: [nvme-of, roce, rdma, ubuntu, storage-configuration, enterprise-storage]
author: Darren Soothill
description: "Complete guide for configuring NVMe over Fabrics (NVMe-oF) with RoCE (RDMA over Converged Ethernet) on Ubuntu Server. Step-by-step persistent configuration for enterprise storage."
keywords: "NVMe-oF, NVMe over Fabrics, RoCE, RDMA, Ubuntu Server, nvmet, nvmetcli, storage configuration"
---

Complete setup for Ubuntu Server with persistent configuration across reboots. This guide covers exporting `/dev/nvme0n1`, `/dev/sdb`, and `/dev/sdc` over RDMA using interface `ens16` at `172.16.10.10:4420`.

## Configuration Summary

- **Server IP:** 172.16.10.10
- **Interface:** ens16
- **Transport:** RDMA (RoCE)
- **Port:** 4420
- **Exported Devices:** /dev/nvme0n1, /dev/sdb, /dev/sdc
- **Subsystem NQN:** nqn.2025-01.com.example:nvme-target

## Table of Contents

1. [Prerequisites and Package Installation](#1-prerequisites-and-package-installation)
2. [Kernel Modules Configuration](#2-kernel-modules-configuration)
3. [Network Configuration](#3-network-configuration)
4. [NVMe Target Configuration](#4-nvme-target-configuration-script)
5. [Systemd Service Setup](#5-systemd-service-setup)
6. [RoCE Optimization](#6-roce-optimization-settings)
7. [Verification and Testing](#7-verification-and-testing)
8. [Client Configuration](#8-client-configuration)
9. [Troubleshooting](#9-troubleshooting)

## 1. Prerequisites and Package Installation

Install all required packages for NVMe-oF and RoCE support:

```bash
# Update system
sudo apt update

# Install required packages
sudo apt install nvme-cli rdma-core infiniband-diags perftest
sudo apt install libibverbs1 ibverbs-utils nvmetcli
```

## 2. Kernel Modules Configuration

Configure kernel modules to load automatically on boot:

```bash
sudo tee /etc/modules-load.d/nvmet.conf <<EOF
# NVMe-oF Target modules
nvmet
nvmet-rdma

# RDMA modules
rdma_cm
ib_core
ib_uverbs
EOF

# Apply module configuration
sudo systemctl restart systemd-modules-load
```

### Verify Modules Loaded

```bash
# Check if modules are loaded
lsmod | grep nvmet
lsmod | grep rdma

# Load manually if needed
sudo modprobe nvmet
sudo modprobe nvmet-rdma
sudo modprobe rdma_cm
sudo modprobe ib_core
```

## 3. Network Configuration (ens16)

Configure the ens16 interface with static IP 172.16.10.10 using Netplan:

```bash
sudo tee /etc/netplan/50-rdma.yaml <<EOF
network:
  version: 2
  renderer: networkd
  ethernets:
    ens16:
      addresses:
        - 172.16.10.10/24
      mtu: 9000
      optional: true
EOF

# Apply network configuration
sudo netplan apply

# Verify interface
ip addr show ens16
```

**Note:** The MTU is set to 9000 (Jumbo frames) for better RDMA performance. Ensure your network infrastructure supports this.

## 4. NVMe Target Configuration Script

Create a script to configure the NVMe-oF target with three exported devices:

```bash
sudo tee /usr/local/bin/setup-nvmet.sh <<'EOF'
#!/bin/bash

SUBSYSTEM_NQN="nqn.2025-01.com.example:nvme-target"
RDMA_IP="172.16.10.10"
RDMA_PORT="4420"

# Wait for configfs to be available
sleep 2

# Create subsystem
mkdir -p /sys/kernel/config/nvmet/subsystems/${SUBSYSTEM_NQN}
echo 1 > /sys/kernel/config/nvmet/subsystems/${SUBSYSTEM_NQN}/attr_allow_any_host

# Create namespace 1 for /dev/nvme0n1
mkdir -p /sys/kernel/config/nvmet/subsystems/${SUBSYSTEM_NQN}/namespaces/1
echo /dev/nvme0n1 > /sys/kernel/config/nvmet/subsystems/${SUBSYSTEM_NQN}/namespaces/1/device_path
echo 1 > /sys/kernel/config/nvmet/subsystems/${SUBSYSTEM_NQN}/namespaces/1/enable

# Create namespace 2 for /dev/sdb
mkdir -p /sys/kernel/config/nvmet/subsystems/${SUBSYSTEM_NQN}/namespaces/2
echo /dev/sdb > /sys/kernel/config/nvmet/subsystems/${SUBSYSTEM_NQN}/namespaces/2/device_path
echo 1 > /sys/kernel/config/nvmet/subsystems/${SUBSYSTEM_NQN}/namespaces/2/enable

# Create namespace 3 for /dev/sdc
mkdir -p /sys/kernel/config/nvmet/subsystems/${SUBSYSTEM_NQN}/namespaces/3
echo /dev/sdc > /sys/kernel/config/nvmet/subsystems/${SUBSYSTEM_NQN}/namespaces/3/device_path
echo 1 > /sys/kernel/config/nvmet/subsystems/${SUBSYSTEM_NQN}/namespaces/3/enable

# Create port
mkdir -p /sys/kernel/config/nvmet/ports/1
echo rdma > /sys/kernel/config/nvmet/ports/1/addr_trtype
echo ipv4 > /sys/kernel/config/nvmet/ports/1/addr_adrfam
echo ${RDMA_IP} > /sys/kernel/config/nvmet/ports/1/addr_traddr
echo ${RDMA_PORT} > /sys/kernel/config/nvmet/ports/1/addr_trsvcid

# Link subsystem to port
ln -s /sys/kernel/config/nvmet/subsystems/${SUBSYSTEM_NQN} \
      /sys/kernel/config/nvmet/ports/1/subsystems/${SUBSYSTEM_NQN}

echo "NVMe-oF Target configured on ens16 (${RDMA_IP}:${RDMA_PORT})"
echo "Exported devices:"
echo "  Namespace 1: /dev/nvme0n1"
echo "  Namespace 2: /dev/sdb"
echo "  Namespace 3: /dev/sdc"
EOF

# Make script executable
sudo chmod +x /usr/local/bin/setup-nvmet.sh
```

### Create Cleanup Script

```bash
sudo tee /usr/local/bin/cleanup-nvmet.sh <<'EOF'
#!/bin/bash

SUBSYSTEM_NQN="nqn.2025-01.com.example:nvme-target"

# Remove subsystem link from port
rm -f /sys/kernel/config/nvmet/ports/1/subsystems/${SUBSYSTEM_NQN} 2>/dev/null

# Disable and remove namespaces
for ns in 1 2 3; do
    if [ -d "/sys/kernel/config/nvmet/subsystems/${SUBSYSTEM_NQN}/namespaces/${ns}" ]; then
        echo 0 > /sys/kernel/config/nvmet/subsystems/${SUBSYSTEM_NQN}/namespaces/${ns}/enable 2>/dev/null
        rmdir /sys/kernel/config/nvmet/subsystems/${SUBSYSTEM_NQN}/namespaces/${ns} 2>/dev/null
    fi
done

# Remove port
rmdir /sys/kernel/config/nvmet/ports/1 2>/dev/null

# Remove subsystem
rmdir /sys/kernel/config/nvmet/subsystems/${SUBSYSTEM_NQN} 2>/dev/null

echo "NVMe-oF Target cleaned up"
EOF

sudo chmod +x /usr/local/bin/cleanup-nvmet.sh
```

## 5. Systemd Service Setup

Create a systemd service to ensure the configuration persists across reboots:

```bash
sudo tee /etc/systemd/system/nvmet.service <<'EOF'
[Unit]
Description=NVMe-oF Target Configuration
After=network-online.target sys-kernel-config.mount systemd-networkd.service
Wants=network-online.target
Requires=sys-kernel-config.mount

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/bin/setup-nvmet.sh
ExecStop=/usr/local/bin/cleanup-nvmet.sh

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd daemon
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable nvmet.service

# Start service now
sudo systemctl start nvmet.service

# Check service status
sudo systemctl status nvmet.service
```

## 6. RoCE Optimization Settings

Apply system-level optimizations for RDMA performance:

```bash
sudo tee /etc/sysctl.d/99-rdma.conf <<EOF
# Increase socket buffer sizes for RDMA
net.core.rmem_max = 268435456
net.core.wmem_max = 268435456
net.ipv4.tcp_rmem = 4096 87380 134217728
net.ipv4.tcp_wmem = 4096 65536 134217728

# Enable TCP timestamps
net.ipv4.tcp_timestamps = 1

# Increase max connections
net.core.somaxconn = 4096
EOF

# Apply sysctl settings
sudo sysctl -p /etc/sysctl.d/99-rdma.conf
```

## 7. Verification and Testing

### Create Status Check Script

```bash
sudo tee /usr/local/bin/check-nvmet-status.sh <<'EOF'
#!/bin/bash

echo "=== NVMe-oF Target Status ==="
echo ""
echo "Interface ens16:"
ip addr show ens16 | grep inet
echo ""
echo "RDMA Devices:"
ibv_devices
echo ""
echo "Target Configuration:"
cat /sys/kernel/config/nvmet/ports/1/addr_traddr 2>/dev/null || echo "Not configured"
echo ""
echo "Exported Namespaces:"
for ns in 1 2 3; do
    if [ -f "/sys/kernel/config/nvmet/subsystems/nqn.2025-01.com.example:nvme-target/namespaces/$ns/device_path" ]; then
        device=$(cat /sys/kernel/config/nvmet/subsystems/nqn.2025-01.com.example:nvme-target/namespaces/$ns/device_path)
        enabled=$(cat /sys/kernel/config/nvmet/subsystems/nqn.2025-01.com.example:nvme-target/namespaces/$ns/enable)
        echo "  Namespace $ns: $device (enabled: $enabled)"
    fi
done
echo ""
echo "Service Status:"
systemctl is-active nvmet.service
EOF

sudo chmod +x /usr/local/bin/check-nvmet-status.sh
```

### Run Verification Commands

```bash
# Run status check
sudo /usr/local/bin/check-nvmet-status.sh

# Check interface
ip addr show ens16

# Verify RDMA devices
ibv_devices
rdma link show

# View kernel logs
sudo dmesg | grep -i nvmet
sudo dmesg | grep -i rdma
```

## 8. Client Configuration

Configure client machines to connect to the NVMe-oF target:

### Install NVMe CLI on Client

```bash
sudo apt update
sudo apt install nvme-cli rdma-core
```

### Discover Available Targets

```bash
# Discover targets on the network
sudo nvme discover -t rdma -a 172.16.10.10 -s 4420
```

### Connect to Target

```bash
# Connect to the NVMe-oF target
sudo nvme connect -t rdma -n nqn.2025-01.com.example:nvme-target -a 172.16.10.10 -s 4420

# Verify connection
sudo nvme list

# Check subsystem details
sudo nvme list-subsys
```

After connecting, you should see three NVMe namespaces appear on the client (e.g., `/dev/nvme1n1`, `/dev/nvme1n2`, `/dev/nvme1n3`) corresponding to the three exported devices from the target.

### Disconnect from Target

```bash
# Disconnect from specific subsystem
sudo nvme disconnect -n nqn.2025-01.com.example:nvme-target

# Or disconnect all
sudo nvme disconnect-all
```

## 9. Troubleshooting

### Modules Not Loading

```bash
# Check if modules exist
modinfo nvmet
modinfo nvmet-rdma

# Force load modules
sudo modprobe -v nvmet
sudo modprobe -v nvmet-rdma

# Check kernel logs
sudo dmesg | tail -50
```

### RDMA Devices Not Found

```bash
# Check if RDMA stack is running
sudo systemctl status rdma-core

# List RDMA devices
ibv_devices
rdma link show

# Verify NIC supports RoCE
lspci | grep -i ethernet
ethtool -i ens16
```

### Target Not Accessible from Client

```bash
# Check if port is listening
sudo ss -tulpn | grep 4420

# Verify firewall rules
sudo ufw status
sudo iptables -L -n

# Test network connectivity
ping 172.16.10.10
```

## Important Notes

- Ensure all devices (`/dev/nvme0n1`, `/dev/sdb`, `/dev/sdc`) exist before starting the service
- RoCE requires proper network configuration - verify MTU settings match across all devices
- Some NICs require firmware updates for RoCE support
- Check that your NIC supports RDMA/RoCE (most modern Mellanox, Broadcom, Intel cards do)

---

© 2025 Darren Soothill. All rights reserved.
