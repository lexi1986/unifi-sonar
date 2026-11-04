#!/usr/bin/env bash
# Voor ontwikkelaars: zet je lokale (nog niet gepushte) code in een bestaande Proxmox-LXC en herstart.
# Instellingen in scripts/local.env (staat niet in git), bijvoorbeeld:
#   CTID=120
#   PVE=proxmox        # SSH-host uit ~/.ssh/config
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[ -f "$ROOT/scripts/local.env" ] && . "$ROOT/scripts/local.env"
: "${CTID:?zet CTID in scripts/local.env}"
: "${PVE:?zet PVE (SSH-host van de Proxmox-server) in scripts/local.env}"
# Eén gedeelde SSH-verbinding: sneller, en voorkomt dat een IPS het als SSH-scan ziet.
SSHOPTS=(-o ControlMaster=auto -o "ControlPath=$HOME/.ssh/cm-%r@%h:%p" -o ControlPersist=120 -o ConnectTimeout=15)
TAR="$(mktemp -t unifi-sonar).tgz"

cd "$ROOT"
COPYFILE_DISABLE=1 tar --no-xattrs -czf "$TAR" --exclude='__pycache__' app web scripts requirements.txt
scp -q "${SSHOPTS[@]}" "$TAR" "$PVE:/tmp/unifi-sonar.tgz"
rm -f "$TAR"
ssh "${SSHOPTS[@]}" "$PVE" "pct push $CTID /tmp/unifi-sonar.tgz /tmp/unifi-sonar.tgz && rm /tmp/unifi-sonar.tgz && \
  pct exec $CTID -- env LC_ALL=C.UTF-8 bash -c 'mkdir -p /opt/unifi-sonar && cd /opt/unifi-sonar && \
    rm -rf app web scripts && tar xzf /tmp/unifi-sonar.tgz && rm /tmp/unifi-sonar.tgz && \
    SOURCE_DIR=/opt/unifi-sonar bash scripts/install.sh'"
