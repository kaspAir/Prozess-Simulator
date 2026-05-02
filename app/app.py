import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, jsonify
from app.simulation import simulate_end_to_end

from app.dashboard import (
    dashboard_for_process,
    operational_dashboard_for_process,
    PERIOD_LABELS,
)

from app.models import db, Activity, Role, Function, Person, Process, Node, Edge
from app.calculations import (
    activity_cost,
    activity_capacity_per_year,
    bottleneck,
    node_position_cost,
    process_position_cost,
    node_position_capacity_per_year,
    process_position_bottleneck,
    node_function_validation,
    node_has_function_warning,
    xor_probability_warnings,
    expected_process_position_cost,
    expected_process_effort_minutes,
)
from app.calculations import (
    activity_cost,
    activity_capacity_per_year,
    bottleneck,
    node_position_cost,
    process_position_cost,
    node_position_capacity_per_year,
    process_position_bottleneck,
    process_effort_minutes,
    process_cost_summary,
)
from app.models import (
    db, Activity, Role, Function, Person, Process, Node, Edge,
    Organization, OrgUnit,
)

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/strafbefehl_lab",
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)


@app.route("/")
def index():
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
def dashboard():
    processes = Process.query.order_by(Process.id).all()

    active_tab = request.args.get("tab") or "strategic"

    op_cases = request.args.get("op_cases", type=float)
    if op_cases is None:
        op_cases = 80

    op_period = request.args.get("op_period") or "day"
    op_period_label = PERIOD_LABELS.get(op_period, "Tag")

    dashboard_items = [
        dashboard_for_process(process)
        for process in processes
    ]

    operational_items = {
        process.id: operational_dashboard_for_process(process, op_cases, op_period)
        for process in processes
    }

    return render_template(
        "dashboard.html",
        dashboard_items=dashboard_items,
        operational_items=operational_items,
        op_cases=op_cases,
        op_period=op_period,
        op_period_label=op_period_label,
        active_tab=active_tab,
    )

@app.route("/activities/new", methods=["GET", "POST"])
@app.route("/activities/<int:activity_id>", methods=["GET", "POST"])
def activity_edit(activity_id=None):
    activity = Activity.query.get(activity_id) if activity_id else Activity()
    roles = Role.query.order_by(Role.name).all()

    if request.method == "POST":
        activity.name = request.form["name"]
        activity.effort_minutes = float(request.form["effort_minutes"])
        activity.legal_basis = request.form.get("legal_basis")
        activity.sort_order = int(request.form.get("sort_order") or 0)
        role_ids = [int(x) for x in request.form.getlist("role_ids")]
        activity.roles = Role.query.filter(Role.id.in_(role_ids)).all() if role_ids else []
        db.session.add(activity)
        db.session.commit()
        return redirect(url_for("index"))

    return render_template("activity_edit.html", activity=activity, roles=roles)


@app.route("/activities/<int:activity_id>/delete", methods=["POST"])
def activity_delete(activity_id):
    activity = Activity.query.get_or_404(activity_id)
    db.session.delete(activity)
    db.session.commit()
    return redirect(url_for("index"))


@app.route("/organization")
def organization():
    organizations = Organization.query.order_by(Organization.name).all()
    selected_org_id = request.args.get("org_id", type=int)
    selected_org = Organization.query.get(selected_org_id) if selected_org_id else (organizations[0] if organizations else None)

    root_units = []
    persons = []

    if selected_org:
        root_units = (
            OrgUnit.query
            .filter_by(organization_id=selected_org.id, parent_id=None)
            .order_by(OrgUnit.sort_order, OrgUnit.name)
            .all()
        )
        persons = Person.query.filter_by(organization_id=selected_org.id).order_by(Person.name).all()

    roles = Role.query.order_by(Role.name).all()
    functions = Function.query.order_by(Function.name).all()

    return render_template(
        "organization.html",
        organizations=organizations,
        selected_org=selected_org,
        root_units=root_units,
        persons=persons,
        roles=roles,
        functions=functions,
    )

