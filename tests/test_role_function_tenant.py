"""Rollen/Funktionen sind je Organisation (Mandant) getrennt – Sichtbarkeit,
Anlage-Bindung und verlustfreier Backfill (geteilte werden dupliziert)."""
from app.auth.permissions import P_DASHBOARD_VIEW, P_ORGCHART_MANAGE
from tests.conftest import login


def _acc_two_orgs(app):
    from app.models import db, Account, Organization
    with app.app_context():
        acc = Account(name="ditwi")
        db.session.add(acc)
        db.session.flush()
        o1 = Organization(account_id=acc.id, name="Org Eins")
        o2 = Organization(account_id=acc.id, name="Org Zwei")
        db.session.add_all([o1, o2])
        db.session.commit()
        return acc.id, o1.id, o2.id


def test_backfill_duplicates_shared_role_per_org(app):
    """Eine von zwei Organisationen genutzte Rolle wird beim Backfill je Mandant
    dupliziert; die Personen behalten je ihre org-eigene Instanz."""
    acc, o1, o2 = _acc_two_orgs(app)
    from app.models import db, Role, Function, Person
    from app.services.tenant_backfill import backfill_account
    with app.app_context():
        f = Function(account_id=acc, name="Prüfen")           # geteilt
        r = Role(account_id=acc, name="Jurist")               # geteilt
        db.session.add_all([f, r])
        db.session.flush()
        r.functions = [f]
        anna = Person(account_id=acc, name="Anna", organization_id=o1, roles=[r], functions=[f])
        ben = Person(account_id=acc, name="Ben", organization_id=o2, roles=[r], functions=[f])
        db.session.add_all([anna, ben])
        db.session.commit()

        backfill_account(acc)

        # Jetzt gibt es je Organisation eine eigene Rolle/Funktion "Jurist"/"Prüfen".
        assert Role.query.filter_by(account_id=acc, name="Jurist", organization_id=o1).count() == 1
        assert Role.query.filter_by(account_id=acc, name="Jurist", organization_id=o2).count() == 1
        assert Function.query.filter_by(name="Prüfen", organization_id=o1).count() == 1
        assert Function.query.filter_by(name="Prüfen", organization_id=o2).count() == 1
        # Personen zeigen auf die Instanz ihrer eigenen Organisation
        anna = Person.query.filter_by(name="Anna").first()
        ben = Person.query.filter_by(name="Ben").first()
        assert anna.roles[0].organization_id == o1
        assert ben.roles[0].organization_id == o2
        assert anna.roles[0].id != ben.roles[0].id
        # Rollen-Funktionen bleiben in derselben Organisation
        assert anna.roles[0].functions[0].organization_id == o1


def test_backfill_single_org_assigns_all(app):
    from app.models import db, Account, Organization, Role, Function
    from app.services.tenant_backfill import backfill_account
    with app.app_context():
        acc = Account(name="solo")
        db.session.add(acc)
        db.session.flush()
        org = Organization(account_id=acc.id, name="Einzige")
        db.session.add(org)
        db.session.flush()
        db.session.add_all([Role(account_id=acc.id, name="R"),
                            Function(account_id=acc.id, name="F")])
        db.session.commit()
        backfill_account(acc.id)
        assert Role.query.filter_by(account_id=acc.id).first().organization_id == org.id
        assert Function.query.filter_by(account_id=acc.id).first().organization_id == org.id


def test_role_list_scoped_by_active_org(app, client):
    """Ein auf Org Eins beschränkter Nutzer sieht auf der Organisationsseite nur
    die Rollen seiner Organisation, nicht die von Org Zwei."""
    from app.models import (
        db, Account, Organization, User, Membership, AccessRole,
        AccessRolePermission, RoleAssignment, Role,
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
        db.session.add(Role(account_id=acc.id, organization_id=o1.id, name="Rolle Eins"))
        db.session.add(Role(account_id=acc.id, organization_id=o2.id, name="Rolle Zwei"))
        role = AccessRole(account_id=acc.id, name="Chart")
        db.session.add(role)
        db.session.flush()
        for pk in (P_DASHBOARD_VIEW, P_ORGCHART_MANAGE):
            db.session.add(AccessRolePermission(access_role_id=role.id, permission_key=pk))
        u = User(name="Kaspar OLL", email="koll@test.ch")
        set_password(u, "password123")
        db.session.add(u)
        db.session.flush()
        m = Membership(user_id=u.id, account_id=acc.id)
        db.session.add(m)
        db.session.flush()
        db.session.add(RoleAssignment(membership_id=m.id, access_role_id=role.id,
                                      organization_id=o1.id))
        db.session.commit()
        o1_id = o1.id

    login(client, "koll@test.ch")
    with client.session_transaction() as sess:
        sess["active_organization_id"] = o1_id
    html = client.get(f"/organization/?org_id={o1_id}").get_data(as_text=True)
    assert "Rolle Eins" in html
    assert "Rolle Zwei" not in html
