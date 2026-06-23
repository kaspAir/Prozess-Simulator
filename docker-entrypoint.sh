#!/usr/bin/env bash
set -e

# Beim ersten Start (leeres Volume) Datenbank anlegen und mit Demo-Daten seeden.
# init_db.py macht drop_all()+create_all()+seed -> daher NUR ausfuehren, wenn
# noch keine DB existiert, um vorhandene Daten nicht zu loeschen.
DB_FILE="/app/data/prozess_simulator.db"

if [ ! -f "$DB_FILE" ]; then
    echo "[entrypoint] Keine Datenbank gefunden -> initialisiere $DB_FILE"
    python init_db.py
else
    echo "[entrypoint] Datenbank vorhanden -> kein Demo-Seed."
fi

# Auth-Seed ist idempotent: Account, Vorlagen-Rollen, Daten-Zuordnung,
# Bootstrap-Admin (falls BOOTSTRAP_ADMIN_* gesetzt).
echo "[entrypoint] Auth-Seed..."
python seed_auth.py

exec "$@"
