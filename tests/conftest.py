"""Gemeinsame Test-Fixtures & Helfer."""
import pytest


@pytest.fixture
def app(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret")

    from app import create_app
    from app.models import db

    application = create_app()
    application.config.update(TESTING=True)
    with application.app_context():
        db.create_all()
    return application


@pytest.fixture
def client(app):
    return app.test_client()


# ── Helfer ─────────────────────────────────────────────────────────────────
def make_account_with_role(app, role_name, permissions, email, password="password123",
                           is_super_admin=False, account_wide=True):
    """Erstellt Account, eine AccessRole mit gegebenen Permissions, User + Membership
    + accountweite RoleAssignment. Gibt (account_id, user_id, role_id) zurueck."""
    from app.models import (
        db, Account, User, Membership, AccessRole, AccessRolePermission, RoleAssignment,
    )
    from app.auth.service import set_password

    with app.app_context():
        acc = Account(name="TestAcc")
        db.session.add(acc)
        db.session.flush()

        role = AccessRole(account_id=acc.id, name=role_name)
        db.session.add(role)
        db.session.flush()
        for p in permissions:
            db.session.add(AccessRolePermission(access_role_id=role.id, permission_key=p))

        user = User(name="Test", email=email, is_super_admin=is_super_admin)
        set_password(user, password)
        db.session.add(user)
        db.session.flush()

        membership = Membership(user_id=user.id, account_id=acc.id)
        db.session.add(membership)
        db.session.flush()

        db.session.add(RoleAssignment(
            membership_id=membership.id, access_role_id=role.id,
            organization_id=None if account_wide else None))
        db.session.commit()
        return acc.id, user.id, role.id


def login(client, email, password="password123"):
    return client.post("/login", data={"email": email, "password": password},
                       follow_redirects=False)
