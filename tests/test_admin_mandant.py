"""Mandanten-Verwaltung: Super-Admin legt Mandanten (Account) + Erst-Admin an;
Mandanten-Admin verwaltet (nur) die Mitglieder seines Mandanten inkl. Löschen."""
from app.auth.permissions import TEMPLATE_ROLES, ACCOUNT_ADMIN_ROLE, P_ACCOUNT_MEMBERS
from tests.conftest import make_account_with_role, login


def test_super_admin_creates_mandant_with_first_admin(app, client):
    make_account_with_role(app, ACCOUNT_ADMIN_ROLE, TEMPLATE_ROLES[ACCOUNT_ADMIN_ROLE],
                           email="super@test.ch", is_super_admin=True)
    login(client, "super@test.ch")
    r = client.post("/admin/accounts/create",
                    data={"name": "Schlichtungsgericht", "admin_name": "Kaspar Schlichtung",
                          "admin_email": "ks@test.ch", "admin_password": "password123"},
                    follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        from app.models import Account, AccessRole, User, Membership, RoleAssignment
        acc = Account.query.filter_by(name="Schlichtungsgericht").first()
        assert acc is not None
        # Vorlagen-Rollen wurden angelegt
        assert AccessRole.query.filter_by(account_id=acc.id, name=ACCOUNT_ADMIN_ROLE).first() is not None
        # Erst-Admin ist Mitglied mit accountweiter Admin-Rolle
        user = User.query.filter_by(email="ks@test.ch").first()
        m = Membership.query.filter_by(user_id=user.id, account_id=acc.id).first()
        assert m is not None
        asg = RoleAssignment.query.filter_by(membership_id=m.id, organization_id=None).first()
        assert asg is not None and P_ACCOUNT_MEMBERS in asg.access_role.permission_keys


def test_non_super_admin_cannot_create_mandant(app, client):
    make_account_with_role(app, ACCOUNT_ADMIN_ROLE, TEMPLATE_ROLES[ACCOUNT_ADMIN_ROLE],
                           email="normal@test.ch")
    login(client, "normal@test.ch")
    r = client.post("/admin/accounts/create", data={"name": "Fremd"})
    assert r.status_code == 403
    with app.app_context():
        from app.models import Account
        assert Account.query.filter_by(name="Fremd").first() is None


def test_admin_can_delete_member(app, client):
    acc, _, _ = make_account_with_role(app, ACCOUNT_ADMIN_ROLE, TEMPLATE_ROLES[ACCOUNT_ADMIN_ROLE],
                                       email="admin@test.ch")
    login(client, "admin@test.ch")
    # zweites Mitglied direkt anlegen
    with app.app_context():
        from app.models import db, User, Membership, AccessRole, RoleAssignment
        from app.auth.service import set_password
        u = User(name="Zweite", email="zwei@test.ch")
        set_password(u, "password123")
        db.session.add(u)
        db.session.flush()
        m = Membership(user_id=u.id, account_id=acc)
        db.session.add(m)
        db.session.flush()
        viewer = AccessRole(account_id=acc, name="Viewer")
        db.session.add(viewer)
        db.session.flush()
        db.session.add(RoleAssignment(membership_id=m.id, access_role_id=viewer.id, organization_id=None))
        db.session.commit()
        mid = m.id

    r = client.post(f"/admin/members/{mid}/delete", follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        from app.models import Membership, User
        assert Membership.query.get(mid) is None          # Mitgliedschaft weg
        assert User.query.filter_by(email="zwei@test.ch").first() is not None  # Benutzer bleibt


def test_cannot_delete_last_account_admin(app, client):
    acc, user_id, _ = make_account_with_role(app, ACCOUNT_ADMIN_ROLE,
                                             TEMPLATE_ROLES[ACCOUNT_ADMIN_ROLE], email="solo@test.ch")
    login(client, "solo@test.ch")
    with app.app_context():
        from app.models import Membership
        mid = Membership.query.filter_by(account_id=acc, user_id=user_id).first().id
    # Der einzige Account-Admin darf sich/den letzten Admin nicht entfernen
    r = client.post(f"/admin/members/{mid}/delete", follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        from app.models import Membership
        assert Membership.query.get(mid) is not None      # bleibt bestehen
