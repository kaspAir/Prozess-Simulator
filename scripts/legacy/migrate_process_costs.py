from sqlalchemy import text
from app.app import app, db

with app.app_context():
    db.create_all()

    with db.engine.begin() as conn:
        conn.execute(text("ALTER TABLE processes ADD COLUMN IF NOT EXISTS owner_org_unit_id INTEGER"))

        conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM information_schema.table_constraints
                    WHERE constraint_name = 'processes_owner_org_unit_id_fkey'
                ) THEN
                    ALTER TABLE processes
                    ADD CONSTRAINT processes_owner_org_unit_id_fkey
                    FOREIGN KEY (owner_org_unit_id) REFERENCES org_units(id);
                END IF;
            END
            $$;
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS node_position (
                node_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
                org_unit_id INTEGER NOT NULL REFERENCES org_units(id) ON DELETE CASCADE,
                PRIMARY KEY (node_id, org_unit_id)
            )
        """))

    print("OK: Prozesskosten-Modell vorbereitet.")
