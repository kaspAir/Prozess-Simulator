"""Daten von einer Quell-DB in eine Ziel-DB kopieren (z. B. SQLite -> MariaDB).

Nutzt die in den Modellen definierten Tabellen und ihre Fremdschlüssel-Reihenfolge
(metadata.sorted_tables), legt das Schema in der Zieldatenbank an und kopiert alle
Zeilen Tabelle für Tabelle. Auto-Increment-Zähler werden bei MySQL/MariaDB am Ende
gesetzt.

Beispiel:
  python scripts/migrate_db.py \
    --source "sqlite:///C:/.../data/prozess_simulator.db" \
    --target "mysql+pymysql://user:pass@host/prozess_simulator"

Hinweis: Die Zieltabellen sollten leer sein (frische DB). Mit --wipe werden sie
vorher geleert.
"""
import argparse
import os
import sys

# Projekt-Root auf den Importpfad legen (Skript liegt in scripts/).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, select, insert, func, text

# Alle Modelle importieren, damit db.metadata vollständig ist.
import app.models as models
db = models.db


def migrate(source_url, target_url, wipe=False):
    src = create_engine(source_url)
    dst = create_engine(target_url)
    md = db.metadata

    print(f"Quelle: {src.url}")
    print(f"Ziel:   {dst.url}")
    md.create_all(dst)
    print("Schema in Zieldatenbank sichergestellt.")

    tables = list(md.sorted_tables)

    if wipe:
        with dst.begin() as dconn:
            for table in reversed(tables):
                dconn.execute(table.delete())
        print("Zieltabellen geleert.")

    with src.connect() as sconn, dst.begin() as dconn:
        for table in tables:
            rows = [dict(r._mapping) for r in sconn.execute(select(table))]
            if rows:
                dconn.execute(insert(table), rows)
            print(f"  {table.name:28s} {len(rows):6d} Zeilen")

    # Auto-Increment bei MySQL/MariaDB auf max(id)+1 setzen
    if dst.dialect.name in ("mysql", "mariadb"):
        with dst.begin() as dconn:
            for table in tables:
                if "id" in table.c:
                    maxid = dconn.execute(select(func.max(table.c.id))).scalar() or 0
                    dconn.execute(text(f"ALTER TABLE {table.name} AUTO_INCREMENT = {maxid + 1}"))
        print("Auto-Increment-Zähler gesetzt.")

    print("Migration abgeschlossen.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="Quell-DB (SQLAlchemy-URL)")
    ap.add_argument("--target", required=True, help="Ziel-DB (SQLAlchemy-URL)")
    ap.add_argument("--wipe", action="store_true", help="Zieltabellen vorher leeren")
    args = ap.parse_args()
    migrate(args.source, args.target, wipe=args.wipe)
