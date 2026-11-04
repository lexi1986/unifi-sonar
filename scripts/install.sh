#!/usr/bin/env bash
# UniFi Sonar installeren of bijwerken op Debian/Ubuntu (ook prima in een Proxmox-LXC).
#
#   curl -fsSL https://raw.githubusercontent.com/lexi1986/unifi-sonar/main/scripts/install.sh | sudo bash
#
# Opnieuw draaien = bijwerken naar de nieuwste versie; je instellingen en historie blijven staan.
# Variabelen: PORT (standaard 80), BRANCH (main), REPO, SOURCE_DIR (lokale code i.p.v. git).
set -euo pipefail

REPO="${REPO:-https://github.com/lexi1986/unifi-sonar.git}"
BRANCH="${BRANCH:-main}"
PORT="${PORT:-80}"
SOURCE_DIR="${SOURCE_DIR:-}"
APP=/opt/unifi-sonar
DATA=/var/lib/unifi-sonar
SVC=unifi-sonar
SVC_USER=unifi-sonar

say() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mFout:\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" = 0 ] || die "draai dit als root (bijv. met sudo)."
command -v apt-get >/dev/null || die "alleen Debian en Ubuntu worden ondersteund."
export DEBIAN_FRONTEND=noninteractive LC_ALL=C.UTF-8 LANG=C.UTF-8

say "Benodigde pakketten installeren"
apt-get update -qq
apt-get install -y -qq python3 python3-venv git ca-certificates iproute2 >/dev/null
python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' || die "Python 3.10 of nieuwer is nodig."

# Poort vrij? (onze eigen service mag hem al gebruiken)
if ss -ltnH "sport = :$PORT" 2>/dev/null | grep -q . && ! systemctl is-active -q "$SVC" 2>/dev/null; then
  die "poort $PORT is al in gebruik. Kies een andere, bijv.: PORT=8080 bash install.sh"
fi

say "Code ophalen"
if [ -n "$SOURCE_DIR" ]; then
  if [ "$(cd "$SOURCE_DIR" && pwd)" != "$APP" ]; then
    mkdir -p "$APP" && cp -a "$SOURCE_DIR"/. "$APP"/
  fi
elif [ -d "$APP/.git" ]; then
  git -C "$APP" fetch -q --depth 1 origin "$BRANCH"
  git -C "$APP" reset -q --hard FETCH_HEAD
else
  rm -rf "$APP"
  git clone -q --depth 1 --branch "$BRANCH" "$REPO" "$APP"
fi

say "Gebruiker en datamap"
id "$SVC_USER" >/dev/null 2>&1 || useradd --system --home "$DATA" --shell /usr/sbin/nologin "$SVC_USER"
install -d -m 700 -o "$SVC_USER" -g "$SVC_USER" "$DATA"

say "Python-omgeving"
[ -x "$APP/.venv/bin/python" ] || python3 -m venv "$APP/.venv"
"$APP/.venv/bin/pip" install -q --disable-pip-version-check --upgrade -r "$APP/requirements.txt"

say "Service $SVC (poort $PORT)"
cat > "/etc/systemd/system/$SVC.service" <<EOF
[Unit]
Description=UniFi Sonar (netwerkdashboard)
After=network-online.target
Wants=network-online.target

[Service]
User=$SVC_USER
WorkingDirectory=$APP
Environment=DATA_DIR=$DATA
Environment=NO_DOTENV=1
ExecStart=$APP/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port $PORT --no-access-log
AmbientCapabilities=CAP_NET_BIND_SERVICE
Restart=always
RestartSec=5
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=$DATA

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable -q "$SVC"
systemctl restart "$SVC"

for _ in $(seq 1 20); do
  if python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:$PORT/api/status', timeout=2)" 2>/dev/null; then
    IP=$(hostname -I 2>/dev/null | awk '{print $1}')
    URL="http://${IP:-<ip-van-deze-machine>}$([ "$PORT" = 80 ] || echo ":$PORT")"
    say "Klaar! Open $URL in je browser; bij de eerste keer start de setup-wizard."
    exit 0
  fi
  sleep 1
done
die "de service start niet. Bekijk de logs met: journalctl -u $SVC -n 50"
