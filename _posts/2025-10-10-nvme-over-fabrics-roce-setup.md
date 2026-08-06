---
layout: post
title: "NVMe-oF with RoCE Configuration Guide - Ubuntu Server"
date: 2025-10-10
last_modified_at: 2026-08-06
categories: [storage, nvme, linux]
tags: [nvme-of, roce, rdma, ubuntu, storage-configuration, linux]
author: Darren Soothill
description: "A lab-focused guide to configuring a persistent Linux NVMe over Fabrics target with RoCE, stable device identities, host access control and explicit network prerequisites."
keywords: "NVMe-oF, NVMe over Fabrics, RoCE, RDMA, Ubuntu Server, nvmet, nvmetcli, storage configuration"
---

This guide builds a persistent Linux kernel NVMe-oF target for a controlled lab. The example uses interface `ens16` at `172.16.10.10:4420`, stable `/dev/disk/by-id/...` device paths and an explicit client host NQN.

> **Data-safety boundary:** an exported block device must not be mounted, used as swap, held by LVM/RAID or accessed by another application on the target. Concurrent local and remote access can corrupt data. Replace every sample identifier, validate the resolved devices and test with disposable storage before adapting this configuration.

## Configuration Summary

- **Server IP:** 172.16.10.10
- **Interface:** ens16
- **Transport:** RDMA (RoCE)
- **Port:** 4420
- **Exported devices:** three site-specific `/dev/disk/by-id/...` paths
- **Subsystem NQN:** nqn.2025-01.com.example:nvme-target
- **Authorised host NQN:** value read from `/etc/nvme/hostnqn` on the client

The page generates its contents list from the headings below, so section links remain in step with the article.

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

**Note:** use MTU 9000 only when the client, target and every switch port on the path have been configured and tested for it. A mismatched MTU causes failures; jumbo frames are not a substitute for correct RoCE fabric design.

## 4. NVMe Target Configuration Script

First read the client's host NQN:

```bash
cat /etc/nvme/hostnqn
```

Then create the target script. Replace all three device IDs and the client host NQN before running it:

```bash
sudo tee /usr/local/bin/setup-nvmet.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

SUBSYSTEM_NQN="nqn.2025-01.com.example:nvme-target"
HOST_NQN="nqn.2014-08.org.nvmexpress:uuid:REPLACE-WITH-CLIENT-HOST-NQN"
RDMA_IP="172.16.10.10"
RDMA_PORT="4420"
PORT_ID="1"
DEVICES=(
  "/dev/disk/by-id/nvme-REPLACE_WITH_DEVICE_1"
  "/dev/disk/by-id/REPLACE_WITH_DEVICE_2"
  "/dev/disk/by-id/REPLACE_WITH_DEVICE_3"
)

CONFIGFS="/sys/kernel/config/nvmet"
SUBSYSTEM_DIR="${CONFIGFS}/subsystems/${SUBSYSTEM_NQN}"
PORT_DIR="${CONFIGFS}/ports/${PORT_ID}"
HOST_DIR="${CONFIGFS}/hosts/${HOST_NQN}"

[[ -d "${CONFIGFS}" ]] || { echo "nvmet configfs is not mounted" >&2; exit 1; }
[[ ! -e "${SUBSYSTEM_DIR}" && ! -e "${PORT_DIR}" ]] || {
  echo "Target configuration already exists; inspect or clean it up first" >&2
  exit 1
}

for device in "${DEVICES[@]}"; do
  [[ -L "${device}" ]] || { echo "Stable device link not found: ${device}" >&2; exit 1; }
  resolved="$(readlink -f "${device}")"
  [[ -b "${resolved}" ]] || { echo "Not a block device: ${device}" >&2; exit 1; }

  while read -r node; do
    if findmnt -rn -S "${node}" >/dev/null; then
      echo "Refusing mounted device or child: ${node}" >&2
      exit 1
    fi
    if swapon --noheadings --raw --output NAME | grep -Fxq "${node}"; then
      echo "Refusing active swap device or child: ${node}" >&2
      exit 1
    fi
    kernel_name="$(lsblk -ndo KNAME "${node}")"
    if find "/sys/class/block/${kernel_name}/holders" -mindepth 1 -maxdepth 1 -print -quit | grep -q .; then
      echo "Refusing device held by another block layer: ${node}" >&2
      exit 1
    fi
  done < <(lsblk -nrpo NAME "${resolved}")
done

# Create subsystem
mkdir "${SUBSYSTEM_DIR}"
echo 0 > "${SUBSYSTEM_DIR}/attr_allow_any_host"

# Authorise one client host NQN
mkdir "${HOST_DIR}"
ln -s "${HOST_DIR}" "${SUBSYSTEM_DIR}/allowed_hosts/${HOST_NQN}"

# Create one namespace per validated stable device path
for index in "${!DEVICES[@]}"; do
  nsid="$((index + 1))"
  namespace_dir="${SUBSYSTEM_DIR}/namespaces/${nsid}"
  mkdir "${namespace_dir}"
  echo "${DEVICES[$index]}" > "${namespace_dir}/device_path"
  echo 1 > "${namespace_dir}/enable"
done

# Create port
mkdir "${PORT_DIR}"
echo rdma > "${PORT_DIR}/addr_trtype"
echo ipv4 > "${PORT_DIR}/addr_adrfam"
echo "${RDMA_IP}" > "${PORT_DIR}/addr_traddr"
echo "${RDMA_PORT}" > "${PORT_DIR}/addr_trsvcid"

# Link subsystem to port
ln -s "${SUBSYSTEM_DIR}" "${PORT_DIR}/subsystems/${SUBSYSTEM_NQN}"

echo "NVMe-oF Target configured on ens16 (${RDMA_IP}:${RDMA_PORT})"
printf 'Authorised host: %s\n' "${HOST_NQN}"
printf 'Exported device: %s\n' "${DEVICES[@]}"
EOF

# Make script executable
sudo chmod +x /usr/local/bin/setup-nvmet.sh
```

