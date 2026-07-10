"""Gestufte Testfälle aus dem TC-Katalog «Testfälle DigiTwin V0.1» (TC-001..025).

Diese Fälle laufen NICHT auf dev (schnelle Suite), sondern erst ab Umgebung
**test** – gesteuert über den Marker `teststufe` (siehe pytest.ini und Jenkinsfile).
Sie sind deterministisch und laufen gegen die eigene DB (Schnittstellenmodus mock).

Noch nicht automatisierbare Fälle (fehlende Funktion oder kein deterministisches
Testorakel) sind bewusst als `skip` mit Begründung markiert – sie erscheinen so
transparent als «übersprungen» im Testprotokoll und können später ausgebaut werden.
"""
import pytest

from app.auth.permissions import TEMPLATE_ROLES, ACCOUNT_ADMIN_ROLE
from tests.conftest import make_account_with_role, login

pytestmark = pytest.mark.teststufe


# ── Helfer ──────────────────────────────────────────────────────────────────
def _admin(app, client, email="tc-admin@test.ch"):
    acc_id, _, _ = make_account_with_role(
        app, ACCOUNT_ADMIN_ROLE, TEMPLATE_ROLES[ACCOUNT_ADMIN_ROLE], email=email)
    login(client, email)
    return acc_id


def _create_org(client, name):
    client.post("/organization/edit", data={"name": name}, follow_redirects=True)


def _org_id(app, name):
    with app.app_context():
        from app.models import Organization
        return Organization.query.filter_by(name=name).first().id


def _new_account(app):
    from app.models import db, Account
    with app.app_context():
        acc = Account(name="SimAcc")
        db.session.add(acc)
        db.session.commit()
        return acc.id


def _build_sim(app, acc_id, fte=0.8, effort=45.0, n_positions=1, proc_name="Hauptprozess Strafbefehl"):
    """Baut ein simulierbares Minimalmodell: Organisation, Stelle(n) mit Person(en),
    Prozess mit Start -> Aktivität -> Ende und zugeordneten Stellen. Gibt process_id."""
    from app.models import db, Organization, OrgUnit, Person, Process, Node, Edge
    with app.app_context():
        org = Organization(name="SimOrg", account_id=acc_id)
        db.session.add(org)
        db.session.flush()

        proc = Process(name=proc_name, account_id=acc_id)
        db.session.add(proc)
        db.session.flush()

        start = Node(process=proc, type="start", name="Start", sort_order=0)
        task = Node(process=proc, type="task", name="Straftatbestand festlegen",
                    effort_minutes=effort, sort_order=1)
        end = Node(process=proc, type="end", name="Ende", sort_order=2)
        db.session.add_all([start, task, end])
        db.session.flush()

        db.session.add(Edge(source_node_id=start.id, target_node_id=task.id))
        db.session.add(Edge(source_node_id=task.id, target_node_id=end.id))

        positions = []
        for i in range(n_positions):
            person = Person(name=f"Person {i}", account_id=acc_id, organization_id=org.id,
                            fte=fte, annual_salary=95000, active=True)
            db.session.add(person)
            db.session.flush()
            pos = OrgUnit(organization_id=org.id, name=f"Stelle {i}",
                          unit_type="Stelle", person_id=person.id)
            db.session.add(pos)
            db.session.flush()
            positions.append(pos)

        task.assigned_positions = positions
        db.session.commit()
        return proc.id


def _simulate(app, process_id, case_count):
    from app.models import Process
    from app.simulation import simulate_end_to_end
    with app.app_context():
        return simulate_end_to_end(Process.query.get(process_id), case_count)


# ── UC-001/002/003: Organisation modellieren ────────────────────────────────
def test_tc_001_neue_organisation_vollstaendig_modellieren(app, client):
    _admin(app, client)
    _create_org(client, "Staatsanwaltschaft Musterkanton")
    oid = _org_id(app, "Staatsanwaltschaft Musterkanton")
    client.post("/organization/unit/edit",
                data={"name": "Zentrale Dienste", "unit_type": "Abteilung",
                      "organization_id": str(oid)}, follow_redirects=True)
    client.post("/organization/person/edit",
                data={"name": "Anna Keller", "annual_salary": "95000", "fte": "0.8",
                      "organization_id": str(oid)}, follow_redirects=True)
    html = client.get(f"/organization/?org_id={oid}").get_data(as_text=True)
    assert "Zentrale Dienste" in html
    assert "Anna Keller" in html


