from app import create_app
from app.models import db, Activity, Role, Function, Person, Process, Node, Edge

app = create_app()

with app.app_context():
    db.drop_all()
    db.create_all()

    roles = [
        Role(name="Leitende Staatsanwältin"),
        Role(name="Staatsanwalt", parent_id=1),
        Role(name="Juristische Mitarbeiterin", parent_id=2),
        Role(name="Kanzlei", parent_id=2),
    ]
    functions = [
        Function(name="Prüfen"),
        Function(name="Recherchieren"),
        Function(name="Entscheiden"),
        Function(name="Erstellen"),
        Function(name="Signieren"),
    ]
    persons = [
        Person(name="Anna Keller", annual_salary=155000, fte=1.0),
        Person(name="Beat Meier", annual_salary=125000, fte=1.0),
        Person(name="Claudia Rossi", annual_salary=95000, fte=0.8),
        Person(name="David Schmid", annual_salary=82000, fte=1.0),
    ]
    db.session.add_all(roles + functions + persons)
    db.session.commit()

    roles[0].functions.extend([functions[2], functions[4]])
    roles[1].functions.extend([functions[0], functions[2], functions[3], functions[4]])
    roles[2].functions.extend([functions[0], functions[1], functions[3]])
    roles[3].functions.extend([functions[1], functions[3]])

    persons[0].roles.append(roles[0])
    persons[1].roles.append(roles[1])
    persons[2].roles.append(roles[2])
    persons[3].roles.append(roles[3])

    main_process = Process(name="Hauptprozess Strafbefehl")
    sub_process = Process(name="Subprozess Abklärungen", parent=main_process)
    db.session.add_all([main_process, sub_process])
    db.session.commit()

    n_start = Node(process=main_process, type="start", name="Start", sort_order=0)
    n1 = Node(process=main_process, type="task", name="Eingang Polizeirapport", effort_minutes=20, legal_basis="Art. 309 StPO / Verfahrenseinleitung", sort_order=1)
    n2 = Node(process=main_process, type="task", name="Behördenauszug 1 aus VOSTRA herunterladen", effort_minutes=10, legal_basis="Strafregistergesetz StReG / VOSTRA", sort_order=2)
    n3 = Node(process=main_process, type="xor", name="Sachverhalt klar?", sort_order=3)
    n_sub = Node(process=main_process, type="subprocess", name="Zusätzliche Abklärungen", subprocess=sub_process, sort_order=4)
    n4 = Node(process=main_process, type="task", name="Straftatbestand festlegen", effort_minutes=45, legal_basis="StGB / Spezialgesetzgebung", sort_order=5)
    n5 = Node(process=main_process, type="task", name="Sanktion festlegen", effort_minutes=30, legal_basis="Art. 352 ff. StPO, StGB Sanktionen", sort_order=6)
    n6 = Node(process=main_process, type="task", name="Strafbefehl erstellen", effort_minutes=40, legal_basis="Art. 352 ff. StPO", sort_order=7)
    n7 = Node(process=main_process, type="task", name="Strafbefehl signieren", effort_minutes=10, legal_basis="Art. 353 StPO", sort_order=8)
    n_end = Node(process=main_process, type="end", name="Ende", sort_order=9)

    s_start = Node(process=sub_process, type="start", name="Start Subprozess", sort_order=0)
    s1 = Node(process=sub_process, type="task", name="Akten ergänzen", effort_minutes=30, legal_basis="StPO Untersuchungsgrundsatz", sort_order=1)
    s2 = Node(process=sub_process, type="task", name="Rückfrage Polizei", effort_minutes=45, legal_basis="StPO Beweiserhebung", sort_order=2)
    s_end = Node(process=sub_process, type="end", name="Zurück in Hauptprozess", sort_order=3)

    db.session.add_all([n_start, n1, n2, n3, n_sub, n4, n5, n6, n7, n_end, s_start, s1, s2, s_end])
    db.session.commit()

    n1.roles.append(roles[3])
    n2.roles.append(roles[3])
    n4.roles.extend([roles[1], roles[2]])
    n5.roles.append(roles[1])
    n6.roles.extend([roles[2], roles[3]])
    n7.roles.append(roles[1])
    s1.roles.append(roles[2])
    s2.roles.append(roles[3])

    edges = [
        Edge(source_node=n_start, target_node=n1),
        Edge(source_node=n1, target_node=n2),
        Edge(source_node=n2, target_node=n3),
        Edge(source_node=n3, target_node=n4, condition="ja"),
        Edge(source_node=n3, target_node=n_sub, condition="nein"),
        Edge(source_node=n_sub, target_node=n4, condition="nach Abklärung"),
        Edge(source_node=n4, target_node=n5),
        Edge(source_node=n5, target_node=n6),
        Edge(source_node=n6, target_node=n7),
        Edge(source_node=n7, target_node=n_end),
        Edge(source_node=s_start, target_node=s1),
        Edge(source_node=s1, target_node=s2),
        Edge(source_node=s2, target_node=s_end),
    ]
    db.session.add_all(edges)

    db.session.add_all([
        Activity(name=n1.name, effort_minutes=n1.effort_minutes, legal_basis=n1.legal_basis, sort_order=1),
        Activity(name=n2.name, effort_minutes=n2.effort_minutes, legal_basis=n2.legal_basis, sort_order=2),
        Activity(name=n4.name, effort_minutes=n4.effort_minutes, legal_basis=n4.legal_basis, sort_order=3),
        Activity(name=n5.name, effort_minutes=n5.effort_minutes, legal_basis=n5.legal_basis, sort_order=4),
        Activity(name=n6.name, effort_minutes=n6.effort_minutes, legal_basis=n6.legal_basis, sort_order=5),
        Activity(name=n7.name, effort_minutes=n7.effort_minutes, legal_basis=n7.legal_basis, sort_order=6),
    ])

    db.session.commit()
    print("Datenbank mit BPMN-Light Graphmodell initialisiert.")