@app.route("/organizations/new", methods=["GET", "POST"])
@app.route("/organizations/<int:organization_id>", methods=["GET", "POST"])
def organization_edit(organization_id=None):
    organization = Organization.query.get(organization_id) if organization_id else Organization()

    if request.method == "POST":
        organization.name = request.form["name"]
        organization.description = request.form.get("description")
        db.session.add(organization)
        db.session.commit()

        if not organization.units:
            root = OrgUnit(
                organization=organization,
                name=organization.name,
                unit_type="Organisation",
                sort_order=0,
            )
            db.session.add(root)
            db.session.commit()

        return redirect(url_for("organization", org_id=organization.id))

    return render_template("organization_edit.html", organization=organization)

@app.route("/organizations/<int:organization_id>/units/new", methods=["GET", "POST"])
@app.route("/organizations/<int:organization_id>/units/<int:unit_id>", methods=["GET", "POST"])
def org_unit_edit(organization_id, unit_id=None):
    organization = Organization.query.get_or_404(organization_id)
    unit = OrgUnit.query.get(unit_id) if unit_id else OrgUnit(organization=organization, unit_type="Team")
    all_units = (
        OrgUnit.query
        .filter_by(organization_id=organization.id)
        .order_by(OrgUnit.sort_order, OrgUnit.name)
        .all()
    )
    roles = Role.query.order_by(Role.name).all()
    persons = Person.query.filter_by(organization_id=organization.id).order_by(Person.name).all()
    functions = Function.query.order_by(Function.name).all()

    if request.method == "POST":
        unit.organization = organization
        unit.name = request.form["name"]
        unit.unit_type = request.form.get("unit_type") or "Team"
        unit.description = request.form.get("description")
        unit.sort_order = int(request.form.get("sort_order") or 0)

        parent_id = request.form.get("parent_id")
        unit.parent_id = int(parent_id) if parent_id else None

        person_id = request.form.get("person_id")
        unit.person_id = int(person_id) if person_id else None

        role_ids = [int(x) for x in request.form.getlist("role_ids")]
        unit.roles = Role.query.filter(Role.id.in_(role_ids)).all() if role_ids else []

        # Wenn eine Stelle mit Person besetzt wird, Person automatisch mit Rollen der Stelle verknüpfen.
        if unit.unit_type == "Stelle" and unit.person_id:
            person = Person.query.get(unit.person_id)
            if person:
                for role in unit.roles:
                    if role not in person.roles:
                        person.roles.append(role)
                db.session.add(person)

        db.session.add(unit)
        db.session.commit()
        return redirect(url_for("organization", org_id=organization.id))

    return render_template(
        "org_unit_edit.html",
        organization=organization,
        unit=unit,
        all_units=all_units,
        roles=roles,
        persons=persons,
        functions=functions,
    )

@app.route("/organizations/<int:organization_id>/units/<int:unit_id>/delete", methods=["POST"])
def org_unit_delete(organization_id, unit_id):
    unit = OrgUnit.query.get_or_404(unit_id)
    db.session.delete(unit)
    db.session.commit()
    return redirect(url_for("organization", org_id=organization_id))


@app.route("/roles/new", methods=["GET", "POST"])
@app.route("/roles/<int:role_id>", methods=["GET", "POST"])
def role_edit(role_id=None):
    role = Role.query.get(role_id) if role_id else Role()
    roles = Role.query.order_by(Role.name).all()
    functions = Function.query.order_by(Function.name).all()

    if request.method == "POST":
        role.name = request.form["name"]
        parent_id = request.form.get("parent_id")
        role.parent_id = int(parent_id) if parent_id else None
        function_ids = [int(x) for x in request.form.getlist("function_ids")]
        role.functions = Function.query.filter(Function.id.in_(function_ids)).all() if function_ids else []
        db.session.add(role)
        db.session.commit()
        return redirect(url_for("organization"))

    return render_template("role_edit.html", role=role, roles=roles, functions=functions)


