"""Smoke-Tests: Die App muss bauen und die Kern-Routen muessen antworten.

Dient Jenkins als Build-Gate. Nutzt eine temporaere SQLite-DB, damit kein
DB-Server noetig ist.
"""
import pytest


@pytest.fixture
def app(tmp_path, monkeypatch):
    db_file = tmp_path / "smoke.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret")

    from app import create_app
    from app.models import db

    application = create_app()
    with application.app_context():
        db.create_all()
    return application


@pytest.fixture
def client(app):
    return app.test_client()


def test_index_redirects_to_dashboard(client):
    resp = client.get("/")
    assert resp.status_code in (301, 302)
    assert "/dashboard" in resp.headers["Location"]


def test_dashboard_ok(client):
    assert client.get("/dashboard").status_code == 200


def test_process_list_ok(client):
    assert client.get("/processes").status_code == 200


def test_process_map_ok(client):
    assert client.get("/process-map").status_code == 200


def test_organization_ok(client):
    # organization_bp hat url_prefix="/organization"
    assert client.get("/organization/", follow_redirects=True).status_code == 200


def test_bpmn_editor_reachable(client):
    # Stellt sicher, dass die BPMN-Editor-Route registriert ist.
    assert client.get("/bpmn").status_code == 200
