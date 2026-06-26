"""Tests fuer die Domaenen-Bearbeitung (Organisation, Einheit, Rolle, Funktion, Person)."""
from app.auth.permissions import TEMPLATE_ROLES, ACCOUNT_ADMIN_ROLE
from tests.conftest import make_account_with_role, login


def _admin(app, client):
    make_account_with_role(app, ACCOUNT_ADMIN_ROLE, TEMPLATE_ROLES[ACCOUNT_ADMIN_ROLE],
                           email="admin@test.ch")
    login(client, "admin@test.ch")


def test_create_and_edit_organization(app, client):
    _admin(app, client)
    r = client.post("/organization/edit",
                    data={"name": "Test Staatsanwaltschaft", "description": "Pilot"},
                    follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        from app.models import Organization
        org = Organization.query.filter_by(name="Test Staatsanwaltschaft").first()
        assert org is not None and org.account_id is not None
        oid = org.id
    r2 = client.post(f"/organization/edit/{oid}", data={"name": "STA NW", "description": ""},
                     follow_redirects=True)
    assert r2.status_code == 200
    with app.app_context():
        from app.models import Organization
        assert Organization.query.get(oid).name == "STA NW"


def test_new_org_form_renders(app, client):
    _admin(app, client)
    assert client.get("/organization/edit").status_code == 200       # neue Organisation
    assert client.get("/organization/role/edit").status_code == 200  # neue Rolle
    assert client.get("/organization/function/edit").status_code == 200
    assert client.get("/organization/person/edit").status_code == 200


def test_create_person_and_unit(app, client):
    _admin(app, client)
    client.post("/organization/edit", data={"name": "Org1"}, follow_redirects=True)
    with app.app_context():
        from app.models import Organization
        oid = Organization.query.filter_by(name="Org1").first().id
    # Einheit-Formular (neu) rendert mit organization_id
    assert client.get(f"/organization/unit/edit?organization_id={oid}").status_code == 200
    # Person anlegen
    r = client.post("/organization/person/edit",
                    data={"name": "Anna Keller", "annual_salary": "150000", "fte": "1.0",
                          "active": "1", "organization_id": str(oid)},
                    follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        from app.models import Person
        p = Person.query.filter_by(name="Anna Keller").first()
        assert p is not None and p.account_id is not None and p.organization_id == oid


def test_viewer_cannot_create_organization(app, client):
    from app.auth.permissions import P_DASHBOARD_VIEW
    make_account_with_role(app, "Viewer", {P_DASHBOARD_VIEW}, email="v@test.ch")
    login(client, "v@test.ch")
    assert client.post("/organization/edit", data={"name": "Hack"}).status_code == 403