@app.route("/functions/new", methods=["GET", "POST"])
@app.route("/functions/<int:function_id>", methods=["GET", "POST"])
def function_edit(function_id=None):
    function = Function.query.get(function_id) if function_id else Function()
    if request.method == "POST":
        function.name = request.form["name"]
        function.description = request.form.get("description")
        db.session.add(function)
        db.session.commit()
        return redirect(url_for("organization"))
    return render_template("function_edit.html", function=function)


@app.route("/persons/new", methods=["GET", "POST"])
@app.route("/persons/<int:person_id>", methods=["GET", "POST"])
def person_edit(person_id=None):
    person = Person.query.get(person_id) if person_id else Person(active=True, fte=1.0)
    roles = Role.query.order_by(Role.name).all()
    functions = Function.query.order_by(Function.name).all()
    organizations = Organization.query.order_by(Organization.name).all()

    if request.method == "POST":
        person.name = request.form["name"]
        person.annual_salary = float(request.form["annual_salary"])
        person.fte = float(request.form["fte"])
        person.active = bool(request.form.get("active"))

        organization_id = request.form.get("organization_id")
        person.organization_id = int(organization_id) if organization_id else None

        role_ids = [int(x) for x in request.form.getlist("role_ids")]
        function_ids = [int(x) for x in request.form.getlist("function_ids")]

        person.roles = Role.query.filter(Role.id.in_(role_ids)).all() if role_ids else []
        person.functions = Function.query.filter(Function.id.in_(function_ids)).all() if function_ids else []

        db.session.add(person)
        db.session.commit()

        if person.organization_id:
            return redirect(url_for("organization", org_id=person.organization_id))
        return redirect(url_for("organization"))

    return render_template(
        "person_edit.html",
        person=person,
        roles=roles,
        functions=functions,
        organizations=organizations,
    )

@app.route("/process/<int:process_id>")
def process_graph(process_id):
    process = Process.query.get_or_404(process_id)
    nodes = Node.query.filter_by(process_id=process.id).order_by(Node.sort_order, Node.id).all()
    edges = (
        Edge.query
        .join(Node, Edge.source_node_id == Node.id)
        .filter(Node.process_id == process.id)
        .all()
    )

    node_function_validations = {
    node.id: node_function_validation(node)
    for node in nodes
    }
    node_function_warnings = {
    node.id: node_has_function_warning(node)
    for node in nodes
    }


    node_costs = {node.id: node_position_cost(node) for node in nodes}
    node_capacities = {node.id: node_position_capacity_per_year(node) for node in nodes}
    total_process_cost = process_position_cost(nodes)
    total_effort_minutes = process_effort_minutes(nodes)
    bottleneck_node, bottleneck_capacity = process_position_bottleneck(nodes)
    xor_warnings = xor_probability_warnings(nodes)
    expected_process_cost = expected_process_position_cost(nodes, edges)
    expected_effort_minutes = expected_process_effort_minutes(nodes, edges)

    return render_template(
        "process_graph.html",
        process=process,
        nodes=nodes,
        edges=edges,
        node_costs=node_costs,
        node_capacities=node_capacities,
        total_process_cost=total_process_cost,
        total_effort_minutes=total_effort_minutes,
        bottleneck_node=bottleneck_node,
        bottleneck_capacity=bottleneck_capacity,
        node_function_validations=node_function_validations,
        node_function_warnings=node_function_warnings,
        xor_warnings=xor_warnings,
        expected_process_cost=expected_process_cost,
        expected_effort_minutes=expected_effort_minutes,
    )


@app.route("/process/<int:process_id>/nodes/<int:node_id>/delete", methods=["POST"])
def node_delete(process_id, node_id):
    node = Node.query.get_or_404(node_id)
    Edge.query.filter(
        (Edge.source_node_id == node.id) | (Edge.target_node_id == node.id)
    ).delete(synchronize_session=False)
    db.session.delete(node)
    db.session.commit()
    return redirect(url_for("process_graph", process_id=process_id))

