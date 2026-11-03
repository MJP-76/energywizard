#!/usr/bin/env bash
# EnergyWizard: installera med en rad. Resten görs i webben.
#
#   curl -fsSL https://raw.githubusercontent.com/murre87/energywizard/main/install.sh | bash
#
# Lägger docker-compose.yml i ~/energywizard (eller EW_DIR) och startar. Går att köra igen
# för att uppdatera; datamappen ./data behålls.
set -euo pipefail
DIR="${EW_DIR:-$HOME/energywizard}"
URL="https://raw.githubusercontent.com/murre87/energywizard/main/docker-compose.enkel.yml"

say() { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mFel:\033[0m %s\n' "$*" >&2; exit 1; }

command -v docker >/dev/null || die "Docker saknas. Installera det först: https://docs.docker.com/engine/install/"
docker compose version >/dev/null 2>&1 || die "'docker compose' saknas. Installera Docker Compose v2."
docker info >/dev/null 2>&1 || die "Docker svarar inte. Kör som en användare i gruppen docker, eller med sudo."

mkdir -p "$DIR/data"
cd "$DIR"
say "Hämtar docker-compose.yml till $DIR"
curl -fsSL "$URL" -o docker-compose.yml
say "Startar EnergyWizard (första gången tar det någon minut)"
docker compose pull -q
docker compose up -d

ip=$(hostname -I 2>/dev/null | awk '{print $1}'); ip="${ip:-den-här-datorn}"
echo
say "Klart! Öppna http://$ip:8503 och följ startguiden."
echo "    Den frågar efter ett lösenord, Home Assistants adress och en token,"
echo "    och sedan väljer du dina prylar. Ingen fil behöver ändras."
