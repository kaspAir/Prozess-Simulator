from sqlalchemy import text
from app.app import app, db
from app.models import Process, Node, Edge

with app.app_context():
    db.create_all()

    with db.engine.begin() as conn:
        conn.execute(text("ALTER TABLE processes ADD COLUMN IF NOT EXISTS x DOUBLE PRECISION DEFAULT 80 NOT NULL"))
        conn.execute(text("ALTER TABLE processes ADD COLUMN IF NOT EXISTS y DOUBLE PRECISION DEFAULT 160 NOT NULL"))

    processes = Process.query.order_by(Process.id).all()

    if len(processes) == 1:
        p1 = processes[0]
        p1.name = "Hauptprozess Eingang Rapport"
        p1.parent_process_id = None
        p1.x = 80
        p1.y = 180

        p2 = Process(name="Hauptprozess Strafbefehl", parent=p1, x=420, y=180)
        p3 = Process(name="Hauptprozess Nacharbeiten", parent=p2, x=760, y=180)
        db.session.add_all([p1, p2, p3])
        db.session.commit()

        for p in [p2, p3]:
            start = Node(process=p, type="start", name="Start", sort_order=0, x=80, y=180)
            end = Node(process=p, type="end", name="Ende", sort_order=99, x=520, y=180)
            db.session.add_all([start, end])
            db.session.commit()
            db.session.add(Edge(source_node=start, target_node=end))
            db.session.commit()

    else:
        for i, p in enumerate(processes):
            p.x = p.x or (80 + (i % 4) * 300)
            p.y = p.y or (120 + (i // 4) * 180)
        db.session.commit()

    print("OK: Prozesslandkarte bereit.")