@app.route("/process/<int:process_id>/nodes/new", methods=["GET", "POST"])
@app.route("/process/<int:process_id>/nodes/<int:node_id>", methods=["GET", "POST"])
def node_edit(process_id, node_id=None):
    process = Process.query.get_or_404(process_id)
    node = Node.query.get(node_id) if node_id else Node(process=process, type="task", sort_order=0, x=120, y=160)
    roles = Role.query.order_by(Role.name).all()
    subprocesses = Process.query.filter(Process.id != process.id).order_by(Process.name).all()
    positions = OrgUnit.query.filter_by(unit_type="Stelle").order_by(OrgUnit.organization_id, OrgUnit.sort_order, OrgUnit.name).all()
    functions = Function.query.order_by(Function.name).all()


    if request.method == "POST":
        node.name = request.form["name"]
        node.type = request.form["type"]
        node.effort_minutes = float(request.form.get("effort_minutes") or 0)
        node.legal_basis = request.form.get("legal_basis")
        node.sort_order = int(request.form.get("sort_order") or 0)
        node.x = float(request.form.get("x") or node.x or 120)
        node.y = float(request.form.get("y") or node.y or 160)

        subprocess_id = request.form.get("subprocess_id")
        node.subprocess_id = int(subprocess_id) if subprocess_id else None

        role_ids = [int(x) for x in request.form.getlist("role_ids")]
        position_ids = [int(x) for x in request.form.getlist("position_ids")]

        function_ids = [int(x) for x in request.form.getlist("required_function_ids")]
        node.required_functions = Function.query.filter(Function.id.in_(function_ids)).all() if function_ids else []

        node.roles = Role.query.filter(Role.id.in_(role_ids)).all() if role_ids else []
        node.assigned_positions = OrgUnit.query.filter(OrgUnit.id.in_(position_ids)).all() if position_ids else []

        db.session.add(node)
        db.session.commit()
        return redirect(url_for("process_graph", process_id=process.id))

    return render_template(
        "node_edit.html",
        process=process,
        node=node,
        roles=roles,
        subprocesses=subprocesses,
        positions=positions,
        functions=functions,
    )

@app.route("/process/<int:process_id>/edges/<int:edge_id>/delete", methods=["POST"])
def edge_delete(process_id, edge_id):
    edge = Edge.query.get_or_404(edge_id)
    source_node_id = edge.source_node_id
    db.session.delete(edge)
    db.session.commit()

    normalize_xor_yes_no(source_node_id)

    return redirect(url_for("process_graph", process_id=process_id))


def normalize_xor_yes_no(source_node_id):
    source = Node.query.get(source_node_id)
    if not source or source.type != "xor":
        return

    outgoing = Edge.query.filter_by(source_node_id=source.id).order_by(Edge.id).all()

    if len(outgoing) == 1:
        outgoing[0].condition = outgoing[0].condition or "Ja"
        outgoing[0].probability_percent = 100
        db.session.add(outgoing[0])
        db.session.commit()
        return

    if len(outgoing) == 2:
        first, second = outgoing[0], outgoing[1]

        first.condition = first.condition or "Ja"
        second.condition = second.condition or "Nein"

        if first.probability_percent is None and second.probability_percent is None:
            first.probability_percent = 50
            second.probability_percent = 50
        elif first.probability_percent is not None and second.probability_percent is None:
            second.probability_percent = 100 - first.probability_percent
        elif first.probability_percent is None and second.probability_percent is not None:
            first.probability_percent = 100 - second.probability_percent

        db.session.add(first)
        db.session.add(second)
        db.session.commit()


