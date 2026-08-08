"""Mandantenfaehigkeit: Ein auf eine Organisation beschraenkter Nutzer darf die
Existenz/Namen anderer Organisationen (Mandanten) nicht sehen und nicht dorthin
wechseln."""
from app.auth.permissions import P_DASHBOARD_VIEW
from tests.conftest import login


def _per_org_user(app, email="kaspar-oll@test.ch", password="password123"):
    """Account mit zwei Organisationen; Nutzer hat NUR in Org Eins eine Rolle."""
    from app.models import (
        db, Account, Organization, User, Membership, AccessRole,
        AccessRolePermission, RoleAssignment,
    )
    from app.auth.service import set_password
    with app.app_context():
        acc = Account(name="ditwi")
        db.session.add(acc)
        db.session.flush()
        o1 = Organization(account_id=acc.id, name="Org Eins")
        o2 = Organization(account_id=acc.id, name="Org Zwei")
        db.session.add_all([o1, o2])
        db.session.flush()

        role = AccessRole(account_id=acc.id, name="Viewer")
        db.session.add(role)
        db.session.flush()
        db.session.add(AccessRolePermission(access_role_id=role.id, permission_key=P_DASHBOARD_VIEW))

        user = User(name="Kaspar OLL", email=email)
        set_password(user, password)
        db.session.add(user)
        db.session.flush()
        m = Membership(user_id=user.id, account_id=acc.id)
        db.session.add(m)
        db.session.flush()
        # Rolle NUR in Org Eins (keine accountweite Zuweisung)
        db.session.add(RoleAssignment(membership_id=m.id, access_role_id=role.id,
                                      organization_id=o1.id))
        db.session.commit()
        return {"o1": o1.id, "o2": o2.id}


def test_foreign_organization_name_not_visible(app, client):
    ids = _per_org_user(app)
    login(client, "kaspar-oll@test.ch")
    body = client.get("/dashboard").get_data(as_text=True)
    assert "Org Eins" in body            # eigene Organisation sichtbar
    assert "Org Zwei" not in body        # fremder Mandant existiert nicht in der Sicht
    assert "ganzer Account" not in body  # kein Account-Level ohne accountweite Rolle
    assert ids["o2"]                     # (nur zur Nutzung der Fixture)


def test_cannot_switch_into_foreign_organization(app, client):
    ids = _per_org_user(app)
    login(client, "kaspar-oll@test.ch")
    # Wechsel in die fremde Organisation -> verboten
    assert client.post("/admin/switch-org",
                       data={"organization_id": ids["o2"]}).status_code == 403
    # «ganzer Account» -> ebenfalls verboten (keine accountweite Rolle)
    assert client.post("/admin/switch-org", data={"organization_id": ""}).status_code == 403
    # Wechsel in die EIGENE Organisation -> erlaubt (Redirect)
    assert client.post("/admin/switch-org",
                       data={"organization_id": ids["o1"]}).status_code in (302, 303)
