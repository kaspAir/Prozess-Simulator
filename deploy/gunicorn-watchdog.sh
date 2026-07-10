#!/usr/bin/env bash
# Watchdog fuer die Gunicorn-Prozesse auf Infomaniak Managed Hosting.
#
# Hintergrund: Gunicorn laeuft via `nohup … &` ohne Supervisor. Managed Hosting
# beendet lang laufende Hintergrundprozesse regelmaessig (Wartung/Reboot/Reaper).
# Dieses Skript prueft je Umgebung den Port und startet Gunicorn bei Bedarf neu.
#
# Installation auf dem Server:
#   cp deploy/gunicorn-watchdog.sh ~/gunicorn-watchdog.sh   # oder Inhalt einfuegen
#   chmod +x ~/gunicorn-watchdog.sh
# Cron (alle 3 Minuten):
#   */3 * * * * /bin/bash $HOME/gunicorn-watchdog.sh >> $HOME/tmp/watchdog.log 2>&1

restart() {  # $1=Verzeichnis $2=Port $3=Name
  curl -sf -o /dev/null "http://127.0.0.1:$2/login" && { echo "$(date '+%F %T') $3 :$2 ok"; return 0; }
  cd "$HOME/$1" || return 1
  . .venv/bin/activate
  set -a; [ -f .env ] && . ./.env; set +a
  mkdir -p logs "$HOME/tmp"
  pidf="$HOME/tmp/gunicorn-pros-$3.pid"
  [ -f "$pidf" ] && kill "$(cat "$pidf")" 2>/dev/null || true
  nohup .venv/bin/gunicorn run:app --bind 127.0.0.1:"$2" --workers 2 --timeout 120 \
        --access-logfile logs/access.log --error-logfile logs/error.log >/dev/null 2>&1 &
  echo $! > "$pidf"
  deactivate
  echo "$(date '+%F %T') $3 :$2 NEU GESTARTET"
}

restart prozess-simulator      8010 prod
restart prozess-simulator-int  8012 int
restart prozess-simulator-test 8011 test