@app.route("/process/<int:process_id>/edges/new", methods=["GET", "POST"])
@app.route("/process/<int:process_id>/edges/<int:edge_id>", methods=["GET", "POST"])
def edge_edit(process_id, edge_id=None):
    process = Process.query.get_or_404(process_id)
    edge = Edge.query.get(edge_id) if edge_id else Edge()
    nodes = Node.query.filter_by(process_id=process.id).order_by(Node.sort_order, Node.id).all()

    if request.method == "POST":
        edge.source_node_id = int(request.form["source_node_id"])
        edge.target_node_id = int(request.form["target_node_id"])
        edge.condition = request.form.get("condition") or None

        probability = request.form.get("probability_percent")
        source = Node.query.get(edge.source_node_id)

        if source and source.type == "xor":
            edge.probability_percent = float(probability) if probability not in (None, "") else None
        else:
            edge.probability_percent = None

        db.session.add(edge)
        db.session.commit()

        normalize_xor_yes_no(edge.source_node_id)

        return redirect(url_for("process_graph", process_id=process.id))

    return render_template("edge_edit.html", process=process, edge=edge, nodes=nodes)


@app.route("/processes/new", methods=["GET", "POST"])
@app.route("/processes/<int:process_id>", methods=["GET", "POST"])
def process_edit(process_id=None):
    parent_id = request.args.get("parent_id", type=int)
    process = Process.query.get(process_id) if process_id else None
    parent = Process.query.get(parent_id) if parent_id else (process.parent if process else None)

    owner_units = OrgUnit.query.filter(OrgUnit.unit_type != "Stelle").order_by(OrgUnit.organization_id, OrgUnit.sort_order, OrgUnit.name).all()

    if request.method == "POST":
        form_parent_id = request.form.get("parent_process_id")
        owner_org_unit_id = request.form.get("owner_org_unit_id")

        if process is None:
            process = Process(
                name=request.form["name"],
                parent_process_id=int(form_parent_id) if form_parent_id else None,
            )
            db.session.add(process)
            db.session.commit()

            start = Node(process=process, type="start", name="Start", sort_order=0, x=80, y=180)
            end = Node(process=process, type="end", name="Ende", sort_order=99, x=520, y=180)
            db.session.add_all([start, end])
            db.session.commit()
            db.session.add(Edge(source_node=start, target_node=end))
            db.session.commit()
        else:
            process.name = request.form["name"]
            process.parent_process_id = int(form_parent_id) if form_parent_id else None

        process.owner_org_unit_id = int(owner_org_unit_id) if owner_org_unit_id else None
        db.session.add(process)
        db.session.commit()

        return redirect(url_for("process_graph", process_id=process.id))

    processes = Process.query.order_by(Process.name).all()
    return render_template(
        "process_edit.html",
        process=process,
        parent=parent,
        processes=processes,
        owner_units=owner_units,
    )

@app.route("/processes/<int:process_id>/delete", methods=["POST"])
def process_delete(process_id):
    process = Process.query.get_or_404(process_id)

    # 1) Untergeordnete Prozesse nicht löschen, sondern zu Hauptprozessen machen.
    child_processes = Process.query.filter_by(parent_process_id=process.id).all()
    for child in child_processes:
        child.parent_process_id = None
        db.session.add(child)

    # 2) BPMN-Subprozess-Nodes, die auf diesen Prozess zeigen, entkoppeln.
    # Das ist der Foreign-Key, der Deinen Fehler verursacht hat.
    referencing_nodes = Node.query.filter_by(subprocess_id=process.id).all()
    for node in referencing_nodes:
        node.subprocess_id = None
        if node.type == "subprocess":
            node.name = f"{node.name} (nicht verknüpft)"
        db.session.add(node)

    # 3) Edges der Nodes dieses Prozesses löschen.
    node_ids = [node.id for node in process.nodes]
    if node_ids:
        Edge.query.filter(
            (Edge.source_node_id.in_(node_ids)) | (Edge.target_node_id.in_(node_ids))
        ).delete(synchronize_session=False)

    # 4) Nodes dieses Prozesses löschen.
    for node in list(process.nodes):
        db.session.delete(node)

    # 5) Prozess löschen.
    db.session.delete(process)
    db.session.commit()

    return redirect(url_for("process_map"))

