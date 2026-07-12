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
        db.session.add(stelle); db.session.commit()

        data = build_model_export(acc_a.id)

        # Ziel-Account: importieren
        acc_b = Account(name="B"); db.session.add(acc_b); db.session.commit()
        counts = import_model(acc_b.id, data)
        assert counts == {"functions": 1, "roles": 1, "organizations": 1,
                          "persons": 1, "units": 2}

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
