from app.app import app, db
from app.models import Process, Node, Edge

with app.app_context():
    main = Process.query.order_by(Process.id).first()
    if not main:
        raise SystemExit("Kein Prozess gefunden.")

    subprocess = Process.query.filter(Process.parent_process_id == main.id).first()
    if not subprocess:
        subprocess = Process(name="Subprozess Zusatzabklärungen", parent_process_id=main.id)
        db.session.add(subprocess)
        db.session.commit()

        s = Node(process_id=subprocess.id, type="start", name="Start Subprozess", x=80, y=180, sort_order=0)
        t = Node(process_id=subprocess.id, type="task", name="Zusatzabklärung durchführen", x=280, y=170, sort_order=1, effort_minutes=30)
        e = Node(process_id=subprocess.id, type="end", name="Ende Subprozess", x=560, y=180, sort_order=99)
        db.session.add_all([s, t, e])
        db.session.commit()
        db.session.add_all([
            Edge(source_node_id=s.id, target_node_id=t.id),
            Edge(source_node_id=t.id, target_node_id=e.id),
        ])
        db.session.commit()

    sub_node = Node.query.filter_by(process_id=main.id, type="subprocess").first()
    if not sub_node:
        sub_node = Node(
            process_id=main.id,
            type="subprocess",
            name="Zusätzliche Abklärungen",
            subprocess_id=subprocess.id,
            x=1030,
            y=300,
            sort_order=50,
        )
        db.session.add(sub_node)
        db.session.commit()
    else:
        sub_node.subprocess_id = subprocess.id
        if not sub_node.x:
            sub_node.x = 1030
        if not sub_node.y:
            sub_node.y = 300
        db.session.add(sub_node)
        db.session.commit()

    print("OK: Subprozess und Subprozess-Node sind vorhanden.")
    print(f"Hauptprozess: {main.id}, Subprozess: {subprocess.id}, Subprozess-Node: {sub_node.id}")