def test_tc_002_vorhandenes_organisationsmodell_aendern(app, client):
    _admin(app, client)
    _create_org(client, "Org Alpha")
    oid = _org_id(app, "Org Alpha")
    client.post("/organization/unit/edit",
                data={"name": "Cyberkriminalitaet", "unit_type": "Team",
                      "organization_id": str(oid)}, follow_redirects=True)
    client.post("/organization/role/edit", data={"name": "Leiterin Kanzlei"},
                follow_redirects=True)
    with app.app_context():
        from app.models import Role
        rid = Role.query.filter_by(name="Leiterin Kanzlei").first().id
    client.post(f"/organization/role/edit/{rid}", data={"name": "Leiterin Kanzlei neu"},
                follow_redirects=True)
    html = client.get(f"/organization/?org_id={oid}").get_data(as_text=True)
    assert "Cyberkriminalitaet" in html
    assert "Leiterin Kanzlei neu" in html


def test_tc_003_neue_organisationseinheit_anlegen(app, client):
    _admin(app, client)
    _create_org(client, "Org Beta")
    oid = _org_id(app, "Org Beta")
    client.post("/organization/unit/edit",
                data={"name": "Cyberkriminalitaet", "unit_type": "Team",
                      "organization_id": str(oid)}, follow_redirects=True)
    with app.app_context():
        from app.models import OrgUnit
        unit = OrgUnit.query.filter_by(name="Cyberkriminalitaet").first()
        assert unit is not None and unit.organization_id == oid


def test_tc_004_person_mit_rolle_und_fte_erfassen(app, client):
    _admin(app, client)
    _create_org(client, "Org Gamma")
    oid = _org_id(app, "Org Gamma")
    client.post("/organization/role/edit", data={"name": "Juristische Mitarbeiterin"},
                follow_redirects=True)
    with app.app_context():
        from app.models import Role
        rid = Role.query.filter_by(name="Juristische Mitarbeiterin").first().id
    client.post("/organization/person/edit",
                data={"name": "Anna Keller", "annual_salary": "95000", "fte": "0.8",
                      "organization_id": str(oid), "role_ids": str(rid)},
                follow_redirects=True)
    with app.app_context():
        from app.models import Person
        p = Person.query.filter_by(name="Anna Keller").first()
        assert p is not None
        assert abs((p.fte or 0) - 0.8) < 1e-6
        assert abs((p.annual_salary or 0) - 95000) < 1e-6
        assert any(r.id == rid for r in p.roles)


def test_tc_005_ungueltige_fte_eingabe_pruefen(app, client):
    _admin(app, client)
    _create_org(client, "Org Delta")
    oid = _org_id(app, "Org Delta")
    client.post("/organization/person/edit",
                data={"name": "Julia Weber", "annual_salary": "80000", "fte": "1.5",
                      "organization_id": str(oid)}, follow_redirects=True)
    with app.app_context():
        from app.models import Person
        assert Person.query.filter_by(name="Julia Weber").first() is None


# ── UC-004: Prozessmodell bearbeiten ────────────────────────────────────────
def _new_process(app, client, name="Hauptprozess Strafbefehl"):
    client.post("/processes/new", data={"name": name}, follow_redirects=True)
    with app.app_context():
        from app.models import Process, Node
        proc = Process.query.filter_by(name=name).first()
        nodes = Node.query.filter_by(process_id=proc.id).all()
        start = next((n for n in nodes if n.type == "start"), None)
        end = next((n for n in nodes if n.type == "end"), None)
        return proc.id, (start.id if start else None), (end.id if end else None)


def test_tc_006_neue_aktivitaet_einfuegen_und_verbinden(app, client):
    _admin(app, client)
    pid, start_id, end_id = _new_process(app, client)
    client.post(f"/process/{pid}/nodes/new",
                data={"name": "Dokumentenpruefung", "type": "task",
                      "effort_minutes": "20", "sort_order": "1"}, follow_redirects=True)
    with app.app_context():
        from app.models import Node
        node = Node.query.filter_by(name="Dokumentenpruefung").first()
        assert node is not None
        nid = node.id
    # verbinden: Start -> neue Aktivität
    client.post(f"/process/{pid}/edges/new",
                data={"source_node_id": str(start_id), "target_node_id": str(nid)},
                follow_redirects=True)
    with app.app_context():
        from app.models import Edge
        assert Edge.query.filter_by(source_node_id=start_id, target_node_id=nid).first() is not None


