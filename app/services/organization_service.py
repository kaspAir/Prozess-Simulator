from app.models import Organization, OrgUnit, Role, Function, Person


def get_organization_overview(org_id=None):
    organizations = Organization.query.order_by(Organization.name).all()

    selected_org = None
    if org_id:
        selected_org = Organization.query.get(org_id)
    elif organizations:
        selected_org = organizations[0]

    root_units = []
    persons = []

    if selected_org:
        root_units = (
            OrgUnit.query
            .filter_by(organization_id=selected_org.id, parent_id=None)
            .order_by(OrgUnit.sort_order, OrgUnit.name)
            .all()
        )

        persons = (
            Person.query
            .filter_by(organization_id=selected_org.id)
            .order_by(Person.name)
            .all()
        )

    roles = Role.query.order_by(Role.name).all()
    functions = Function.query.order_by(Function.name).all()

    return {
        "organizations": organizations,
        "selected_org": selected_org,
        "root_units": root_units,
        "roles": roles,
        "functions": functions,
        "persons": persons,
    }