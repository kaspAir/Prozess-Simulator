from sqlalchemy import text
from app.app import app, db

with app.app_context():
    db.create_all()
    with db.engine.begin() as conn:
        conn.execute(text("ALTER TABLE edges ADD COLUMN IF NOT EXISTS probability_percent DOUBLE PRECISION"))
    print("OK: probability_percent auf edges ist vorhanden.")
