from sqlalchemy import text
from app.app import app, db

with app.app_context():
    db.create_all()

    with db.engine.begin() as conn:
        conn.execute(text("ALTER TABLE processes ADD COLUMN IF NOT EXISTS x DOUBLE PRECISION DEFAULT 80 NOT NULL"))
        conn.execute(text("ALTER TABLE processes ADD COLUMN IF NOT EXISTS y DOUBLE PRECISION DEFAULT 160 NOT NULL"))

        result = conn.execute(text("SELECT id, x, y FROM processes ORDER BY id"))
        rows = result.fetchall()

        for i, row in enumerate(rows):
            # Nur alte Default-Positionen sinnvoll verteilen.
            if row.x == 80 and row.y == 160:
                x = 80 + (i % 4) * 300
                y = 120 + (i // 4) * 180
                conn.execute(
                    text("UPDATE processes SET x = :x, y = :y WHERE id = :id"),
                    {"x": x, "y": y, "id": row.id},
                )

    print("OK: Prozesspositionen sind im Model und in der DB vorbereitet.")