### Create Cleanup Script

```bash
sudo tee /usr/local/bin/cleanup-nvmet.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

SUBSYSTEM_NQN="nqn.2025-01.com.example:nvme-target"
HOST_NQN="nqn.2014-08.org.nvmexpress:uuid:REPLACE-WITH-CLIENT-HOST-NQN"
PORT_ID="1"
CONFIGFS="/sys/kernel/config/nvmet"
SUBSYSTEM_DIR="${CONFIGFS}/subsystems/${SUBSYSTEM_NQN}"
PORT_DIR="${CONFIGFS}/ports/${PORT_ID}"
HOST_DIR="${CONFIGFS}/hosts/${HOST_NQN}"

# Remove subsystem link from port
rm -f "${PORT_DIR}/subsystems/${SUBSYSTEM_NQN}"

# Disable and remove namespaces
for ns in 1 2 3; do
    namespace_dir="${SUBSYSTEM_DIR}/namespaces/${ns}"
    if [[ -d "${namespace_dir}" ]]; then
        echo 0 > "${namespace_dir}/enable"
        rmdir "${namespace_dir}"
    fi
done

# Remove host access link and host object
rm -f "${SUBSYSTEM_DIR}/allowed_hosts/${HOST_NQN}"

# Remove port
if [[ -d "${PORT_DIR}" ]]; then
  rmdir "${PORT_DIR}"
fi

# Remove subsystem
if [[ -d "${SUBSYSTEM_DIR}" ]]; then
  rmdir "${SUBSYSTEM_DIR}"
fi

if [[ -d "${HOST_DIR}" ]]; then
  rmdir "${HOST_DIR}"
fi

echo "NVMe-oF Target cleaned up"
EOF

sudo chmod +x /usr/local/bin/cleanup-nvmet.sh
```

Use the same subsystem and host NQNs in both scripts. If setup stops after creating only part of the configfs tree, inspect it and run the cleanup script before retrying; the setup script deliberately refuses to overwrite pre-existing state.

## 5. Systemd Service Setup

Create a systemd service to ensure the configuration persists across reboots:

```bash
sudo tee /etc/systemd/system/nvmet.service <<'EOF'
[Unit]
Description=NVMe-oF Target Configuration
After=network-online.target sys-kernel-config.mount
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

## 6. RoCE Network Prerequisites

The socket-buffer and TCP sysctls sometimes copied into RoCE guides do not tune the NVMe/RDMA data path. RoCE performance and reliability depend on the NIC, driver and complete Ethernet fabric. Record the negotiated link, MTU and RDMA state first:

```bash
ip -details link show ens16
ethtool ens16
ethtool -i ens16
rdma link show
ibv_devinfo
```

For a converged Ethernet deployment, design and verify PFC/ECN, queue mapping, VLAN isolation and congestion behaviour across both hosts and every switch hop. Apply vendor-specific settings only after confirming the exact adapter, firmware, driver and switch configuration. Benchmark before and after each change and keep a recovery path.

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
# rdma-core is a package; inspect devices, links, driver and kernel messages
ibv_devices
rdma link show
ethtool -i ens16
sudo journalctl -k -b | grep -Ei 'rdma|roce|infiniband'
```

The presence of an Ethernet adapter or the `rdma-core` package does not prove RoCE capability. Confirm the exact adapter, firmware and driver support in the vendor's compatibility documentation.

### Target Not Accessible from Client

```bash
# Inspect the kernel target configuration
sudo find /sys/kernel/config/nvmet -maxdepth 5 -type f -print

# Verify firewall rules
sudo ufw status

# Test network connectivity
ping 172.16.10.10
```

`ss` reports TCP and UDP sockets; it is not an authoritative check for an RDMA CM listener. Validate the configfs listener and run `nvme discover` from the authorised client.

## Important Notes

- Resolve and record every `/dev/disk/by-id/...` link before starting; do not use enumeration-dependent names such as `/dev/sdb` in a persistent target
- Keep exported devices unmounted and outside swap, LVM, RAID and every other local storage consumer
- Keep `attr_allow_any_host` disabled and add only the required host NQNs
- RoCE requires an end-to-end network design; verify MTU, PFC/ECN and congestion behaviour across the complete path
- Some NICs require firmware updates for RoCE support
- Confirm support against the exact adapter model, firmware and driver rather than inferring it from the vendor name

This configuration demonstrates a single-path lab target. A production design also needs an availability model, multipathing and failure testing, monitoring, change control, access policy and a documented recovery procedure.

## Additional Resources

- [Linux NVMe subsystem documentation](https://docs.kernel.org/nvme/index.html)
- [Red Hat guidance on RoCE network design](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_distributed_workloads/configuring-roce-networking-for-distributed-llm-deployments_distributed-llm-roce)
- [NVMe specifications](https://nvmexpress.org/specifications/)
