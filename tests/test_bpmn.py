"""BPMN-Phase-1: Editor-Seite + Load/Save-API (bpmn-js speichert BPMN-2.0-XML je Prozess)."""
from app.auth.permissions import TEMPLATE_ROLES, ACCOUNT_ADMIN_ROLE, P_DASHBOARD_VIEW
from tests.conftest import make_account_with_role, login

SAMPLE_BPMN = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
    'id="Definitions_X" targetNamespace="http://bpmn.io/schema/bpmn">'
    '<bpmn:process id="Process_X" isExecutable="false">'
    '<bpmn:startEvent id="StartEvent_MARKER"/>'
    '<bpmn:parallelGateway id="Gateway_AND"/>'
    '</bpmn:process></bpmn:definitions>'
)


def _admin_with_process(app, client):
    make_account_with_role(app, ACCOUNT_ADMIN_ROLE, TEMPLATE_ROLES[ACCOUNT_ADMIN_ROLE],
                           email="bpmn-admin@test.ch")
    login(client, "bpmn-admin@test.ch")
    client.post("/processes/new", data={"name": "BPMN Prozess"}, follow_redirects=True)
    with app.app_context():
        from app.models import Process
        return Process.query.filter_by(name="BPMN Prozess").first().id


def test_bpmn_editor_page_ok(app, client):
    pid = _admin_with_process(app, client)
    resp = client.get(f"/process/{pid}/bpmn")
    assert resp.status_code == 200
    assert "bpmn-modeler.production.min.js" in resp.get_data(as_text=True)


def test_bpmn_default_diagram_returned(app, client):
    pid = _admin_with_process(app, client)
    resp = client.get(f"/api/process/{pid}/bpmn")
    assert resp.status_code == 200
    assert "bpmn:definitions" in resp.get_data(as_text=True)


def test_bpmn_save_and_reload_roundtrip(app, client):
    pid = _admin_with_process(app, client)
    r = client.post(f"/api/process/{pid}/bpmn", json={"xml": SAMPLE_BPMN})
    assert r.get_json()["ok"] is True
    reloaded = client.get(f"/api/process/{pid}/bpmn").get_data(as_text=True)
    assert "StartEvent_MARKER" in reloaded
    assert "parallelGateway" in reloaded   # AND-Gateway wurde persistiert


def test_bpmn_save_rejects_non_bpmn(app, client):
    pid = _admin_with_process(app, client)
    r = client.post(f"/api/process/{pid}/bpmn", json={"xml": "kein xml"})
    assert r.status_code == 400
    assert r.get_json()["ok"] is False


def test_bpmn_xor_probability_persists(app, client):
    """XOR-Pfad-Wahrscheinlichkeit (pros:probability) bleibt im gespeicherten BPMN erhalten."""
    pid = _admin_with_process(app, client)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
        'xmlns:pros="http://ditwi.ch/bpmn/pros" id="Definitions_P" '
        'targetNamespace="http://bpmn.io/schema/bpmn">'
        '<bpmn:process id="Process_P" isExecutable="false">'
        '<bpmn:exclusiveGateway id="GW"/>'
        '<bpmn:sequenceFlow id="f1" sourceRef="GW" targetRef="T1" pros:probability="60"/>'
        '</bpmn:process></bpmn:definitions>'
    )
    assert client.post(f"/api/process/{pid}/bpmn", json={"xml": xml}).get_json()["ok"] is True
    reloaded = client.get(f"/api/process/{pid}/bpmn").get_data(as_text=True)
    assert 'pros:probability="60"' in reloaded


TASK_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
    'xmlns:pros="http://ditwi.ch/bpmn/pros" id="D" targetNamespace="x">'
    '<bpmn:process id="P"><bpmn:startEvent id="S"/>'
    '<bpmn:task id="A" name="Prüfen" pros:effortMinutes="30"/>'
    '<bpmn:sequenceFlow id="s1" sourceRef="S" targetRef="A"/>'
    '</bpmn:process></bpmn:definitions>'
)


def test_bpmn_analysis_api(app, client):
    pid = _admin_with_process(app, client)
    client.post(f"/api/process/{pid}/bpmn", json={"xml": TASK_XML})
    data = client.get(f"/api/process/{pid}/bpmn/analysis").get_json()
    assert data["has_model"] is True
    assert abs(data["total_effort"] - 30) < 1e-6
    assert data["activities"][0]["name"] == "Prüfen"


def test_dashboard_shows_bpmn_summary(app, client):
    pid = _admin_with_process(app, client)
    client.post(f"/api/process/{pid}/bpmn", json={"xml": TASK_XML})
    html = client.get("/dashboard").get_data(as_text=True)
    assert "Aufwand &amp; Kosten je Prozess" in html
    assert "BPMN Prozess" in html


def test_process_type_saved_and_on_map(app, client):
    """Prozesstyp wird gespeichert und erscheint in der Prozesslandkarte."""
    pid = _admin_with_process(app, client)
    client.post(f"/processes/{pid}",
                data={"name": "BPMN Prozess", "priority": 2, "process_type": "Kernprozess"},
                follow_redirects=True)
    with app.app_context():
        from app.models import Process
        assert Process.query.get(pid).process_type == "Kernprozess"
    assert "Kernprozess" in client.get("/process-map").get_data(as_text=True)


def test_bpmn_import_creates_process_on_map(app, client):
    """Import legt einen neuen Hauptprozess an (mit Typ) und öffnet ihn; er
    erscheint danach in der Prozesslandkarte."""
    make_account_with_role(app, ACCOUNT_ADMIN_ROLE, TEMPLATE_ROLES[ACCOUNT_ADMIN_ROLE],
                           email="import-admin@test.ch")
    login(client, "import-admin@test.ch")
    r = client.post("/api/processes/import",
                    json={"name": "Importierter Prozess", "process_type": "Kernprozess",
                          "xml": TASK_XML})
    body = r.get_json()
    assert body["ok"] is True
    assert "/bpmn" in body["redirect"]
    with app.app_context():
        from app.models import Process
        p = Process.query.get(body["id"])
        assert p.parent_process_id is None            # Hauptprozess -> in der Landkarte
        assert p.process_type == "Kernprozess"
        assert "Prüfen" in (p.bpmn_xml or "")
    assert "Importierter Prozess" in client.get("/process-map").get_data(as_text=True)


def test_bpmn_import_rejects_non_bpmn(app, client):
    make_account_with_role(app, ACCOUNT_ADMIN_ROLE, TEMPLATE_ROLES[ACCOUNT_ADMIN_ROLE],
                           email="import-admin2@test.ch")
    login(client, "import-admin2@test.ch")
    assert client.post("/api/processes/import",
                       json={"name": "X", "xml": "kein xml"}).status_code == 400
    assert client.post("/api/processes/import",
                       json={"name": "", "xml": TASK_XML}).status_code == 400


def test_bpmn_save_requires_manage_permission(app, client):
    make_account_with_role(app, "Viewer", {P_DASHBOARD_VIEW}, email="bpmn-viewer@test.ch")
    login(client, "bpmn-viewer@test.ch")
    # Viewer darf nicht speichern (POST => Prozess-Verwaltungsrecht nötig)
    assert client.post("/api/process/1/bpmn", json={"xml": SAMPLE_BPMN}).status_code == 403
