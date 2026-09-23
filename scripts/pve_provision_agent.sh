#!/bin/bash
# ==============================================================================
# Proxmox VE Automated Agent Provisioner
# Runs on Proxmox VE Host (192.168.178.105)
# Automatically selects LXC Container vs KVM QEMU VM based on Engine Requirements:
#   - antigravity : LXC (4 Cores, 4GB RAM, 20GB Disk)
#   - codex       : LXC (4 Cores, 4GB RAM, 30GB Disk)
#   - hermes      : KVM VM (q35, ovmf, cpu host, 8 Cores, 16GB RAM, 60GB Disk)
#   - openclaw    : KVM VM (4 Cores, 8GB RAM, 50GB Disk, Full Chromium Sandbox)
#   - ceo         : LXC (2 Cores, 2GB RAM, 15GB Disk)
# ==============================================================================
set -e

COCKPIT_HOST="${COCKPIT_HOST:-192.168.178.168:3000}"
STORAGE="${STORAGE:-ssd-storage}"
BRIDGE="${BRIDGE:-vmbr0}"
ISO_STORAGE="${ISO_STORAGE:-local}"

ENGINE="antigravity"
VMID=""
NAME=""
FORCE_TYPE=""

while [ $# -gt 0 ]; do
    case "$1" in
        --engine|-e) ENGINE="$2"; shift 2 ;;
        --vmid|-v)   VMID="$2"; shift 2 ;;
        --name|-n)   NAME="$2"; shift 2 ;;
        --type|-t)   FORCE_TYPE="$2"; shift 2 ;; # "lxc" or "vm"
        --cockpit)   COCKPIT_HOST="$2"; shift 2 ;;
        *) shift ;;
    esac
done

ENGINE_LOWER="$(echo "$ENGINE" | tr '[:upper:]' '[:lower:]')"

if [ -z "$VMID" ]; then
    VMID=$(pvesh get /cluster/nextid)
fi

if [ -z "$NAME" ]; then
    NAME="agy-${ENGINE_LOWER}-${VMID}"
fi

echo "===================================================================="
echo ">>> Proxmox Agent Provisioning Engine"
echo ">>> Node Name     : ${NAME}"
echo ">>> Target VMID   : ${VMID}"
echo ">>> Agent Engine  : ${ENGINE_LOWER}"
echo ">>> Cockpit Host  : ${COCKPIT_HOST}"
echo "===================================================================="

# Determine Virtualization Type based on engine requirements
VIRT_TYPE="lxc"
if [ "$ENGINE_LOWER" = "hermes" ] || [ "$ENGINE_LOWER" = "openclaw" ]; then
    VIRT_TYPE="qemu"
fi

if [ -n "$FORCE_TYPE" ]; then
    VIRT_TYPE="$FORCE_TYPE"
fi

echo ">>> Selected Virtualization Architecture: ${VIRT_TYPE^^}"

