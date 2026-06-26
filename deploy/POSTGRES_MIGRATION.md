# Migration SQLite → PostgreSQL (Plan)

> Status: vorbereitet. Auszuführen, sobald eine PostgreSQL-Instanz verfügbar ist
> (Infomaniak managed DB, Cloud-Server „Phronesis“ oder externer Anbieter).

Bis dahin läuft die Produktion auf **SQLite mit WAL-Härtung** (siehe `app/__init__.py`:
`journal_mode=WAL`, `busy_timeout`), was paralleles Arbeiten im Pilot stabilisiert.

## Voraussetzungen
- Erreichbare PostgreSQL-DB + Connection-String, z. B.
  `postgresql+psycopg2://user:pass@host:5432/prozess_simulator`
- `psycopg2-binary` ist bereits in `requirements.txt`.

## Vorgehen je Umgebung (test → integration → main)

1. **Wartungsfenster** ankündigen (kurz, da Datenmengen klein).
2. **Schema anlegen** in der neuen DB:
   ```bash
   DATABASE_URL=postgresql+psycopg2://… python -c "from app import create_app; from app.models import db; \
     app=create_app();\
     import contextlib;\
     [db.create_all() for _ in [0]] if app.app_context().push() or True else None"
   ```
   (oder schlicht `seed_auth.py` mit gesetzter `DATABASE_URL` ausführen – legt Schema + Account + Rollen + Admin an.)
3. **Daten umziehen** mit dem Helfer (Tabelle für Tabelle, FK-Reihenfolge beachtet):
   ```bash
   python scripts/migrate_sqlite_to_postgres.py \
     --sqlite  ~/prozess-simulator/data/prozess_simulator.db \
     --postgres "postgresql+psycopg2://…"
   ```
   Alternativ `pgloader` für den Massentransfer.
4. **`.env` umstellen**: `DATABASE_URL` der Umgebung auf den Postgres-String setzen.
5. **Deploy** der Umgebung (Jenkins-Job) → App nutzt Postgres.
6. **Smoke-Test**: Login, Dashboard, eine Organisation/Person anlegen, Prozess öffnen.
7. **Reihenfolge**: erst test verifizieren, dann integration, dann main.

## Hinweise
- Reihenfolge beim Datentransfer wegen Fremdschlüsseln:
  accounts → users → organizations → access_roles → memberships → role_assignments →
  roles/functions/activities → org_units → persons → processes → nodes → edges →
  Verknüpfungstabellen (role_function, person_role, node_role, …) → login_events, invitations.
- Sequenzen (ID-Zähler) in Postgres nach dem Import auf `max(id)+1` setzen.
- SQLite-Dateien als Backup behalten, bis Postgres verifiziert ist.

> Der eigentliche Migrations-Skript (`scripts/migrate_sqlite_to_postgres.py`) wird
> erstellt, sobald die Ziel-DB feststeht – er hängt von Details der Instanz ab.