@app.route("/process-map")
def process_map():
    processes = Process.query.order_by(Process.id).all()
    process_summaries = {process.id: process_cost_summary(process) for process in processes}
    return render_template("process_map.html", processes=processes, process_summaries=process_summaries)

@app.route("/processes")
def process_list():
    processes = Process.query.order_by(Process.parent_process_id.nullsfirst(), Process.name).all()
    process_summaries = {process.id: process_cost_summary(process) for process in processes}
    return render_template("process_list.html", processes=processes, process_summaries=process_summaries)

@app.route("/simulation", methods=["GET", "POST"])
def simulation():
    processes = Process.query.filter(Process.parent_process_id.is_(None)).order_by(Process.name).all()

    selected_process_id = request.values.get("process_id", type=int)
    selected_process = Process.query.get(selected_process_id) if selected_process_id else (processes[0] if processes else None)

    case_count = request.values.get("case_count", type=float) or 1000
    result = simulate_end_to_end(selected_process, case_count) if selected_process else None

    return render_template(
        "simulation.html",
        processes=processes,
        selected_process=selected_process,
        case_count=case_count,
        result=result,
    )


@app.route("/api/processes/<int:process_id>/position", methods=["POST"])
def api_update_process_position(process_id):
    process = Process.query.get_or_404(process_id)
    data = request.get_json(force=True)

    process.x = float(data.get("x", process.x or 80))
    process.y = float(data.get("y", process.y or 160))

    db.session.add(process)
    db.session.commit()

    return jsonify({
        "ok": True,
        "process_id": process.id,
        "x": process.x,
        "y": process.y,
    })

@app.route("/api/nodes/<int:node_id>/position", methods=["POST"])
def api_update_node_position(node_id):
    node = Node.query.get_or_404(node_id)
    data = request.get_json(force=True)
    node.x = float(data.get("x", node.x))
    node.y = float(data.get("y", node.y))
    db.session.add(node)
    db.session.commit()
    return jsonify({"ok": True, "node_id": node.id, "x": node.x, "y": node.y})


@app.route("/api/process/<int:process_id>/edges", methods=["POST"])
def api_create_edge(process_id):
    process = Process.query.get_or_404(process_id)
    data = request.get_json(force=True)

    source_node_id = int(data["source_node_id"])
    target_node_id = int(data["target_node_id"])
    condition = data.get("condition") or None
    probability_percent = data.get("probability_percent")

    source = Node.query.get_or_404(source_node_id)
    target = Node.query.get_or_404(target_node_id)

    if source.process_id != process.id or target.process_id != process.id:
        return jsonify({"ok": False, "error": "Nodes müssen im gleichen Prozess liegen."}), 400

    edge = Edge(
        source_node_id=source.id,
        target_node_id=target.id,
        condition=condition,
        probability_percent=(
            float(probability_percent)
            if source.type == "xor" and probability_percent not in (None, "")
            else None
        ),
    )
    db.session.add(edge)
    db.session.commit()

    normalize_xor_yes_no(edge.source_node_id)

    return jsonify({
        "ok": True,
        "edge": {
            "id": edge.id,
            "source_node_id": edge.source_node_id,
            "target_node_id": edge.target_node_id,
            "condition": edge.condition,
            "probability_percent": edge.probability_percent,
        }
    })


@app.route("/processes/<int:process_id>/detach", methods=["POST"])
def process_detach(process_id):
    process = Process.query.get_or_404(process_id)
    process.parent_process_id = None
    db.session.add(process)
    db.session.commit()
    return redirect(request.referrer or url_for("process_map"))

