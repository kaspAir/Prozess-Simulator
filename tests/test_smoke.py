"""Smoke-Tests: App baut, Login-Wall greift, Kern-Routen antworten fuer
einen eingeloggten Account-Admin. Build-Gate fuer Jenkins."""
from app.auth.permissions import TEMPLATE_ROLES, ACCOUNT_ADMIN_ROLE
from tests.conftest import make_account_with_role, login


def _admin(app):
    return make_account_with_role(
        app, ACCOUNT_ADMIN_ROLE, TEMPLATE_ROLES[ACCOUNT_ADMIN_ROLE],
        email="admin@test.ch")


def test_unauthenticated_redirects_to_login(client):
    resp = client.get("/dashboard")
    assert resp.status_code in (301, 302)
    assert "/login" in resp.headers["Location"]


def test_login_page_ok(client):
    assert client.get("/login").status_code == 200


def test_health_ok_without_login(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert data["version"]


def test_dashboard_ok_when_logged_in(app, client):
    _admin(app)
    login(client, "admin@test.ch")
    assert client.get("/dashboard").status_code == 200


def test_core_routes_ok_when_logged_in(app, client):
    _admin(app)
    login(client, "admin@test.ch")
    for url in ["/processes", "/process-map", "/organization/"]:
        assert client.get(url, follow_redirects=True).status_code == 200


def test_appearance_page_lists_all_themes(app, client):
    _admin(app)
    login(client, "admin@test.ch")
    html = client.get("/appearance").get_data(as_text=True)
    for token in ['data-theme="standard"', 'data-theme="kanzlei"',
                  'data-theme="signal"', 'data-theme="twin"', "themes.css"]:
        assert token in html
