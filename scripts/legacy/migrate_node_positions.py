from sqlalchemy import text
from app.app import app, db

with app.app_context():
    with db.engine.begin() as conn:
        conn.execute(text("ALTER TABLE nodes ADD COLUMN IF NOT EXISTS x DOUBLE PRECISION DEFAULT 80 NOT NULL"))
        conn.execute(text("ALTER TABLE nodes ADD COLUMN IF NOT EXISTS y DOUBLE PRECISION DEFAULT 160 NOT NULL"))

        result = conn.execute(text("SELECT id, sort_order, type FROM nodes ORDER BY process_id, sort_order, id"))
        rows = result.fetchall()

        for row in rows:
            x = 80 + (row.sort_order or 0) * 210
            y = 170
            if row.type == "xor":
                y = 135
            elif row.type == "subprocess":
                y = 290
            conn.execute(text("UPDATE nodes SET x = :x, y = :y WHERE id = :id"), {"x": x, "y": y, "id": row.id})

    print("Migration erledigt: nodes.x und nodes.y sind vorhanden.")
