"""Angemeldeter Nutzer ohne wirksame Rolle bekommt die freundliche 403-Seite
(nicht die nackte Werkzeug-Meldung) – und einen 403-Status."""
from tests.conftest import login


def _user_without_role(app, email="daniel@ditwi.ch", password="password123"):
    from app.models import db, Account, User, Membership
    from app.auth.service import set_password
    with app.app_context():
        acc = Account(name="Staatsanwaltschaft Musterkanton")
        db.session.add(acc)
        db.session.flush()
        user = User(name="Daniel Kettiger", email=email)
        set_password(user, password)
        db.session.add(user)
        db.session.flush()
        db.session.add(Membership(user_id=user.id, account_id=acc.id))  # KEINE Rolle
        db.session.commit()


def test_logged_in_without_role_gets_friendly_403(app, client):
    _user_without_role(app)
    login(client, "daniel@ditwi.ch")
    r = client.get("/dashboard")
    assert r.status_code == 403
    body = r.get_data(as_text=True)
    assert "keine Rolle" in body                     # freundlicher Text
    assert "Staatsanwaltschaft Musterkanton" in body  # Account genannt
    assert "You don't have the permission" not in body  # nicht die Werkzeug-Seite


def test_anonymous_403_redirects_to_login(app, client):
    # Ohne Login greift zwar schon die Login-Wall; der Handler bleibt dennoch robust.
    r = client.get("/dashboard", follow_redirects=False)
    assert r.status_code in (302, 401, 403)
    if r.status_code == 302:
        assert "/login" in r.headers.get("Location", "")
