from app.app import app, db
from app.models import Activity, Role, Function, Person, role_function, role_activity

with app.app_context():
    db.drop_all()
    db.create_all()

    activities = [
        Activity(name="Eingang Polizeirapport", effort_minutes=20, legal_basis="Art. 309 StPO / Verfahrenseinleitung"),
        Activity(name="Behördenauszug 1 aus VOSTRA herunterladen", effort_minutes=10, legal_basis="Strafregistergesetz StReG / VOSTRA"),
        Activity(name="Straftatbestand festlegen", effort_minutes=45, legal_basis="StGB / Spezialgesetzgebung"),
        Activity(name="Sanktion festlegen", effort_minutes=30, legal_basis="Art. 352 ff. StPO, StGB Sanktionen"),
        Activity(name="Strafbefehl erstellen", effort_minutes=40, legal_basis="Art. 352 ff. StPO"),
        Activity(name="Strafbefehl signieren", effort_minutes=10, legal_basis="Art. 353 StPO"),
    ]

    roles = [
        Role(name="Leitende Staatsanwältin", parent_id=None),
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

    db.session.add_all(activities + roles + functions + persons)
    db.session.commit()

    # Funktionen zu Rollen
    roles[0].functions.extend([functions[2], functions[4]])
    roles[1].functions.extend([functions[0], functions[2], functions[3], functions[4]])
    roles[2].functions.extend([functions[0], functions[1], functions[3]])
    roles[3].functions.extend([functions[1], functions[3]])

    # Personen zu Rollen
    persons[0].roles.append(roles[0])
    persons[1].roles.append(roles[1])
    persons[2].roles.append(roles[2])
    persons[3].roles.append(roles[3])

    # Rollen zu Aktivitäten
    activities[0].roles.append(roles[3])
    activities[1].roles.append(roles[3])
    activities[2].roles.extend([roles[1], roles[2]])
    activities[3].roles.append(roles[1])
    activities[4].roles.extend([roles[2], roles[3]])
    activities[5].roles.append(roles[1])

    db.session.commit()
    print("Datenbank initialisiert und Demodaten geladen.")
