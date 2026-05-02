import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, jsonify

from app.models import db, Activity, Role, Function, Person, Process, Node, Edge
from app.calculations import activity_cost, activity_capacity_per_year, bottleneck

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
    activities = Activity.query.order_by(Activity.sort_order, Activity.id).all()
    rows = []
    for a in activities:
        rows.append({
            "activity": a,
            "cost": activity_cost(a),
            "capacity": activity_capacity_per_year(a),
        })
    bottleneck_activity, max_cases = bottleneck(activities)
    return render_template("index.html", rows=rows, bottleneck_activity=bottleneck_activity, max_cases=max_cases)


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
    roles = Role.query.order_by(Role.name).all()
    root_roles = Role.query.filter(Role.parent_id.is_(None)).order_by(Role.name).all()
    persons = Person.query.order_by(Person.name).all()
    functions = Function.query.order_by(Function.name).all()
    return render_template("organization.html", roles=roles, root_roles=root_roles, persons=persons, functions=functions)


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
    if request.method == "POST":
        person.name = request.form["name"]
        person.annual_salary = float(request.form["annual_salary"])
        person.fte = float(request.form["fte"])
        person.active = bool(request.form.get("active"))
        role_ids = [int(x) for x in request.form.getlist("role_ids")]
        person.roles = Role.query.filter(Role.id.in_(role_ids)).all() if role_ids else []
        db.session.add(person)
        db.session.commit()
        return redirect(url_for("organization"))
    return render_template("person_edit.html", person=person, roles=roles)


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
    return render_template("process_graph.html", process=process, nodes=nodes, edges=edges)


@app.route("/process/<int:process_id>/nodes/new", methods=["GET", "POST"])
@app.route("/process/<int:process_id>/nodes/<int:node_id>", methods=["GET", "POST"])
def node_edit(process_id, node_id=None):
    process = Process.query.get_or_404(process_id)
    node = Node.query.get(node_id) if node_id else Node(process=process, type="task", sort_order=0, x=120, y=160)
    roles = Role.query.order_by(Role.name).all()
    subprocesses = Process.query.filter(Process.id != process.id).order_by(Process.name).all()

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
        node.roles = Role.query.filter(Role.id.in_(role_ids)).all() if role_ids else []

        db.session.add(node)
        db.session.commit()
        return redirect(url_for("process_graph", process_id=process.id))

    return render_template("node_edit.html", process=process, node=node, roles=roles, subprocesses=subprocesses)


@app.route("/process/<int:process_id>/nodes/<int:node_id>/delete", methods=["POST"])
def node_delete(process_id, node_id):
    node = Node.query.get_or_404(node_id)
    Edge.query.filter(
        (Edge.source_node_id == node.id) | (Edge.target_node_id == node.id)
    ).delete(synchronize_session=False)
    db.session.delete(node)
    db.session.commit()
    return redirect(url_for("process_graph", process_id=process_id))


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
        db.session.add(edge)
        db.session.commit()
        return redirect(url_for("process_graph", process_id=process.id))

    return render_template("edge_edit.html", process=process, edge=edge, nodes=nodes)


@app.route("/process/<int:process_id>/edges/<int:edge_id>/delete", methods=["POST"])
def edge_delete(process_id, edge_id):
    edge = Edge.query.get_or_404(edge_id)
    db.session.delete(edge)
    db.session.commit()
    return redirect(url_for("process_graph", process_id=process_id))


@app.route("/processes/new", methods=["GET", "POST"])
def process_edit():
    parent_id = request.args.get("parent_id", type=int)
    parent = Process.query.get(parent_id) if parent_id else None

    if request.method == "POST":
        form_parent_id = request.form.get("parent_process_id")
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
        return redirect(url_for("process_graph", process_id=process.id))

    processes = Process.query.order_by(Process.name).all()
    return render_template("process_edit.html", parent=parent, processes=processes)


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

    source = Node.query.get_or_404(source_node_id)
    target = Node.query.get_or_404(target_node_id)

    if source.process_id != process.id or target.process_id != process.id:
        return jsonify({"ok": False, "error": "Nodes müssen im gleichen Prozess liegen."}), 400

    edge = Edge(source_node_id=source.id, target_node_id=target.id, condition=condition)
    db.session.add(edge)
    db.session.commit()

    return jsonify({
        "ok": True,
        "edge": {
            "id": edge.id,
            "source_node_id": edge.source_node_id,
            "target_node_id": edge.target_node_id,
            "condition": edge.condition,
        }
    })