if [ "$VIRT_TYPE" = "qemu" ] || [ "$VIRT_TYPE" = "vm" ]; then
    echo ">>> Provisioning KVM QEMU Virtual Machine (Full Hardware Virtualization)..."
    
    # 1. Ensure Ubuntu 22.04 cloud-init image is available
    IMG_DIR="/var/lib/vz/template/iso"
    IMG_FILE="${IMG_DIR}/jammy-server-cloudimg-amd64.img"
    mkdir -p "${IMG_DIR}"
    if [ ! -f "${IMG_FILE}" ]; then
        echo "    Downloading Ubuntu 22.04 Cloud-Init Image..."
        wget -q --show-progress -O "${IMG_FILE}" "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"
    fi

    # Hardware Specs by Engine
    MEM="8192"
    CORES="4"
    DISK_SIZE="50G"
    if [ "$ENGINE_LOWER" = "hermes" ]; then
        MEM="16384"
        CORES="8"
        DISK_SIZE="60G"
    fi

    echo "    Allocating: ${CORES} vCPUs (host), ${MEM} MB RAM, ${DISK_SIZE} Disk"

    # 2. Create VM
    qm create "${VMID}" \
        --name "${NAME}" \
        --memory "${MEM}" \
        --cores "${CORES}" \
        --cpu host \
        --machine q35 \
        --bios ovmf \
        --agent enabled=1 \
        --net0 "virtio,bridge=${BRIDGE}"

    # 3. Add EFI Disk for UEFI boot
    qm set "${VMID}" --efidisk0 "${STORAGE}:0,efitype=4m,pre-enrolled-keys=1"

    # 4. Import Cloud Image
    qm importdisk "${VMID}" "${IMG_FILE}" "${STORAGE}"
    IMPORTED_VOL=$(qm config "${VMID}" | grep -o "unused[0-9]*: ${STORAGE}:[a-zA-Z0-9_-]*" | head -n1 | awk '{print $2}')
    if [ -z "$IMPORTED_VOL" ]; then
        IMPORTED_VOL="${STORAGE}:vm-${VMID}-disk-1"
    fi

    # 5. Attach Disk and Cloud-Init
    qm set "${VMID}" --scsihw virtio-scsi-single --scsi0 "${IMPORTED_VOL},discard=on,ssd=1"
    qm set "${VMID}" --ide2 "${STORAGE}:cloudinit"
    qm set "${VMID}" --boot order=scsi0
    qm set "${VMID}" --serial0 socket --vga serial0
    qm set "${VMID}" --ciuser ubuntu
    qm set "${VMID}" --ipconfig0 ip=dhcp
    qm resize "${VMID}" scsi0 "${DISK_SIZE}"

    # Copy SSH keys
    if [ -f /root/.ssh/authorized_keys ]; then
        qm set "${VMID}" --sshkey /root/.ssh/authorized_keys
    fi

    echo "    Starting VM ${VMID}..."
    qm start "${VMID}"
    echo "✅ KVM QEMU VM ${VMID} (${NAME}) provisioned and running!"
    echo "    Once booted, log into the VM and run:"
    echo "    curl -sSL http://${COCKPIT_HOST}/install.sh | bash -s -- --engine ${ENGINE_LOWER}"

else
    echo ">>> Provisioning Proxmox LXC Container (Lightweight Isolation)..."

    MEM="4096"
    CORES="4"
    DISK_SIZE="20G"
    if [ "$ENGINE_LOWER" = "ceo" ]; then
        MEM="2048"
        CORES="2"
        DISK_SIZE="15G"
    elif [ "$ENGINE_LOWER" = "codex" ]; then
        DISK_SIZE="30G"
    fi

    # Ensure Ubuntu template exists
    TEMPLATE="/var/lib/vz/template/cache/ubuntu-22.04-standard_22.04-1_amd64.tar.zst"
    if [ ! -f "$TEMPLATE" ]; then
        TEMPLATE="/var/lib/vz/template/cache/ubuntu-24.04-standard_24.04-2_amd64.tar.zst"
    fi

    echo "    Allocating: ${CORES} Cores, ${MEM} MB RAM, ${DISK_SIZE} Disk"

    pct create "${VMID}" "${TEMPLATE}" \
        --hostname "${NAME}" \
        --cores "${CORES}" \
        --memory "${MEM}" \
        --swap 1024 \
        --rootfs "${STORAGE}:${DISK_SIZE}" \
        --net0 "name=eth0,bridge=${BRIDGE},ip=dhcp,type=veth" \
        --features "nesting=1,keyctl=1" \
        --unprivileged 0 \
        --start 1

    echo "    LXC container started. Executing automated installer..."
    sleep 4
    pct exec "${VMID}" -- bash -c "curl -sSL http://${COCKPIT_HOST}/install.sh | bash -s -- --engine ${ENGINE_LOWER}" || true
    echo "✅ LXC Container ${VMID} (${NAME}) provisioned and bootstrapped!"
fi

echo "===================================================================="
echo ">>> Register this node in Cockpit with VMID ${VMID} and its IP address."
echo "===================================================================="
