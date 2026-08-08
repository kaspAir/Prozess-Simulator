"""Drag'n'Drop-Zuordnung Person/Organisationseinheit → BPMN-Aktivität.

Deckt drei Ebenen ab:
- bpmn_assign: pros:-Attribute textuell setzen (bpmn-js-fest, DI unangetastet).
- assignment_service: Personen im Teilbaum + Funktionen-Schnittmenge + Rollen-Vereinigung.
- API /api/process/<id>/assign: kompletter Weg inkl. Persistenz + Anzeige.
"""
from app.auth.permissions import TEMPLATE_ROLES, ACCOUNT_ADMIN_ROLE
from app.services.bpmn_assign import set_activity_pros
from tests.conftest import make_account_with_role, login


# ── bpmn_assign (reine Logik, keine DB) ────────────────────────────────────
SELF_CLOSING = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="D" targetNamespace="x">'
    '<bpmn:process id="P"><bpmn:task id="A" name="Prüfen"/>'
    '<bpmn:task id="B" name="Buchen"/></bpmn:process></bpmn:definitions>'
)


def test_set_pros_injects_namespace_and_attr():
    xml, found = set_activity_pros(SELF_CLOSING, "A", personIds="5,7")
    assert found is True
    assert 'xmlns:pros="http://ditwi.ch/bpmn/pros"' in xml   # Namespace ergänzt
    assert 'pros:personIds="5,7"' in xml
    # Self-Close bleibt erhalten, andere Aktivität unberührt
    assert 'name="Prüfen" pros:personIds="5,7" />' in xml
    assert '<bpmn:task id="B" name="Buchen"/>' in xml


def test_set_pros_overwrites_existing():
    xml, _ = set_activity_pros(SELF_CLOSING, "A", roleIds="1")
    xml, _ = set_activity_pros(xml, "A", roleIds="2,3")
    assert 'pros:roleIds="2,3"' in xml
    assert 'pros:roleIds="1"' not in xml


def test_set_pros_empty_value_removes():
    xml, _ = set_activity_pros(SELF_CLOSING, "A", functionIds="9")
    assert 'pros:functionIds="9"' in xml
    xml, _ = set_activity_pros(xml, "A", functionIds="")
    assert "pros:functionIds" not in xml


def test_set_pros_unknown_activity_is_noop():
    xml, found = set_activity_pros(SELF_CLOSING, "DOES_NOT_EXIST", personIds="5")
    assert found is False
    assert xml == SELF_CLOSING


# ── assignment_service + API (mit DB) ──────────────────────────────────────
def _seed_org(app, account_id):
    """Abteilung mit zwei Stellen: Anna (F1,F2 / R1) und Ben (F1,F3 / R2)."""
    from app.models import db, Organization, OrgUnit, Person, Function, Role
    with app.app_context():
        org = Organization(account_id=account_id, name="Amt")
        db.session.add(org)
        db.session.flush()

        f1 = Function(account_id=account_id, name="F1")
        f2 = Function(account_id=account_id, name="F2")
        f3 = Function(account_id=account_id, name="F3")
        r1 = Role(account_id=account_id, name="R1")
        r2 = Role(account_id=account_id, name="R2")
        db.session.add_all([f1, f2, f3, r1, r2])
        db.session.flush()

        anna = Person(account_id=account_id, name="Anna", functions=[f1, f2], roles=[r1])
        ben = Person(account_id=account_id, name="Ben", functions=[f1, f3], roles=[r2])
        db.session.add_all([anna, ben])
        db.session.flush()

        abt = OrgUnit(organization_id=org.id, name="Abteilung", unit_type="Abteilung")
        db.session.add(abt)
        db.session.flush()
        s1 = OrgUnit(organization_id=org.id, name="Stelle 1", unit_type="Stelle",
                     parent_id=abt.id, person_id=anna.id)
        s2 = OrgUnit(organization_id=org.id, name="Stelle 2", unit_type="Stelle",
                     parent_id=abt.id, person_id=ben.id)
        db.session.add_all([s1, s2])
        db.session.commit()
        return {"abt": abt.id, "anna": anna.id, "ben": ben.id,
                "f1": f1.id, "r1": r1.id, "r2": r2.id}


def test_resolve_unit_intersection_and_union(app):
    acc, _, _ = make_account_with_role(app, ACCOUNT_ADMIN_ROLE,
                                       TEMPLATE_ROLES[ACCOUNT_ADMIN_ROLE], email="a1@test.ch")
    ids = _seed_org(app, acc)
    from app.services.assignment_service import resolve_assignment
    with app.app_context():
        res = resolve_assignment(acc, "unit", ids["abt"])
    assert sorted(res["person_ids"]) == sorted([ids["anna"], ids["ben"]])
    assert res["person_count"] == 2
    assert res["function_ids"] == [ids["f1"]]                 # Schnittmenge: nur F1
    assert sorted(res["role_ids"]) == sorted([ids["r1"], ids["r2"]])   # Vereinigung


def test_resolve_person(app):
    acc, _, _ = make_account_with_role(app, ACCOUNT_ADMIN_ROLE,
                                       TEMPLATE_ROLES[ACCOUNT_ADMIN_ROLE], email="a2@test.ch")
    ids = _seed_org(app, acc)
    from app.services.assignment_service import resolve_assignment
    with app.app_context():
        res = resolve_assignment(acc, "person", ids["anna"])
    assert res["person_ids"] == [ids["anna"]]
    assert res["role_ids"] == [ids["r1"]]
    assert len(res["function_ids"]) == 2                      # F1 + F2


def test_assign_api_end_to_end(app, client):
    acc, _, _ = make_account_with_role(app, ACCOUNT_ADMIN_ROLE,
                                       TEMPLATE_ROLES[ACCOUNT_ADMIN_ROLE], email="assign@test.ch")
    ids = _seed_org(app, acc)
    login(client, "assign@test.ch")
    # Prozess mit einer Aktivität "A" anlegen
    from app.models import db, Process
    with app.app_context():
        proc = Process(account_id=acc, name="Zuweisungsprozess", bpmn_xml=SELF_CLOSING)
        db.session.add(proc)
        db.session.commit()
        pid = proc.id

    r = client.post(f"/api/process/{pid}/assign",
                    json={"activity_id": "A", "source_type": "unit", "source_id": ids["abt"]})
    body = r.get_json()
    assert body["ok"] is True
    assert body["person_count"] == 2

    # Persistiert + in der Analyse sichtbar (Anna und Ben an Aktivität A)
    data = client.get(f"/api/process/{pid}/bpmn/analysis").get_json()
    act_a = next(a for a in data["activities"] if a["id"] == "A")
    names = sorted(p["name"] for p in act_a["persons"])
    assert names == ["Anna", "Ben"]


def test_assignment_page_lists_org_and_processes(app, client):
    acc, _, _ = make_account_with_role(app, ACCOUNT_ADMIN_ROLE,
                                       TEMPLATE_ROLES[ACCOUNT_ADMIN_ROLE], email="page@test.ch")
    _seed_org(app, acc)
    login(client, "page@test.ch")
    html = client.get("/assignment").get_data(as_text=True)
    assert "Abteilung" in html
    assert "Anna" in html
    assert 'data-type="unit"' in html and 'data-type="person"' in html
