from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

role_function = db.Table(
    "role_function",
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id"), primary_key=True),
    db.Column("function_id", db.Integer, db.ForeignKey("functions.id"), primary_key=True),
)

role_activity = db.Table(
    "role_activity",
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id"), primary_key=True),
    db.Column("activity_id", db.Integer, db.ForeignKey("activities.id"), primary_key=True),
)

person_role = db.Table(
    "person_role",
    db.Column("person_id", db.Integer, db.ForeignKey("persons.id"), primary_key=True),
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id"), primary_key=True),
)

node_role = db.Table(
    "node_role",
    db.Column("node_id", db.Integer, db.ForeignKey("nodes.id"), primary_key=True),
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id"), primary_key=True),
)

node_position = db.Table(
    "node_position",
    db.Column("node_id", db.Integer, db.ForeignKey("nodes.id"), primary_key=True),
    db.Column("org_unit_id", db.Integer, db.ForeignKey("org_units.id"), primary_key=True),
)

person_function = db.Table(
    "person_function",
    db.Column("person_id", db.Integer, db.ForeignKey("persons.id"), primary_key=True),
    db.Column("function_id", db.Integer, db.ForeignKey("functions.id"), primary_key=True),
)

org_unit_role = db.Table(
    "org_unit_role",
    db.Column("org_unit_id", db.Integer, db.ForeignKey("org_units.id"), primary_key=True),
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id"), primary_key=True),
)

node_function = db.Table(
    "node_function",
    db.Column("node_id", db.Integer, db.ForeignKey("nodes.id"), primary_key=True),
    db.Column("function_id", db.Integer, db.ForeignKey("functions.id"), primary_key=True),
)

class Activity(db.Model):
    __tablename__ = "activities"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    effort_minutes = db.Column(db.Float, nullable=False, default=0)
    legal_basis = db.Column(db.Text, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    roles = db.relationship("Role", secondary=role_activity, back_populates="activities")


class Process(db.Model):
    __tablename__ = "processes"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    parent_process_id = db.Column(db.Integer, db.ForeignKey("processes.id"), nullable=True)

    x = db.Column(db.Float, nullable=False, default=80)
    y = db.Column(db.Float, nullable=False, default=160)

    parent = db.relationship("Process", remote_side=[id], backref="subprocesses")
    nodes = db.relationship("Node", back_populates="process", foreign_keys="Node.process_id")
    owner_org_unit_id = db.Column(db.Integer, db.ForeignKey("org_units.id"), nullable=True)
    owner_org_unit = db.relationship("OrgUnit", foreign_keys=[owner_org_unit_id])


class Node(db.Model):
    __tablename__ = "nodes"
    id = db.Column(db.Integer, primary_key=True)
    process_id = db.Column(db.Integer, db.ForeignKey("processes.id"), nullable=False)
    type = db.Column(db.String(50), nullable=False, default="task")
    name = db.Column(db.String(255), nullable=False)
    effort_minutes = db.Column(db.Float, nullable=False, default=0)
    legal_basis = db.Column(db.Text, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    x = db.Column(db.Float, nullable=False, default=80)
    y = db.Column(db.Float, nullable=False, default=160)

    subprocess_id = db.Column(db.Integer, db.ForeignKey("processes.id"), nullable=True)

    process = db.relationship("Process", back_populates="nodes", foreign_keys=[process_id])
    subprocess = db.relationship("Process", foreign_keys=[subprocess_id])
    roles = db.relationship("Role", secondary=node_role, back_populates="nodes")
    required_functions = db.relationship("Function", secondary=node_function, backref="required_by_nodes")

    assigned_positions = db.relationship("OrgUnit", secondary=node_position, backref="assigned_nodes")

    outgoing_edges = db.relationship(
        "Edge",
        foreign_keys="Edge.source_node_id",
        back_populates="source_node",
        cascade="all, delete-orphan",
    )
    incoming_edges = db.relationship(
        "Edge",
        foreign_keys="Edge.target_node_id",
        back_populates="target_node",
        cascade="all, delete-orphan",
    )


class Edge(db.Model):
    __tablename__ = "edges"
    id = db.Column(db.Integer, primary_key=True)
    source_node_id = db.Column(db.Integer, db.ForeignKey("nodes.id"), nullable=False)
    target_node_id = db.Column(db.Integer, db.ForeignKey("nodes.id"), nullable=False)
    condition = db.Column(db.String(255), nullable=True)

    source_node = db.relationship("Node", foreign_keys=[source_node_id], back_populates="outgoing_edges")
    target_node = db.relationship("Node", foreign_keys=[target_node_id], back_populates="incoming_edges")
    probability_percent = db.Column(db.Float, nullable=True)

class Organization(db.Model):
    __tablename__ = "organizations"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    units = db.relationship("OrgUnit", back_populates="organization", cascade="all, delete-orphan")


class OrgUnit(db.Model):
    __tablename__ = "org_units"
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("org_units.id"), nullable=True)

    name = db.Column(db.String(255), nullable=False)
    unit_type = db.Column(db.String(80), nullable=False, default="Team")
    description = db.Column(db.Text, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    person_id = db.Column(db.Integer, db.ForeignKey("persons.id"), nullable=True)
    person = db.relationship("Person", backref="positions")

    organization = db.relationship("Organization", back_populates="units")
    parent = db.relationship("OrgUnit", remote_side=[id], backref="children")
    roles = db.relationship("Role", secondary=org_unit_role, back_populates="org_units")


class Role(db.Model):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=True)
    parent = db.relationship("Role", remote_side=[id], backref="children")
    functions = db.relationship("Function", secondary=role_function, back_populates="roles")
    persons = db.relationship("Person", secondary=person_role, back_populates="roles")
    activities = db.relationship("Activity", secondary=role_activity, back_populates="roles")
    nodes = db.relationship("Node", secondary=node_role, back_populates="roles")
    org_units = db.relationship("OrgUnit", secondary=org_unit_role, back_populates="roles")
    

class Function(db.Model):
    __tablename__ = "functions"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    roles = db.relationship("Role", secondary=role_function, back_populates="functions")
    persons = db.relationship("Person", secondary=person_function, back_populates="functions")



class Person(db.Model):
    __tablename__ = "persons"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True)
    organization = db.relationship("Organization", backref="persons")
    annual_salary = db.Column(db.Float, nullable=False, default=0)
    fte = db.Column(db.Float, nullable=False, default=1.0)
    active = db.Column(db.Boolean, nullable=False, default=True)
    roles = db.relationship("Role", secondary=person_role, back_populates="persons")
    functions = db.relationship("Function", secondary=person_function, back_populates="persons")

