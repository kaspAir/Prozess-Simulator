from flask import (
    Blueprint, render_template, request, abort, redirect, url_for, flash, session,
)
from flask_login import current_user

from app.models import (
    db, Organization, OrgUnit, Role, Function, Person, RoleAssignment, Invitation,
)

from app.services.organization_service import get_organization_overview
from app.auth.permissions import P_DASHBOARD_VIEW, P_ORGCHART_MANAGE, P_PERSONS_MANAGE
from app.auth.service import user_has_permission, current_account_id

organization_bp = Blueprint("organization", __name__, url_prefix="/organization")


@organization_bp.before_request
def _guard():
    ep = (request.endpoint or "").split(".")[-1]
    if ep == "person_edit":
        need = P_PERSONS_MANAGE
    elif ep in ("organization_edit", "organization_delete", "org_unit_edit",
                "org_unit_delete", "role_edit", "function_edit"):
        need = P_ORGCHART_MANAGE
    else:
        need = P_DASHBOARD_VIEW
    if not user_has_permission(current_user, need):
        abort(403)


def _acc():
    return current_account_id()


def _ids(field):
    return [int(x) for x in request.form.getlist(field) if x]


# ── Übersicht ────────────────────────────────────────────────────────────
@organization_bp.route("/")
def organization():
    # B-02: zuletzt gewaehlte Organisation ueber Navigation hinweg merken,
    # statt bei jedem Aufruf auf die erste zurueckzufallen.
    org_id = request.args.get("org_id", type=int)
    if org_id:
        session["org_overview_id"] = org_id
    else:
        org_id = session.get("org_overview_id")
    data = get_organization_overview(org_id)
    # tatsaechlich angezeigte Organisation zurueckschreiben (auch nach Fallback)
    session["org_overview_id"] = data["selected_org"].id if data["selected_org"] else None
    return render_template("organization.html", **data)


# ── Organisation ─────────────────────────────────────────────────────────
@organization_bp.route("/edit", methods=["GET", "POST"])
@organization_bp.route("/edit/<int:organization_id>", methods=["GET", "POST"])
def organization_edit(organization_id=None):
    organization = (
        Organization.query.filter_by(id=organization_id, account_id=_acc()).first()
        if organization_id else Organization()
    )
    if organization_id and organization is None:
        abort(404)

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        description = (request.form.get("description") or "").strip() or None

        # B-06: keine zwei Organisationen mit gleichem Namen im selben Account
        dup = Organization.query.filter_by(account_id=_acc(), name=name).first()
        if name and dup and dup.id != organization.id:
            flash(f"Es gibt bereits eine Organisation «{name}».", "error")
            organization.name = name
            organization.description = description
            return render_template("organization_edit.html", organization=organization)

        organization.name = name
        organization.description = description
        if organization.id is None:
            organization.account_id = _acc()
            db.session.add(organization)
        db.session.commit()
        flash("Organisation gespeichert.", "success")
        return redirect(url_for("organization.organization", org_id=organization.id))

    return render_template("organization_edit.html", organization=organization)


# ── Organisation löschen ────────────────────────────────────────────────────
@organization_bp.route("/delete/<int:organization_id>", methods=["POST"])
def organization_delete(organization_id):
    org = Organization.query.filter_by(id=organization_id, account_id=_acc()).first()
    if org is None:
        abort(404)
    name = org.name

    # Personen bleiben erhalten, werden aber von dieser Organisation gelöst.
    for p in list(org.persons):
        p.organization_id = None
    # Org-spezifische Rollenzuweisungen/Einladungen verlieren mit der Org ihre Bedeutung.
    RoleAssignment.query.filter_by(organization_id=org.id).delete(synchronize_session=False)
    Invitation.query.filter_by(organization_id=org.id).update(
        {"organization_id": None}, synchronize_session=False)

    db.session.delete(org)  # Einheiten/Stellen via cascade "delete-orphan"
    db.session.commit()
    flash(f"Organisation «{name}» wurde gelöscht.", "success")
    return redirect(url_for("organization.organization"))