def test_tc_007_reihenfolge_von_prozessschritten_aendern(app, client):
    _admin(app, client)
    pid, _, _ = _new_process(app, client, name="Prozess Reihenfolge")
    client.post(f"/process/{pid}/nodes/new",
                data={"name": "Schritt A", "type": "task", "sort_order": "1"},
                follow_redirects=True)
    client.post(f"/process/{pid}/nodes/new",
                data={"name": "Schritt B", "type": "task", "sort_order": "2"},
                follow_redirects=True)
    with app.app_context():
        from app.models import Node
        a = Node.query.filter_by(name="Schritt A").first()
    # A ans Ende schieben (sort_order 9)
    client.post(f"/process/{pid}/nodes/{a.id}",
                data={"name": "Schritt A", "type": "task", "sort_order": "9"},
                follow_redirects=True)
    with app.app_context():
        from app.models import Node
        order = [n.name for n in Node.query.filter_by(process_id=pid)
                 .order_by(Node.sort_order).all() if n.name in ("Schritt A", "Schritt B")]
        assert order == ["Schritt B", "Schritt A"]


def test_tc_008_gateway_in_modell_einfuegen(app, client):
    _admin(app, client)
    pid, start_id, end_id = _new_process(app, client, name="Prozess Gateway")
    client.post(f"/process/{pid}/nodes/new",
                data={"name": "Unterlagen vollstaendig?", "type": "xor", "sort_order": "1"},
                follow_redirects=True)
    client.post(f"/process/{pid}/nodes/new",
                data={"name": "Pfad Ja", "type": "task", "sort_order": "2"},
                follow_redirects=True)
    client.post(f"/process/{pid}/nodes/new",
                data={"name": "Pfad Nein", "type": "task", "sort_order": "3"},
                follow_redirects=True)
    with app.app_context():
        from app.models import Node
        xor = Node.query.filter_by(name="Unterlagen vollstaendig?").first()
        ja = Node.query.filter_by(name="Pfad Ja").first()
        nein = Node.query.filter_by(name="Pfad Nein").first()
        xid, jid, nid = xor.id, ja.id, nein.id
    client.post(f"/process/{pid}/edges/new",
                data={"source_node_id": str(xid), "target_node_id": str(jid)},
                follow_redirects=True)
    client.post(f"/process/{pid}/edges/new",
                data={"source_node_id": str(xid), "target_node_id": str(nid)},
                follow_redirects=True)
    with app.app_context():
        from app.models import Edge
        outgoing = Edge.query.filter_by(source_node_id=xid).all()
        assert len(outgoing) == 2
        conditions = {e.condition for e in outgoing}
        assert conditions == {"Ja", "Nein"}
        assert sum((e.probability_percent or 0) for e in outgoing) == 100


# ── UC-005: Aktivitätsdauern / Kapazitäten ──────────────────────────────────
def test_tc_009_ungueltige_dauerwerte_validieren(app, client):
    _admin(app, client)
    pid, _, _ = _new_process(app, client, name="Prozess Dauer")
    client.post(f"/process/{pid}/nodes/new",
                data={"name": "NegativDauer", "type": "task", "effort_minutes": "-15"},
                follow_redirects=True)
    with app.app_context():
        from app.models import Node
        node = Node.query.filter_by(name="NegativDauer").first()
        assert node is not None and (node.effort_minutes or 0) >= 0


# ── UC-006: Prozesse analysieren ────────────────────────────────────────────
def test_tc_010_vorhandenen_prozess_analysieren(app, client):
    _admin(app, client)
    pid, _, _ = _new_process(app, client, name="Hauptprozess Strafbefehl")
    client.post(f"/process/{pid}/nodes/new",
                data={"name": "Straftatbestand festlegen", "type": "task",
                      "effort_minutes": "45", "sort_order": "1"}, follow_redirects=True)
    html = client.get(f"/process/{pid}").get_data(as_text=True)
    assert html and "Straftatbestand festlegen" in html


# ── UC-007/008/009: Ressourcen / Engpässe / Simulation ──────────────────────
def test_tc_011_kapazitaetsengpass_erkennen(app):
    acc = _new_account(app)
    pid = _build_sim(app, acc, fte=0.8, effort=45.0)
    res = _simulate(app, pid, 30000)   # hohe Last
    assert res["feasible"] is False


def test_tc_012_ausreichende_kapazitaet_erkennen(app):
    acc = _new_account(app)
    pid = _build_sim(app, acc, fte=0.8, effort=45.0)
    res = _simulate(app, pid, 1000)    # geringe Last
    assert res["feasible"] is True


@pytest.mark.skip(reason="Auswertung je Organisationseinheit (Filter) noch nicht als "
                         "Funktion vorhanden – TC-013")
def test_tc_013_ressourcenzuordnung_nach_einheit(app):
    pass


