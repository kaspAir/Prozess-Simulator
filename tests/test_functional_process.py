"""Fachliche End-to-End-Testfälle (deterministisch).

Muster für die wachsende Testfall-Sammlung: hier «einen Prozess erfassen und
Nodes darin anlegen». Läuft heute gegen die eigene DB (Schnittstellenmodus mock).
Später können solche Fälle YAML-/Agent-generiert entstehen – die Ausführung und
das Pass/Fail-Urteil bleiben in jedem Fall deterministisch (Test-Runner).
"""
from app.auth.permissions import TEMPLATE_ROLES, ACCOUNT_ADMIN_ROLE
from tests.conftest import make_account_with_role, login


def _admin(app, client):
    make_account_with_role(app, ACCOUNT_ADMIN_ROLE, TEMPLATE_ROLES[ACCOUNT_ADMIN_ROLE],
                           email="admin@test.ch")
    login(client, "admin@test.ch")


def test_create_process_and_add_nodes(app, client):
    _admin(app, client)

    # 1) Prozess erfassen
    r = client.post("/processes/new", data={"name": "Strafbefehl"}, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        from app.models import Process, Node
        proc = Process.query.filter_by(name="Strafbefehl").first()
        assert proc is not None
        pid = proc.id
        # Beim Anlegen entstehen automatisch Start- und Ende-Node
        assert Node.query.filter_by(process_id=pid).count() >= 2

    # 2) Aktivität (Node) erfassen
    r2 = client.post(
        f"/process/{pid}/nodes/new",
        data={"name": "Straftatbestand festlegen", "type": "task",
              "effort_minutes": "45", "sort_order": "1"},
        follow_redirects=True,
    )
    assert r2.status_code == 200
    with app.app_context():
        from app.models import Node
        node = Node.query.filter_by(name="Straftatbestand festlegen").first()
        assert node is not None and node.process_id == pid
        assert abs((node.effort_minutes or 0) - 45.0) < 0.001

    # 3) Prozessansicht zeigt den neuen Node
    graph = client.get(f"/process/{pid}").get_data(as_text=True)
    assert "Straftatbestand festlegen" in graph


def test_negative_node_effort_is_clamped(app, client):
    """B-04 fachlich abgesichert: negativer Aufwand wird nicht gespeichert."""
    _admin(app, client)
    client.post("/processes/new", data={"name": "P2"}, follow_redirects=True)
    with app.app_context():
        from app.models import Process
        pid = Process.query.filter_by(name="P2").first().id
    client.post(f"/process/{pid}/nodes/new",
                data={"name": "NegativNode", "type": "task", "effort_minutes": "-15"},
                follow_redirects=True)
    with app.app_context():
        from app.models import Node
        node = Node.query.filter_by(name="NegativNode").first()
        assert node is not None and (node.effort_minutes or 0) >= 0