# ── Organisationseinheit ───────────────────────────────────────────────────
@organization_bp.route("/unit/edit", methods=["GET", "POST"])
@organization_bp.route("/unit/edit/<int:unit_id>", methods=["GET", "POST"])
def org_unit_edit(unit_id=None):
    unit = OrgUnit.query.get(unit_id) if unit_id else OrgUnit()
    if unit_id and (unit is None or unit.organization.account_id != _acc()):
        abort(404)

    if request.method == "POST":
        org_id = unit.organization_id or request.form.get("organization_id", type=int) \
            or request.args.get("organization_id", type=int)
        org = Organization.query.filter_by(id=org_id, account_id=_acc()).first()
        if org is None:
            abort(404)
        unit.organization_id = org.id
        unit.name = (request.form.get("name") or "").strip()
        unit.unit_type = request.form.get("unit_type") or "Team"
        unit.parent_id = request.form.get("parent_id", type=int) or None
        unit.sort_order = request.form.get("sort_order", type=int) or 0
        unit.description = (request.form.get("description") or "").strip() or None
        unit.person_id = request.form.get("person_id", type=int) or None
        unit.roles = Role.query.filter(Role.id.in_(_ids("role_ids")),
                                       Role.account_id == _acc()).all() if _ids("role_ids") else []
        # Rollen der Stelle automatisch der Person zuordnen
        if unit.person_id and unit.roles:
            person = db.session.get(Person, unit.person_id)
            if person:
                for r in unit.roles:
                    if r not in person.roles:
                        person.roles.append(r)
        if unit.id is None:
            db.session.add(unit)
        db.session.commit()
        flash("Einheit gespeichert.", "success")
        return redirect(url_for("organization.organization", org_id=org.id))

    # GET
    org_id = unit.organization_id or request.args.get("organization_id", type=int)
    organization = Organization.query.filter_by(id=org_id, account_id=_acc()).first() if org_id else None
    if organization is None:
        abort(404)
    all_units = OrgUnit.query.filter_by(organization_id=organization.id).order_by(
        OrgUnit.sort_order, OrgUnit.name).all()
    persons = Person.query.filter_by(account_id=_acc()).order_by(Person.name).all()
    roles = Role.query.filter_by(account_id=_acc()).order_by(Role.name).all()
    return render_template(
        "org_unit_edit.html", unit=unit, organization=organization,
        all_units=all_units, persons=persons, roles=roles,
        preselect_parent_id=request.args.get("parent_id", type=int),
        preselect_unit_type=request.args.get("unit_type"))


@organization_bp.route("/unit/<int:unit_id>/delete", methods=["POST"])
def org_unit_delete(unit_id):
    unit = OrgUnit.query.get_or_404(unit_id)
    if unit.organization.account_id != _acc():
        abort(404)
    org_id = unit.organization_id
    db.session.delete(unit)
    db.session.commit()
    flash("Einheit gelöscht.", "success")
    return redirect(url_for("organization.organization", org_id=org_id))


# ── Rolle ───────────────────────────────────────────────────────────────────
@organization_bp.route("/role/edit", methods=["GET", "POST"])
@organization_bp.route("/role/edit/<int:role_id>", methods=["GET", "POST"])
def role_edit(role_id=None):
    role = (Role.query.filter_by(id=role_id, account_id=_acc()).first()
            if role_id else Role())
    if role_id and role is None:
        abort(404)

    if request.method == "POST":
        role.name = (request.form.get("name") or "").strip()
        role.parent_id = request.form.get("parent_id", type=int) or None
        role.functions = Function.query.filter(Function.id.in_(_ids("function_ids")),
                                                Function.account_id == _acc()).all() if _ids("function_ids") else []
        if role.id is None:
            role.account_id = _acc()
            db.session.add(role)
        db.session.commit()
        flash("Rolle gespeichert.", "success")
        return redirect(url_for("organization.organization"))

    roles = Role.query.filter_by(account_id=_acc()).order_by(Role.name).all()
    functions = Function.query.filter_by(account_id=_acc()).order_by(Function.name).all()
    return render_template("role_edit.html", role=role, roles=roles, functions=functions)


