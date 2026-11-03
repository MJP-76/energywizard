#!/usr/bin/env bash
# EnergyWizard: installera med en rad.
#
#   curl -fsSL https://raw.githubusercontent.com/murre87/energywizard/main/install.sh | bash
#
# Frågar efter Home Assistants adress, en token och ett lösenord till webben. Sedan skapas
# allt annat (.env, databaslösenord, en tom house_config.yaml) och allt startas. Resten,
# alltså vilka prylar du har, väljer du i webben med entitetsväljaren.
#
# Går att köra igen: befintliga inställningar behålls, och koden uppdateras.
# Utan frågor: EW_HA_URL=... EW_HA_TOKEN=... EW_PASSWORD=... bash install.sh
set -euo pipefail

REPO="https://github.com/murre87/energywizard.git"
DIR="${EW_DIR:-$HOME/energywizard}"

say()  { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m  %s\n' "$*"; }
die()  { printf '\033[1;31mFel:\033[0m %s\n' "$*" >&2; exit 1; }

# Frågor läses från terminalen även när skriptet kommer via "curl | bash".
ask() {  # ask <variabel> <fråga> [dold]
  local __v="$1" __q="$2" __hide="${3:-}" __a=""
  if [ -n "${!__v:-}" ]; then return; fi
  have_tty || die "Ingen terminal att fråga i. Sätt $__v i miljön."
  if [ -n "$__hide" ]; then read -r -s -p "$__q: " __a </dev/tty; echo >/dev/tty
  else read -r -p "$__q: " __a </dev/tty; fi
  printf -v "$__v" '%s' "$__a"
}

have_tty() { (: </dev/tty) 2>/dev/null; }
randpw() { LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24; }

# --- 1. Förutsättningar -------------------------------------------------------------------
command -v git >/dev/null    || die "git saknas. Installera det först (t.ex. 'sudo apt install git')."
command -v docker >/dev/null || die "Docker saknas. Installera det först: https://docs.docker.com/engine/install/"
docker compose version >/dev/null 2>&1 || die "'docker compose' saknas. Installera Docker Compose v2."
docker info >/dev/null 2>&1 || die "Docker svarar inte. Kör som en användare i gruppen docker, eller med sudo."

# --- 2. Koden -----------------------------------------------------------------------------
if [ -f docker-compose.yml ] && [ -d smartbox ]; then
  DIR="$PWD"                                  # körs inifrån en befintlig kopia
elif [ -d "$DIR/.git" ]; then
  say "Uppdaterar koden i $DIR"
  git -C "$DIR" pull --ff-only -q || warn "Kunde inte uppdatera koden, kör vidare med den som finns."
else
  say "Hämtar EnergyWizard till $DIR"
  git clone -q --depth 1 "$REPO" "$DIR"
fi
cd "$DIR"

# --- 3. Inställningar (bara första gången) ------------------------------------------------
if [ -f .env ]; then
  say "Behåller dina inställningar i $DIR/.env"
else
  echo
  echo "Två uppgifter från Home Assistant behövs:"
  echo "  1. Adressen, t.ex. 192.168.1.10 eller http://homeassistant.local:8123"
  echo "  2. En token: i Home Assistant, klicka på ditt namn nere till vänster, fliken"
  echo "     Säkerhet, och längst ner 'Skapa token'."
  echo
  EW_HA_URL="${EW_HA_URL:-}"; EW_HA_TOKEN="${EW_HA_TOKEN:-}"; EW_PASSWORD="${EW_PASSWORD:-}"
  while :; do
    ask EW_HA_URL "Home Assistants adress"
    ask EW_HA_TOKEN "Token (syns inte när du klistrar in)" hide
    case "$EW_HA_URL" in http://*|https://*) url="${EW_HA_URL%/}";;
                          *:*) url="http://${EW_HA_URL%/}";;
                          *)   url="http://${EW_HA_URL%/}:8123";; esac
    url="${url%/api}"
    code=$(curl -sk -o /dev/null -w '%{http_code}' -m 10 -H "Authorization: Bearer $EW_HA_TOKEN" "$url/api/" || true)
    if [ "$code" = "200" ]; then say "Kontakt med Home Assistant på $url"; break; fi
    case "$code" in
      401|403) warn "Home Assistant svarade men tog inte emot token ($code).";;
      000)     warn "Fick inget svar från $url. Stämmer adressen? Prova med https:// om din HA kör det.";;
      *)       warn "Oväntat svar från $url ($code).";;
    esac
    have_tty || die "Kontrollera EW_HA_URL och EW_HA_TOKEN."
    ans=""; read -r -p "Försöka igen? [J/n] " ans </dev/tty
    case "$ans" in n|N) warn "Fortsätter ändå. Du kan rätta HA_URL/HA_TOKEN i $DIR/.env senare."; break;; esac
    EW_HA_URL=""; EW_HA_TOKEN=""
  done
  while [ -z "$EW_PASSWORD" ]; do
    ask EW_PASSWORD "Välj ett lösenord till webben" hide
  done

  umask 077
  cat > .env <<EOF
# Skapad av install.sh $(date +%F). Checkas aldrig in i git.
HA_URL=$url
HA_TOKEN=$EW_HA_TOKEN
POSTGRES_USER=energywizard
POSTGRES_PASSWORD=$(randpw)
POSTGRES_DB=energywizard
HOUSE_CONFIG_HOST_PATH=./config/house_config.yaml
HOUSE_CONFIG_MODE=rw
HOUSE_CONFIG_WRITABLE=1
DASHBOARD_ENV_PATH=./secrets/dashboard.env
EOF
  mkdir -p secrets
  [ -f secrets/dashboard.env ] || printf 'DASHBOARD_PASSWORD=%s\n' "$EW_PASSWORD" > secrets/dashboard.env
  umask 022
fi

# Tom konfiguration: giltig, allt blir overksamt tills du valt dina prylar i webben.
if [ ! -f config/house_config.yaml ]; then
  printf 'house_id: "%s"\n' "$(hostname | tr -cd 'A-Za-z0-9-' | head -c 40)" > config/house_config.yaml
fi
chmod a+rw config/house_config.yaml     # webben (egen container) sparar här

# --- 4. Starta ----------------------------------------------------------------------------
say "Hämtar och startar (första gången tar det några minuter)"
docker compose --profile webdashboard pull --ignore-pull-failures -q 2>/dev/null || true
docker compose --profile webdashboard up -d

ip=$(hostname -I 2>/dev/null | awk '{print $1}'); ip="${ip:-din-server}"
echo
say "Klart! Öppna http://$ip:8503 och logga in med lösenordet du valde."
echo "    Under Inställningar > Entitetsväljaren hittar den dina prylar i Home Assistant."
echo "    Kryssa i det du har och tryck 'Spara och starta'. Sedan styr EnergyWizard."
echo
echo "    Loggar:      cd $DIR && docker compose logs -f smartbox"
echo "    Uppdatera:   kör samma installationsrad igen"
