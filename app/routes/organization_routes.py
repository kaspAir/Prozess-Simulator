from flask import Blueprint, render_template, request

from app.models import (
    Organization,
    OrgUnit,
    Role,
    Function,
    Person,
)

from app.services.organization_service import get_organization_overview

organization_bp = Blueprint("organization", __name__, url_prefix="/organization")

#print(">>> LOADED app.web.organization_routes")

@organization_bp.route("/")
def organization():
    org_id = request.args.get("org_id", type=int)
    data = get_organization_overview(org_id)
    return render_template("organization.html", **data)


@organization_bp.route("/edit")
@organization_bp.route("/edit/<int:organization_id>")
def organization_edit(organization_id=None):
    organization = Organization.query.get(organization_id) if organization_id else None
    return render_template("organization_edit.html", organization=organization)


@organization_bp.route("/unit/edit")
@organization_bp.route("/unit/edit/<int:unit_id>")
def org_unit_edit(unit_id=None):
    unit = OrgUnit.query.get(unit_id) if unit_id else None
    organization_id = request.args.get("organization_id", type=int)
    parent_id = request.args.get("parent_id", type=int)
    unit_type = request.args.get("unit_type")
    return render_template(
        "org_unit_edit.html",
        unit=unit,
        organization_id=organization_id,
        parent_id=parent_id,
        unit_type=unit_type,
    )


@organization_bp.route("/role/edit")
@organization_bp.route("/role/edit/<int:role_id>")
def role_edit(role_id=None):
    role = Role.query.get(role_id) if role_id else None
    return render_template("role_edit.html", role=role)


@organization_bp.route("/function/edit")
@organization_bp.route("/function/edit/<int:function_id>")
def function_edit(function_id=None):
    function = Function.query.get(function_id) if function_id else None
    return render_template("function_edit.html", function=function)


@organization_bp.route("/person/edit")
@organization_bp.route("/person/edit/<int:person_id>")
def person_edit(person_id=None):
    person = Person.query.get(person_id) if person_id else None
    return render_template("person_edit.html", person=person)

#print("LOADED organization_routes.py endpoints: organization, organization_edit, org_unit_edit, role_edit, function_edit, person_edit")