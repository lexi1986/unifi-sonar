#!/usr/bin/env bash
# UniFi Sonar bijwerken naar de nieuwste release op GitHub. Je instellingen en historie blijven staan.
# Wordt bij installeren neergezet als `unifi-sonar-update`, en in een container ook als `update`.
#
#   update            bijwerken als er een nieuwe versie is
#   update --check    alleen kijken of er een update is
#   update --force    ook opnieuw installeren als je al de nieuwste versie hebt
set -euo pipefail

# Alles zit in main(): bash leest het hele script vóór het start, zodat het bijwerken van dit
# bestand tijdens het draaien geen kwaad kan.
main() {
  local APP=/opt/unifi-sonar DATA=/var/lib/unifi-sonar mode="${1:-}"
  say() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
  die() { printf '\033[1;31mFout:\033[0m %s\n' "$*" >&2; exit 1; }
  version() { sed -n 's/^VERSION = "\(.*\)"/\1/p' "$APP/app/__init__.py" 2>/dev/null || true; }

  case "$mode" in
    ""|--check|--force) ;;
    -h|--help) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "onbekende optie '$mode' (gebruik --check of --force)" ;;
  esac
  [ "$(id -u)" = 0 ] || die "draai dit als root (bijv. met sudo)."
  [ -d "$APP/.git" ] || die "geen installatie via git gevonden in $APP. Installeer opnieuw met:
  curl -fsSL https://raw.githubusercontent.com/lexi1986/unifi-sonar/main/scripts/install.sh | sudo bash"

  local ref="${BRANCH:-}" cur cur_v new new_v=""
  cur=$(git -C "$APP" rev-parse --short HEAD)
  cur_v=$(version)
  if [ -z "$ref" ]; then
    ref=$(git -C "$APP" ls-remote --refs --tags --sort=-v:refname origin 'v[0-9]*' | head -n 1 | sed 's#.*refs/tags/##')
    [ -n "$ref" ] || die "GitHub is niet bereikbaar, of er is nog geen release. Heeft deze machine internet?"
    new_v=${ref#v}
  fi

  say "Zoeken naar een nieuwe versie ($ref)"
  git -C "$APP" fetch -q --depth 50 origin "$ref" || die "GitHub is niet bereikbaar. Heeft deze machine internet?"
  new=$(git -C "$APP" rev-parse --short FETCH_HEAD)

  # Nooit terug naar een oudere release, en ook niet opnieuw als je deze versie al hebt.
  if [ -n "$new_v" ] && [ "$mode" != --force ] && [ "$(printf '%s\n%s\n' "$cur_v" "$new_v" | sort -V | tail -n 1)" = "$cur_v" ]; then
    say "UniFi Sonar is al up-to-date (versie $cur_v)."
    exit 0
  fi
  if [ "$cur" = "$new" ] && [ "$mode" != --force ]; then
    say "UniFi Sonar is al up-to-date (versie $cur_v, $cur)."
    exit 0
  fi
  if [ "$cur" != "$new" ]; then
    echo
    echo "  Nieuw sinds jouw versie ($cur_v, $cur):"
    git -C "$APP" log -n 15 --format='    • %s' HEAD..FETCH_HEAD 2>/dev/null || echo "    (lijst niet beschikbaar)"
    echo
  fi
  if [ "$mode" = --check ]; then
    echo "  Bijwerken: typ 'update'."
    exit 0
  fi

  if [ -f "$DATA/config.json" ]; then   # voor de zekerheid: je koppeling en meldingskanalen
    cp -p "$DATA/config.json" "$DATA/config.json.bak"
  fi
  git -C "$APP" reset -q --hard FETCH_HEAD
  SOURCE_DIR="$APP" bash "$APP/scripts/install.sh"
  echo
  say "Bijgewerkt: $cur_v ($cur) → $(version) ($new)."
}

main "$@"
exit
