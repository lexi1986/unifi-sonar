#!/usr/bin/env bash
# UniFi Sonar in een nieuwe LXC-container op Proxmox VE. Draai dit op de Proxmox-host (als root):
#
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/lexi1986/unifi-sonar/main/scripts/proxmox-lxc.sh)"
#
# Maakt een kleine Debian-container (1 core, 512 MB, 4 GB, unprivileged, start mee op) en installeert
# daarin UniFi Sonar. Alle vragen hebben een standaardantwoord; Enter is genoeg.
# DRY_RUN=1 laat alleen zien wat er zou gebeuren.
set -euo pipefail

RAW="${RAW:-https://raw.githubusercontent.com/lexi1986/unifi-sonar/main}"
DRY="${DRY_RUN:-}"

say() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mFout:\033[0m %s\n' "$*" >&2; exit 1; }
run() { if [ -n "$DRY" ]; then echo "   [dry-run] $*"; else "$@"; fi; }
ask() {   # ask "vraag" "standaard"
  local a=""
  if { : </dev/tty; } 2>/dev/null; then read -r -p "$1 [$2]: " a </dev/tty 2>/dev/null || true; fi
  printf '%s' "${a:-$2}"
}

command -v pct >/dev/null && command -v pveam >/dev/null || die "dit script moet op een Proxmox VE-host draaien."
[ "$(id -u)" = 0 ] || die "draai dit als root."

echo
echo "  UniFi Sonar – installatie in een Proxmox-container"
echo

CTID=$(ask "Container-ID" "$(pvesh get /cluster/nextid)")
pct status "$CTID" >/dev/null 2>&1 && die "container $CTID bestaat al."
NAME=$(ask "Hostnaam" "unifi-sonar")
DEF_STORE=$(pvesm status -content rootdir 2>/dev/null | awk 'NR>1 && $3=="active"{print $1; exit}')
STORAGE=$(ask "Opslag voor de container" "${DEF_STORE:-local-lvm}")
BRIDGE=$(ask "Netwerkbrug" "vmbr0")
NET=$(ask "IP-adres (dhcp, of vast zoals 192.168.1.50/24)" "dhcp")
NETOPT="name=eth0,bridge=$BRIDGE,ip=$NET"
if [ "$NET" != "dhcp" ]; then
  [[ "$NET" == */* ]] || die "geef een vast adres op met netmasker, bijv. 192.168.1.50/24"
  GW=$(ask "Gateway" "$(echo "${NET%/*}" | awk -F. '{print $1"."$2"."$3".1"}')")
  NETOPT="$NETOPT,gw=$GW"
fi
PORT=$(ask "Poort van het dashboard" "80")

say "Debian-template zoeken"
ARCH=$(dpkg --print-architecture 2>/dev/null || echo amd64)
TSTORE=$(pvesm status -content vztmpl 2>/dev/null | awk 'NR>1 && $3=="active"{print $1; exit}')
TSTORE=${TSTORE:-local}
pick() { grep -E "^debian-(13|12)-standard_.*_${ARCH}\.tar\.(zst|gz|xz)$" | sort -V | awk -F_ '{v=substr($1,8,2)} {print v" "$0}' | sort -k1,1n -k2V | tail -1 | cut -d' ' -f2; }
# eerst een template dat al gedownload is, anders de nieuwste uit de lijst
TEMPLATE=$(pveam list "$TSTORE" 2>/dev/null | awk 'NR>1{print $1}' | sed 's|.*/||' | pick)
if [ -z "$TEMPLATE" ]; then
  run pveam update >/dev/null || true
  TEMPLATE=$(pveam available --section system 2>/dev/null | awk '{print $2}' | pick)
fi
[ -n "$TEMPLATE" ] || die "geen Debian-template voor $ARCH gevonden (pveam available)."
say "Template: $TEMPLATE"
if ! pveam list "$TSTORE" 2>/dev/null | grep -q "$TEMPLATE"; then
  say "Template $TEMPLATE downloaden"
  run pveam download "$TSTORE" "$TEMPLATE" >/dev/null
fi

say "Container $CTID aanmaken"
run pct create "$CTID" "$TSTORE:vztmpl/$TEMPLATE" \
  --hostname "$NAME" --description "UniFi Sonar – https://github.com/lexi1986/unifi-sonar" \
  --cores 1 --memory 512 --swap 512 --rootfs "$STORAGE:4" --net0 "$NETOPT" \
  --unprivileged 1 --features nesting=1 --onboot 1 --tags "unifi-sonar" --timezone host
run pct start "$CTID"

if [ -z "$DRY" ]; then
  say "Wachten op netwerk in de container"
  ok=""
  for _ in $(seq 1 30); do
    if pct exec "$CTID" -- getent hosts deb.debian.org >/dev/null 2>&1; then ok=1; break; fi
    sleep 2
  done
  [ -n "$ok" ] || die "de container krijgt geen internet. Controleer IP/gateway/DNS en draai daarna in de container: curl -fsSL $RAW/scripts/install.sh | bash"
fi

say "UniFi Sonar installeren in de container"
TMP=$(mktemp)
run curl -fsSL "$RAW/scripts/install.sh" -o "$TMP"
run pct push "$CTID" "$TMP" /root/install-unifi-sonar.sh
run pct exec "$CTID" -- env PORT="$PORT" bash /root/install-unifi-sonar.sh
rm -f "$TMP"

if [ -z "$DRY" ]; then
  IP=$(pct exec "$CTID" -- hostname -I | awk '{print $1}')
  echo
  say "Klaar! Open http://$IP$([ "$PORT" = 80 ] || echo ":$PORT") en volg de setup-wizard."
  echo "    Bijwerken later: pct exec $CTID -- bash /root/install-unifi-sonar.sh"
fi
