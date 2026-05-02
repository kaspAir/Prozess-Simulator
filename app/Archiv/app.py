import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for
from app.models import db, Activity, Role, Function, Person
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
