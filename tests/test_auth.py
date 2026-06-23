"""Auth-/Berechtigungs-Tests."""
from app.auth.permissions import (
    TEMPLATE_ROLES, ACCOUNT_ADMIN_ROLE,
    P_DASHBOARD_VIEW, P_PERSONS_MANAGE, P_PROCESSES_MANAGE, P_ACCOUNT_MEMBERS,
)
from tests.conftest import make_account_with_role, login


# ── Permission-Enforcement ─────────────────────────────────────────────────
def test_viewer_can_view_but_not_edit(app, client):
    make_account_with_role(app, "Viewer", {P_DASHBOARD_VIEW}, email="viewer@test.ch")
    login(client, "viewer@test.ch")

    assert client.get("/dashboard").status_code == 200
    assert client.get("/processes").status_code == 200          # Lesen erlaubt
    # Schreiben (Prozess anlegen) verboten
    assert client.post("/processes/new", data={"name": "X"}).status_code == 403
    # Mitarbeitende bearbeiten verboten (persons.manage fehlt)
    assert client.get("/organization/person/edit").status_code == 403


def test_process_editor_can_create(app, client):
    make_account_with_role(app, "Prozess-Editor", TEMPLATE_ROLES["Prozess-Editor"],
                           email="ped@test.ch")
    login(client, "ped@test.ch")
    # GET-Formular erreichbar, und POST nicht 403 (Redirect nach Anlegen)
    resp = client.post("/processes/new", data={"name": "Neu"}, follow_redirects=False)
    assert resp.status_code != 403


# ── "mindestens ein Account-Admin" ─────────────────────────────────────────
def test_last_account_admin_protected(app):
    acc_id, user_id, _ = make_account_with_role(
        app, ACCOUNT_ADMIN_ROLE, TEMPLATE_ROLES[ACCOUNT_ADMIN_ROLE], email="a1@test.ch")
    with app.app_context():
        from app.models import Membership
        from app.auth.service import is_last_account_admin
        m = Membership.query.filter_by(account_id=acc_id, user_id=user_id).first()
        assert is_last_account_admin(m) is True


# ── Pro-Organisation-Zuweisung ─────────────────────────────────────────────
def test_per_organization_scope(app):
    with app.app_context():
        from app.models import (
            db, Account, Organization, User, Membership, AccessRole,
            AccessRolePermission, RoleAssignment,
        )
        from app.auth.service import set_password, user_has_permission

        acc = Account(name="Acc"); db.session.add(acc); db.session.flush()
        org_a = Organization(name="A", account_id=acc.id)
        org_b = Organization(name="B", account_id=acc.id)
        db.session.add_all([org_a, org_b]); db.session.flush()

        role = AccessRole(account_id=acc.id, name="PersEditor"); db.session.add(role); db.session.flush()
        db.session.add(AccessRolePermission(access_role_id=role.id, permission_key=P_PERSONS_MANAGE))

        user = User(name="U", email="u@test.ch"); set_password(user, "password123")
        db.session.add(user); db.session.flush()
        m = Membership(user_id=user.id, account_id=acc.id); db.session.add(m); db.session.flush()
        # Rolle NUR fuer Organisation A
        db.session.add(RoleAssignment(membership_id=m.id, access_role_id=role.id,
                                      organization_id=org_a.id))
        db.session.commit()

        assert user_has_permission(user, P_PERSONS_MANAGE, organization_id=org_a.id, account=acc) is True
        assert user_has_permission(user, P_PERSONS_MANAGE, organization_id=org_b.id, account=acc) is False


# ── Einladung ──────────────────────────────────────────────────────────────
def test_accept_invitation_creates_membership(app):
    acc_id, _, role_id = make_account_with_role(
        app, ACCOUNT_ADMIN_ROLE, TEMPLATE_ROLES[ACCOUNT_ADMIN_ROLE], email="host@test.ch")
    with app.app_context():
        from app.models import User, Membership
        from app.auth.service import create_invitation, accept_invitation

        inv = create_invitation(acc_id, "new@test.ch", role_id, organization_id=None)
        user, err = accept_invitation(inv.token, "Neu", "password123")
        assert err is None
        assert user is not None
        m = Membership.query.filter_by(user_id=user.id, account_id=acc_id).first()
        assert m is not None
