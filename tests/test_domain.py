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


def test_add_subunit_and_position(app, client):
    _admin(app, client)
    client.post("/organization/edit", data={"name": "OrgX"}, follow_redirects=True)
    with app.app_context():
        from app.models import Organization
        oid = Organization.query.filter_by(name="OrgX").first().id
    client.post("/organization/unit/edit",
                data={"name": "Dep", "unit_type": "Departement", "organization_id": str(oid)},
                follow_redirects=True)
    with app.app_context():
        from app.models import OrgUnit
        pid = OrgUnit.query.filter_by(name="Dep").first().id
    # "Einheit unterstellen" / "Stelle hinzufügen" – GET-Formular rendert mit parent_id
    assert client.get(f"/organization/unit/edit?organization_id={oid}&parent_id={pid}").status_code == 200
    assert client.get(f"/organization/unit/edit?organization_id={oid}&parent_id={pid}&unit_type=Stelle").status_code == 200
    # Untereinheit + Stelle anlegen
    client.post("/organization/unit/edit",
                data={"name": "Sub", "unit_type": "Team", "parent_id": str(pid), "organization_id": str(oid)},
                follow_redirects=True)
    client.post("/organization/unit/edit",
                data={"name": "Stelle1", "unit_type": "Stelle", "parent_id": str(pid), "organization_id": str(oid)},
                follow_redirects=True)
    with app.app_context():
        from app.models import OrgUnit
        sub = OrgUnit.query.filter_by(name="Sub").first()
        stelle = OrgUnit.query.filter_by(name="Stelle1").first()
        assert sub.parent_id == pid
        assert stelle.parent_id == pid and stelle.unit_type == "Stelle"


def test_person_fte_above_one_rejected(app, client):
    """B-03: FTE > 1.0 darf nicht gespeichert werden."""
    _admin(app, client)
    r = client.post("/organization/person/edit",
                    data={"name": "Zu viel FTE", "annual_salary": "120000", "fte": "1.5"},
                    follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        from app.models import Person
        assert Person.query.filter_by(name="Zu viel FTE").first() is None


def test_person_negative_salary_rejected(app, client):
    """B-04: negatives Jahresgehalt darf nicht gespeichert werden."""
    _admin(app, client)
    r = client.post("/organization/person/edit",
                    data={"name": "Minusgehalt", "annual_salary": "-5000", "fte": "1.0"},
                    follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        from app.models import Person
        assert Person.query.filter_by(name="Minusgehalt").first() is None


def test_duplicate_org_name_rejected(app, client):
    """B-06: keine zwei Organisationen mit gleichem Namen im selben Account."""
    _admin(app, client)
    client.post("/organization/edit", data={"name": "OLL"}, follow_redirects=True)
    client.post("/organization/edit", data={"name": "OLL"}, follow_redirects=True)
    with app.app_context():
        from app.models import Organization
        assert Organization.query.filter_by(name="OLL").count() == 1


def test_delete_organization(app, client):
    """B-06: Duplikat/Organisation kann gelöscht werden; Person bleibt erhalten."""
    _admin(app, client)
    client.post("/organization/edit", data={"name": "ZuLoeschen"}, follow_redirects=True)
    with app.app_context():
        from app.models import Organization
        oid = Organization.query.filter_by(name="ZuLoeschen").first().id
    client.post("/organization/person/edit",
                data={"name": "Bleibt Erhalten", "annual_salary": "100000", "fte": "1.0",
                      "organization_id": str(oid)}, follow_redirects=True)
    r = client.post(f"/organization/delete/{oid}", follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        from app.models import Organization, Person
        assert Organization.query.get(oid) is None
        p = Person.query.filter_by(name="Bleibt Erhalten").first()
        assert p is not None and p.organization_id is None


def test_viewer_cannot_delete_organization(app, client):
    """Löschen erfordert Organigramm-Verwaltungsrecht, nicht nur Ansicht."""
    from app.auth.permissions import P_DASHBOARD_VIEW
    make_account_with_role(app, "Viewer", {P_DASHBOARD_VIEW}, email="v2@test.ch")
    login(client, "v2@test.ch")
    assert client.post("/organization/delete/1").status_code == 403


def test_viewer_cannot_create_organization(app, client):
    from app.auth.permissions import P_DASHBOARD_VIEW
    make_account_with_role(app, "Viewer", {P_DASHBOARD_VIEW}, email="v@test.ch")
    login(client, "v@test.ch")
    assert client.post("/organization/edit", data={"name": "Hack"}).status_code == 403
