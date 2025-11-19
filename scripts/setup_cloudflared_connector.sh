#!/usr/bin/env bash
# Automates cloudflared installation and tunnel connector bootstrap on Debian/Ubuntu (apt) or RHEL/Oracle (dnf).
set -euo pipefail

TOKEN="${1:-}"  # Optional argument; fallback to CLOUDFLARE_TUNNEL_TOKEN env if empty
if [[ -z "$TOKEN" && -n "${CLOUDFLARE_TUNNEL_TOKEN:-}" ]]; then
  TOKEN="$CLOUDFLARE_TUNNEL_TOKEN"
fi

install_with_apt() {
  echo "[cloudflared] Installing via apt..."
  sudo mkdir -p --mode=0755 /usr/share/keyrings
  curl -fsSL https://pkg.cloudflare.com/cloudflare-public-v2.gpg | sudo tee /usr/share/keyrings/cloudflare-public-v2.gpg >/dev/null
  echo 'deb [signed-by=/usr/share/keyrings/cloudflare-public-v2.gpg] https://pkg.cloudflare.com/cloudflared any main' | \
    sudo tee /etc/apt/sources.list.d/cloudflared.list >/dev/null
  sudo apt-get update
  sudo apt-get install -y cloudflared
}

install_with_dnf() {
  echo "[cloudflared] Installing via dnf..."
  sudo tee /etc/yum.repos.d/cloudflared.repo >/dev/null <<'EOF'
[cloudflared]
name=cloudflared
baseurl=https://pkg.cloudflare.com/cloudflared/rpm
enabled=1
gpgcheck=1
gpgkey=https://pkg.cloudflare.com/cloudflare-main.gpg
EOF
  sudo dnf install -y cloudflared
}

if command -v apt-get >/dev/null 2>&1; then
  install_with_apt
elif command -v dnf >/dev/null 2>&1; then
  install_with_dnf
else
  echo "Unsupported package manager. Install cloudflared manually." >&2
  exit 1
fi

cloudflared --version

if [[ -n "$TOKEN" ]]; then
  echo "[cloudflared] Installing connector service..."
  sudo cloudflared service install "$TOKEN"
else
  echo "No tunnel token provided. Run: sudo cloudflared service install <TOKEN>"
fi
