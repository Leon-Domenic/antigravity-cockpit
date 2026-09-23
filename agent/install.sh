#!/bin/bash
# ==============================================================================
# Antigravity Cockpit Universal Multi-Engine Node Installer
# Usage: curl -sSL http://<COCKPIT_HOST>/install.sh | bash -s -- --engine <engine>
# Supported Engines: antigravity, codex, hermes, openclaw, ceo, custom
# ==============================================================================
set -e

COCKPIT_HOST="${COCKPIT_HOST:-192.168.178.168:3000}"
COCKPIT_HOST="${COCKPIT_HOST#http://}"
COCKPIT_HOST="${COCKPIT_HOST#https://}"
COCKPIT_HOST="${COCKPIT_HOST%/}"
ENGINE="antigravity"

# Parse CLI arguments
while [ $# -gt 0 ]; do
    case "$1" in
        --engine|-e)
            ENGINE="$2"
            shift 2
            ;;
        --engine=*)
            ENGINE="${1#*=}"
            shift
            ;;
        --cockpit)
            COCKPIT_HOST="$2"
            shift 2
            ;;
        --cockpit=*)
            COCKPIT_HOST="${1#*=}"
            shift
            ;;
        *)
            shift
            ;;
    esac
done

COCKPIT_HOST="${COCKPIT_HOST#http://}"
COCKPIT_HOST="${COCKPIT_HOST#https://}"
COCKPIT_HOST="${COCKPIT_HOST%/}"

ENGINE_LOWER="$(echo "$ENGINE" | tr '[:upper:]' '[:lower:]')"

echo "===================================================================="
echo ">>> Antigravity Cockpit Universal Node Installer"
echo ">>> Target Engine : ${ENGINE_LOWER}"
echo ">>> Cockpit Host  : http://${COCKPIT_HOST}"
echo "===================================================================="

# Check root privileges
if [ "$(id -u)" -ne 0 ]; then
    echo "❌ Error: This installer must be run as root (use sudo)."
    exit 1
fi

# Ensure curl/wget present in fresh minimal container
if ! command -v curl &>/dev/null && ! command -v wget &>/dev/null; then
    echo ">>> Installing curl and wget..."
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq && apt-get install -y -qq curl wget ca-certificates >/dev/null 2>&1 || true
fi

TMP_DIR="$(mktemp -d /tmp/cockpit-installer-XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

# Download common helper library
wget -q -O "${TMP_DIR}/common.sh" "http://${COCKPIT_HOST}/packages/installers/common.sh" || true
if [ ! -f "${TMP_DIR}/common.sh" ]; then
    # Fallback to embedded common.sh if direct package fetch fails
    cat << 'EOF' > "${TMP_DIR}/common.sh"
detect_virt() {
    if command -v systemd-detect-virt &>/dev/null; then
        systemd-detect-virt 2>/dev/null || echo "unknown"
    else
        echo "unknown"
    fi
}
check_system_resources() { :; }
install_core_dependencies() {
    apt-get update -qq && apt-get install -y -qq curl wget git python3 python3-flask python3-requests python3-pip
}
deploy_agent_bridge() {
    wget -q -O /usr/local/bin/agent_bridge.py "http://$1/packages/agent_bridge.py" || true
    chmod +x /usr/local/bin/agent_bridge.py
    systemctl daemon-reload && systemctl enable --now agent-bridge.service || true
}
install_skills_library() { :; }
EOF
fi

chmod +x "${TMP_DIR}/common.sh"

# Route to specialized installer
case "${ENGINE_LOWER}" in
    hermes)
        echo ">>> Downloading Hermes Agent installer package..."
        wget -q -O "${TMP_DIR}/install_hermes.sh" "http://${COCKPIT_HOST}/packages/installers/install_hermes.sh"
        chmod +x "${TMP_DIR}/install_hermes.sh"
        COCKPIT_HOST="${COCKPIT_HOST}" bash "${TMP_DIR}/install_hermes.sh"
        ;;
    openclaw)
        echo ">>> Downloading Open Claw Crawler installer package..."
        wget -q -O "${TMP_DIR}/install_openclaw.sh" "http://${COCKPIT_HOST}/packages/installers/install_openclaw.sh"
        chmod +x "${TMP_DIR}/install_openclaw.sh"
        COCKPIT_HOST="${COCKPIT_HOST}" bash "${TMP_DIR}/install_openclaw.sh"
        ;;
    codex)
        echo ">>> Downloading Codex Agent installer package..."
        wget -q -O "${TMP_DIR}/install_codex.sh" "http://${COCKPIT_HOST}/packages/installers/install_codex.sh"
        chmod +x "${TMP_DIR}/install_codex.sh"
        COCKPIT_HOST="${COCKPIT_HOST}" bash "${TMP_DIR}/install_codex.sh"
        ;;
    ceo)
        echo ">>> Downloading CEO Executive Node installer package..."
        wget -q -O "${TMP_DIR}/install_ceo.sh" "http://${COCKPIT_HOST}/packages/installers/install_ceo.sh"
        chmod +x "${TMP_DIR}/install_ceo.sh"
        COCKPIT_HOST="${COCKPIT_HOST}" bash "${TMP_DIR}/install_ceo.sh"
        ;;
    antigravity|*)
        echo ">>> Downloading Antigravity Agent installer package..."
        wget -q -O "${TMP_DIR}/install_antigravity.sh" "http://${COCKPIT_HOST}/packages/installers/install_antigravity.sh"
        chmod +x "${TMP_DIR}/install_antigravity.sh"
        COCKPIT_HOST="${COCKPIT_HOST}" bash "${TMP_DIR}/install_antigravity.sh"
        ;;
esac
