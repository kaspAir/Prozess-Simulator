# Umstieg auf MariaDB (Infomaniak-nativ)

> Status: vorbereitet. Treiber (`PyMySQL`) und Migrationsskript (`scripts/migrate_db.py`)
> sind vorhanden und getestet. Auszuführen, sobald eine MariaDB-Datenbank angelegt ist.

Infomaniak Managed Hosting bietet **MariaDB/MySQL nativ** an – das ist hier der
einfachste Weg zu echtem Mehrbenutzer-Betrieb. PostgreSQL wäre nur als externe/remote
DB möglich und damit aufwändiger.

## 1. MariaDB-Datenbank anlegen (Infomaniak-Panel)
- Im Hosting unter **Datenbanken** eine **MariaDB/MySQL-Datenbank** erstellen.
- Datenbankname, Benutzer und Passwort notieren; Host ist i. d. R. `localhost`
  (gleicher Server) oder der von Infomaniak angegebene DB-Host.
- Zeichensatz **utf8mb4** wählen (Umlaute/Unicode).

## 2. Connection-String
```
mysql+pymysql://<user>:<passwort>@<host>/<dbname>?charset=utf8mb4
```

## 3. Pro Umgebung (test → integration → main)
1. Kurzes Wartungsfenster ankündigen.
2. **Schema + Migration** ausführen (vom App-Verzeichnis der Umgebung, im aktivierten venv):
   ```bash
   python scripts/migrate_db.py \
     --source "sqlite:///$HOME/prozess-simulator/data/prozess_simulator.db" \
     --target "mysql+pymysql://<user>:<pass>@<host>/<dbname>?charset=utf8mb4"
   ```
   Das Skript legt das Schema an, kopiert alle Tabellen in FK-Reihenfolge und setzt
   die Auto-Increment-Zähler. (Mit `--wipe` werden Zieltabellen vorher geleert –
   nur bei wiederholtem Lauf nötig.)
3. **`.env`** der Umgebung anpassen:
   ```
   DATABASE_URL=mysql+pymysql://<user>:<pass>@<host>/<dbname>?charset=utf8mb4
   ```
4. **Deploy** (Jenkins-Job). Die App nutzt nun MariaDB. `seed_auth.py` läuft idempotent
   und ergänzt nur Fehlendes.
5. **Smoke-Test:** Login, Dashboard, Organisation/Person anlegen, Prozess öffnen.
6. Erst test verifizieren, dann integration, dann main.

## Hinweise
- Treiber `PyMySQL` ist bereits in `requirements.txt`.
- Die SQLite-WAL-Einstellungen greifen bei MariaDB nicht (werden übersprungen) – kein Problem.
- SQLite-Dateien als Backup behalten, bis MariaDB verifiziert ist.
- Pro Umgebung eine eigene DB (oder eigener Präfix/Schema), analog zu den getrennten
  SQLite-Dateien.
- Getestet: `scripts/migrate_db.py` kopiert alle Tabellen inkl. Verknüpfungstabellen
  vollständig (Zeilenzahlen identisch).