# ── Funktion ──────────────────────────────────────────────────────────────
@organization_bp.route("/function/edit", methods=["GET", "POST"])
@organization_bp.route("/function/edit/<int:function_id>", methods=["GET", "POST"])
def function_edit(function_id=None):
    function = (Function.query.filter_by(id=function_id, account_id=_acc()).first()
                if function_id else Function())
    if function_id and function is None:
        abort(404)

    if request.method == "POST":
        function.name = (request.form.get("name") or "").strip()
        function.description = (request.form.get("description") or "").strip() or None
        if function.id is None:
            function.account_id = _acc()
            db.session.add(function)
        db.session.commit()
        flash("Funktion gespeichert.", "success")
        return redirect(url_for("organization.organization"))

    return render_template("function_edit.html", function=function)


# ── Person ──────────────────────────────────────────────────────────────────
@organization_bp.route("/person/edit", methods=["GET", "POST"])
@organization_bp.route("/person/edit/<int:person_id>", methods=["GET", "POST"])
def person_edit(person_id=None):
    person = (Person.query.filter_by(id=person_id, account_id=_acc()).first()
              if person_id else Person(active=True, fte=1.0))
    if person_id and person is None:
        abort(404)

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        org_id = request.form.get("organization_id", type=int) or None
        salary = request.form.get("annual_salary", type=float) or 0
        fte = request.form.get("fte", type=float) or 0
        active = bool(request.form.get("active"))
        sel_roles = (Role.query.filter(Role.id.in_(_ids("role_ids")),
                                       Role.account_id == _acc()).all()
                     if _ids("role_ids") else [])
        sel_functions = (Function.query.filter(Function.id.in_(_ids("function_ids")),
                                               Function.account_id == _acc()).all()
                         if _ids("function_ids") else [])

        # Validierung (B-03 FTE ≤ 1.0, B-04 keine Negativwerte)
        errors = []
        if fte < 0 or fte > 1:
            errors.append("Die Anstellung (FTE) muss zwischen 0.0 und 1.0 (0–100 %) liegen.")
        if salary < 0:
            errors.append("Das Jahresgehalt darf nicht negativ sein.")

        if errors:
            for e in errors:
                flash(e, "error")
            organizations = Organization.query.filter_by(account_id=_acc()).order_by(Organization.name).all()
            roles = Role.query.filter_by(account_id=_acc()).order_by(Role.name).all()
            functions = Function.query.filter_by(account_id=_acc()).order_by(Function.name).all()
            # transientes Objekt mit den Eingaben, damit das Formular sie behaelt
            form_person = Person(name=name, organization_id=org_id,
                                 annual_salary=salary, fte=fte, active=active)
            form_person.id = person.id
            form_person.roles = sel_roles
            form_person.functions = sel_functions
            return render_template("person_edit.html", person=form_person,
                                   organizations=organizations, roles=roles, functions=functions)

        person.name = name
        person.organization_id = org_id
        person.annual_salary = salary
        person.fte = fte
        person.active = active
        person.roles = sel_roles
        person.functions = sel_functions
        if person.id is None:
            person.account_id = _acc()
            db.session.add(person)
        db.session.commit()
        flash("Person gespeichert.", "success")
        return redirect(url_for("organization.organization", org_id=person.organization_id))

    organizations = Organization.query.filter_by(account_id=_acc()).order_by(Organization.name).all()
    roles = Role.query.filter_by(account_id=_acc()).order_by(Role.name).all()
    functions = Function.query.filter_by(account_id=_acc()).order_by(Function.name).all()
    return render_template("person_edit.html", person=person, organizations=organizations,
                           roles=roles, functions=functions)
