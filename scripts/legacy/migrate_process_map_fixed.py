from sqlalchemy import text
from app.app import app, db
from app.models import Process, Node, Edge

with app.app_context():
    db.create_all()

    with db.engine.begin() as conn:
        conn.execute(text("ALTER TABLE processes ADD COLUMN IF NOT EXISTS x DOUBLE PRECISION DEFAULT 80 NOT NULL"))
        conn.execute(text("ALTER TABLE processes ADD COLUMN IF NOT EXISTS y DOUBLE PRECISION DEFAULT 160 NOT NULL"))

    processes = Process.query.order_by(Process.id).all()

    # Demo-Prozesslandkarte, falls nur ein Prozess existiert
    if len(processes) == 1:
        p1 = processes[0]
        p1.name = "Hauptprozess Eingang Rapport"
        p1.parent_process_id = None
        db.session.add(p1)
        db.session.commit()

        with db.engine.begin() as conn:
            conn.execute(text("UPDATE processes SET x = 80, y = 180 WHERE id = :id"), {"id": p1.id})

        p2 = Process(name="Hauptprozess Strafbefehl", parent=p1)
        p3 = Process(name="Hauptprozess Nacharbeiten")
        db.session.add(p2)
        db.session.commit()

        p3.parent = p2
        db.session.add(p3)
        db.session.commit()

        with db.engine.begin() as conn:
            conn.execute(text("UPDATE processes SET x = 420, y = 180 WHERE id = :id"), {"id": p2.id})
            conn.execute(text("UPDATE processes SET x = 760, y = 180 WHERE id = :id"), {"id": p3.id})

        for p in [p2, p3]:
            start = Node(process=p, type="start", name="Start", sort_order=0, x=80, y=180)
            end = Node(process=p, type="end", name="Ende", sort_order=99, x=520, y=180)
            db.session.add_all([start, end])
            db.session.commit()
            db.session.add(Edge(source_node=start, target_node=end))
            db.session.commit()

    else:
        with db.engine.begin() as conn:
            result = conn.execute(text("SELECT id FROM processes ORDER BY id"))
            rows = result.fetchall()

            for i, row in enumerate(rows):
                x = 80 + (i % 4) * 300
                y = 120 + (i // 4) * 180
                conn.execute(
                    text("UPDATE processes SET x = :x, y = :y WHERE id = :id AND (x = 80 AND y = 160)"),
                    {"x": x, "y": y, "id": row.id},
                )

    print("OK: Prozesslandkarte bereit.")
