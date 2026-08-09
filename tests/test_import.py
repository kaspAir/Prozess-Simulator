"""Import eines exportierten Modells in einen anderen Account (Roundtrip)."""
import json

from app.auth.permissions import TEMPLATE_ROLES, ACCOUNT_ADMIN_ROLE
from tests.conftest import make_account_with_role, login


def test_import_route_urlencoded(app, client):
    """Import läuft über ein normales Formularfeld (urlencoded) – proxy-tauglich."""
    make_account_with_role(app, ACCOUNT_ADMIN_ROLE, TEMPLATE_ROLES[ACCOUNT_ADMIN_ROLE],
                           email="imp@test.ch")
    login(client, "imp@test.ch")
    data = {"organizations": [{"id": 1, "name": "Importierte Org", "description": None, "units": []}],
            "roles": [], "functions": [], "persons": []}
    r = client.post("/organization/import", data={"json": json.dumps(data)}, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        from app.models import Organization
        assert Organization.query.filter_by(name="Importierte Org").first() is not None


def test_import_dedup_is_per_organization(app, client):
    """Dedup wirkt JE ORGANISATION (Mandant): innerhalb einer Organisation gibt es
    keine Katalog-Dubletten. Zwei Importe legen (additiv) zwei Organisationen an –
    jede hat ihren eigenen, dublettenfreien Katalog (nichts wird über Mandanten
    hinweg vermischt)."""
    make_account_with_role(app, ACCOUNT_ADMIN_ROLE, TEMPLATE_ROLES[ACCOUNT_ADMIN_ROLE],
                           email="imp2@test.ch")
    login(client, "imp2@test.ch")
    data = {"organizations": [{"id": 1, "name": "Org", "description": None, "units": []}],
            "roles": [{"id": 10, "name": "Jurist", "parent_id": None, "function_ids": [100]}],
            "functions": [{"id": 100, "name": "Prüfen", "description": None}],
            "persons": []}
    for _ in range(2):
        r = client.post("/organization/import", data={"json": json.dumps(data)},
                        follow_redirects=True)
        assert r.status_code == 200
    with app.app_context():
        from app.models import Function, Role, Account, Organization
        acc = Account.query.filter_by(name="TestAcc").first()
        orgs = Organization.query.filter_by(account_id=acc.id, name="Org").all()
        assert len(orgs) == 2                     # additiver Import -> zwei Mandanten
        for org in orgs:                          # je Mandant genau eine Instanz
            assert Function.query.filter_by(organization_id=org.id, name="Prüfen").count() == 1
            assert Role.query.filter_by(organization_id=org.id, name="Jurist").count() == 1


def test_export_import_roundtrip(app):
    from app.models import db, Account, Organization, OrgUnit, Role, Function, Person
    from app.services.export_service import build_model_export
    from app.services.import_service import import_model

    with app.app_context():
        # Quell-Account mit vollständigem Mini-Modell
        acc_a = Account(name="A"); db.session.add(acc_a); db.session.flush()
        fn = Function(account_id=acc_a.id, name="Prüfen"); db.session.add(fn); db.session.flush()
        role = Role(account_id=acc_a.id, name="Jurist"); role.functions = [fn]
        db.session.add(role); db.session.flush()
        org = Organization(account_id=acc_a.id, name="STA MK"); db.session.add(org); db.session.flush()
        person = Person(account_id=acc_a.id, name="Anna", organization_id=org.id,
                        annual_salary=100000, fte=1.0)
        person.roles = [role]; person.functions = [fn]
        db.session.add(person); db.session.flush()
        dep = OrgUnit(organization_id=org.id, name="Abteilung", unit_type="Abteilung")
        db.session.add(dep); db.session.flush()
        stelle = OrgUnit(organization_id=org.id, name="Stelle 1", unit_type="Stelle",
                         parent_id=dep.id, person_id=person.id)
        stelle.roles = [role]
        db.session.add(stelle); db.session.flush()

        # Prozess im alten Node-Modell (wird beim Export zu BPMN)
        from app.models import Process, Node, Edge
        proc = Process(account_id=acc_a.id, name="P1", owner_org_unit_id=dep.id)
        db.session.add(proc); db.session.flush()
        n1 = Node(process_id=proc.id, type="start", name="Start", x=50, y=50, sort_order=0)
        n2 = Node(process_id=proc.id, type="task", name="Prüfen", effort_minutes=30,
                  x=180, y=50, sort_order=1)
        n2.required_functions = [fn]; n2.roles = [role]; n2.assigned_positions = [stelle]
        n3 = Node(process_id=proc.id, type="end", name="Ende", x=320, y=50, sort_order=2)
        db.session.add_all([n1, n2, n3]); db.session.flush()
        db.session.add_all([
            Edge(source_node_id=n1.id, target_node_id=n2.id),
            Edge(source_node_id=n2.id, target_node_id=n3.id, probability_percent=100),
        ])
        db.session.commit()

        data = build_model_export(acc_a.id)
        assert data["processes"][0]["bpmn_xml"].startswith("<?xml")  # BPMN erzeugt

        # Ziel-Account: importieren
        acc_b = Account(name="B"); db.session.add(acc_b); db.session.commit()
        counts = import_model(acc_b.id, data)
        assert counts == {"functions": 1, "roles": 1, "organizations": 1,
                          "persons": 1, "units": 2, "processes": 1}

        # Prozess kam als BPMN an, mit auf den Zielaccount umgeschriebenen IDs
        p2 = Process.query.filter_by(account_id=acc_b.id, name="P1").first()
        assert p2 is not None and p2.bpmn_xml
        fn2 = Function.query.filter_by(account_id=acc_b.id, name="Prüfen").first()
        st2 = (OrgUnit.query.join(Organization)
               .filter(Organization.account_id == acc_b.id, OrgUnit.name == "Stelle 1").first())
        assert 'pros:functionIds="%d"' % fn2.id in p2.bpmn_xml
        assert 'pros:positionIds="%d"' % st2.id in p2.bpmn_xml
        # Rechnung greift: Aufwand 30 Min., Kosten > 0 (Stelle -> Person -> Gehalt)
        from app.services.bpmn_simulation import analyze_bpmn
        res = analyze_bpmn(p2)
        assert res["has_model"] and abs(res["total_effort"] - 30) < 0.01
        assert res["total_cost"] > 0

        # Relationen korrekt neu verdrahtet?
        org2 = Organization.query.filter_by(account_id=acc_b.id, name="STA MK").first()
        assert org2 is not None
        p2 = Person.query.filter_by(account_id=acc_b.id, name="Anna").first()
        assert p2.organization_id == org2.id
        assert [r.name for r in p2.roles] == ["Jurist"]
        assert [f.name for f in p2.functions] == ["Prüfen"]
        st2 = (OrgUnit.query.join(Organization)
               .filter(Organization.account_id == acc_b.id, OrgUnit.name == "Stelle 1").first())
        assert st2.person_id == p2.id
        assert st2.parent_id is not None          # parent (Abteilung) neu gemappt
        assert [r.name for r in st2.roles] == ["Jurist"]