def test_tc_014_engpass_durch_ueberlastung_erkennen(app):
    acc = _new_account(app)
    pid = _build_sim(app, acc, fte=0.8, effort=45.0)
    res = _simulate(app, pid, 30000)
    assert any(not row["ok"] for row in res["person_rows"])


def test_tc_015_simulation_mit_bestehenden_daten_starten(app):
    acc = _new_account(app)
    pid = _build_sim(app, acc, fte=0.8, effort=45.0)
    res = _simulate(app, pid, 1000)
    assert "feasible" in res and res["person_rows"]


def test_tc_016_veraenderung_personalkapazitaet_simulieren(app):
    acc = _new_account(app)
    pid = _build_sim(app, acc, fte=0.6, effort=45.0)
    cap_low = _simulate(app, pid, 1000)["total_capacity_minutes"]
    with app.app_context():
        from app.models import db, Person
        person = Person.query.filter_by(name="Person 0").first()
        person.fte = 1.0
        db.session.commit()
    cap_high = _simulate(app, pid, 1000)["total_capacity_minutes"]
    assert cap_high > cap_low


def test_tc_017_veraenderung_aktivitaetsdauern_simulieren(app):
    acc = _new_account(app)
    pid = _build_sim(app, acc, fte=0.8, effort=45.0)
    req_before = _simulate(app, pid, 1000)["total_expected_minutes"]
    with app.app_context():
        from app.models import db, Node
        node = Node.query.filter_by(name="Straftatbestand festlegen").first()
        node.effort_minutes = 30.0
        db.session.commit()
    req_after = _simulate(app, pid, 1000)["total_expected_minutes"]
    assert req_after < req_before


def test_tc_018_zusaetzliche_stelle_simulieren(app):
    acc = _new_account(app)
    pid_one = _build_sim(app, acc, fte=0.8, effort=45.0, n_positions=1)
    cap_one = _simulate(app, pid_one, 1000)["total_capacity_minutes"]
    pid_two = _build_sim(app, acc, fte=0.8, effort=45.0, n_positions=2,
                         proc_name="Hauptprozess Strafbefehl 2")
    cap_two = _simulate(app, pid_two, 1000)["total_capacity_minutes"]
    assert cap_two > cap_one


@pytest.mark.skip(reason="Auswirkung der Rollen-Umverteilung braucht ein tieferes "
                         "Bewertungsorakel – TC-019 (später)")
def test_tc_019_andere_rollenverteilung_simulieren(app):
    pass


# ── UC-011: Dashboard / Ergebnisse ──────────────────────────────────────────
def test_tc_020_simulationsergebnisse_im_dashboard_anzeigen(app, client):
    acc_id = _admin(app, client, email="tc20@test.ch")
    _build_sim(app, acc_id, fte=0.8, effort=45.0)
    resp = client.get("/dashboard?tab=operational")
    assert resp.status_code == 200
    assert "Hauptprozess Strafbefehl" in resp.get_data(as_text=True)


# ── UC-013: Export (noch nicht implementiert) ───────────────────────────────
@pytest.mark.skip(reason="Export-Funktion (JSON) noch nicht implementiert – TC-021")
def test_tc_021_modell_als_json_exportieren(app):
    pass


@pytest.mark.skip(reason="Export-Funktion (XML) noch nicht implementiert – TC-022")
def test_tc_022_modell_als_xml_exportieren(app):
    pass


@pytest.mark.skip(reason="Export-Vollstaendigkeit setzt Export-Funktion voraus – TC-023")
def test_tc_023_vollstaendigkeit_des_exports_pruefen(app):
    pass


# ── UC-014: Organisationsentwicklung ────────────────────────────────────────
def test_tc_024_gesamtsicht_der_organisation_bereitstellen(app, client):
    _admin(app, client)
    _create_org(client, "Gesamtsicht Org")
    oid = _org_id(app, "Gesamtsicht Org")
    client.post("/organization/unit/edit",
                data={"name": "Abteilung X", "unit_type": "Abteilung",
                      "organization_id": str(oid)}, follow_redirects=True)
    client.post("/organization/person/edit",
                data={"name": "Max Muster", "annual_salary": "90000", "fte": "1.0",
                      "organization_id": str(oid)}, follow_redirects=True)
    resp = client.get(f"/organization/?org_id={oid}")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Abteilung X" in html and "Max Muster" in html


@pytest.mark.skip(reason="Ableitung von Verbesserungspotenzialen ist explorativ/analytisch "
                         "und hat kein deterministisches Testorakel – TC-025 (Mensch/Agent)")
def test_tc_025_verbesserungspotenziale_ableiten(app):
    pass
