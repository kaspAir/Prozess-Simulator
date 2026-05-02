from sqlalchemy import text
from app.app import app, db

with app.app_context():
    db.create_all()

    with db.engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS node_function (
                node_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
                function_id INTEGER NOT NULL REFERENCES functions(id) ON DELETE CASCADE,
                PRIMARY KEY (node_id, function_id)
            )
        """))

    print("OK: node_function Tabelle bereit.")