@app.route("/api/edges/<int:edge_id>", methods=["DELETE", "POST"])
def api_delete_edge(edge_id):
    edge = Edge.query.get_or_404(edge_id)
    db.session.delete(edge)
    db.session.commit()
    return jsonify({"ok": True, "edge_id": edge_id})

@app.route("/api/processes/<int:process_id>/detach", methods=["POST", "DELETE"])
def api_process_detach(process_id):
    process = Process.query.get_or_404(process_id)
    process.parent_process_id = None
    db.session.add(process)
    db.session.commit()
    return jsonify({"ok": True, "process_id": process_id})

@app.route("/api/processes/<int:process_id>", methods=["DELETE", "POST"])
def api_delete_process(process_id):
    process = Process.query.get_or_404(process_id)

    child_processes = Process.query.filter_by(parent_process_id=process.id).all()
    for child in child_processes:
        child.parent_process_id = None
        db.session.add(child)

    referencing_nodes = Node.query.filter_by(subprocess_id=process.id).all()
    for node in referencing_nodes:
        node.subprocess_id = None
        if node.type == "subprocess":
            node.name = f"{node.name} (nicht verknüpft)"
        db.session.add(node)

    node_ids = [node.id for node in process.nodes]
    if node_ids:
        Edge.query.filter(
            (Edge.source_node_id.in_(node_ids)) | (Edge.target_node_id.in_(node_ids))
        ).delete(synchronize_session=False)

    for node in list(process.nodes):
        db.session.delete(node)

    db.session.delete(process)
    db.session.commit()

    return jsonify({"ok": True, "process_id": process_id})

@app.route("/api/processes/<int:source_process_id>/connect/<int:target_process_id>", methods=["POST"])
def api_connect_processes(source_process_id, target_process_id):
    source = Process.query.get_or_404(source_process_id)
    target = Process.query.get_or_404(target_process_id)

    if source.id == target.id:
        return jsonify({"ok": False, "error": "Ein Prozess kann nicht mit sich selbst verbunden werden."}), 400

    # Einfache Zyklusprüfung: target darf kein Vorfahr von source sein.
    current = source
    while current.parent_process_id:
        if current.parent_process_id == target.id:
            return jsonify({"ok": False, "error": "Diese Verbindung würde einen Zyklus erzeugen."}), 400
        current = Process.query.get(current.parent_process_id)
        if current is None:
            break

    target.parent_process_id = source.id
    db.session.add(target)
    db.session.commit()

    return jsonify({
        "ok": True,
        "source_process_id": source.id,
        "target_process_id": target.id,
        "source_name": source.name,
        "target_name": target.name,
    })

@app.route("/api/xor/<int:node_id>/split", methods=["POST"])
def api_update_xor_split(node_id):
    node = Node.query.get_or_404(node_id)

    if node.type != "xor":
        return jsonify({"ok": False, "error": "Node ist keine XOR-Entscheidung."}), 400

    outgoing = Edge.query.filter_by(source_node_id=node.id).order_by(Edge.id).all()

    if len(outgoing) != 2:
        return jsonify({"ok": False, "error": "XOR muss genau zwei ausgehende Pfeile haben."}), 400

    data = request.get_json(force=True)
    yes_percent = float(data.get("yes_percent", 0))

    if yes_percent < 0 or yes_percent > 100:
        return jsonify({"ok": False, "error": "Ja-Prozent muss zwischen 0 und 100 liegen."}), 400

    no_percent = 100 - yes_percent

    yes_edge, no_edge = outgoing[0], outgoing[1]

    yes_edge.condition = "Ja"
    yes_edge.probability_percent = yes_percent

    no_edge.condition = "Nein"
    no_edge.probability_percent = no_percent

    db.session.add(yes_edge)
    db.session.add(no_edge)
    db.session.commit()

    return jsonify({
        "ok": True,
        "node_id": node.id,
        "yes_edge_id": yes_edge.id,
        "no_edge_id": no_edge.id,
        "yes_percent": yes_percent,
        "no_percent": no_percent,
    })
