# Step 37: Dashboard-Hilfsfunktionen
# Datei: app/dashboard.py

ANNUAL_WORKING_HOURS_PER_FTE = 2100
ANNUAL_WORKING_MINUTES_PER_FTE = ANNUAL_WORKING_HOURS_PER_FTE * 60

PERIOD_CAPACITY_FACTOR = {
    "day": 1 / 220,
    "week": 1 / 52,
    "month": 1 / 12,
    "year": 1,
}

PERIOD_LABELS = {
    "day": "Tag",
    "week": "Woche",
    "month": "Monat",
    "year": "Jahr",
}


def period_capacity_minutes_for_fte(fte, period):
    return (fte or 0) * ANNUAL_WORKING_MINUTES_PER_FTE * PERIOD_CAPACITY_FACTOR.get(period, 1)


def position_capacity_minutes(position, period="year"):
    person = getattr(position, "person", None)
    if not person:
        return 0
    return period_capacity_minutes_for_fte(person.fte or 0, period)


def node_capacity_cases(node, period="year"):
    effort = node.effort_minutes or 0
    if effort <= 0:
        return 0

    positions = list(getattr(node, "assigned_positions", []) or [])
    if not positions:
        return 0

    total_minutes = sum(position_capacity_minutes(position, period) for position in positions)
    if total_minutes <= 0:
        return 0

    return total_minutes / effort


def node_capacity_cases_per_year(node):
    return node_capacity_cases(node, "year")


def node_capacity_minutes(node, period):
    positions = list(getattr(node, "assigned_positions", []) or [])
    return sum(position_capacity_minutes(position, period) for position in positions)


def dashboard_for_process(process):
    rows = []

    for node in process.nodes:
        if node.type != "task":
            continue

        positions = list(getattr(node, "assigned_positions", []) or [])
        if not positions:
            continue

        capacity = node_capacity_cases_per_year(node)
        if capacity <= 0:
            continue

        rows.append({
            "node": node,
            "capacity": capacity,
            "positions": positions,
        })

    rows.sort(key=lambda row: row["capacity"])

    bottleneck_capacity = rows[0]["capacity"] if rows else 0
    max_capacity = rows[-1]["capacity"] if rows else 0

    for row in rows:
        capacity = row["capacity"]

        if bottleneck_capacity and capacity <= bottleneck_capacity * 1.0001:
            status = "red"
        elif bottleneck_capacity and capacity <= bottleneck_capacity * 1.2:
            status = "yellow"
        else:
            status = "green"

        width = max(6, (capacity / max_capacity) * 100) if max_capacity else 0
        row["status"] = status
        row["width"] = width

    return {
        "process": process,
        "rows": rows,
        "bottleneck_capacity": bottleneck_capacity,
        "max_capacity": max_capacity,
    }


def outgoing_probability(edge, outgoing_count):
    if outgoing_count <= 1:
        return 1.0
    return (edge.probability_percent or 0) / 100


def node_visit_factors(process):
    nodes = list(process.nodes)
    factors = {node.id: 0.0 for node in nodes}
    node_by_id = {node.id: node for node in nodes}

    starts = [node for node in nodes if node.type == "start"]
    if starts:
        for start in starts:
            factors[start.id] = 1.0
    elif nodes:
        factors[nodes[0].id] = 1.0

    edges = []
    for node in nodes:
        edges.extend(list(node.outgoing_edges or []))
    edges = sorted(edges, key=lambda e: e.id)

    for _ in range(max(1, len(nodes) * 2)):
        changed = False

        for edge in edges:
            source = node_by_id.get(edge.source_node_id)
            target = node_by_id.get(edge.target_node_id)
            if not source or not target:
                continue

            source_factor = factors.get(source.id, 0.0)
            if source_factor <= 0:
                continue

            outgoing = list(source.outgoing_edges or [])
            multiplier = 1.0

            if source.type == "xor":
                multiplier = outgoing_probability(edge, len(outgoing))

            candidate = source_factor * multiplier

            if candidate > factors.get(target.id, 0.0):
                factors[target.id] = candidate
                changed = True

        if not changed:
            break

    return factors


def operational_dashboard_for_process(process, period_cases, period):
    """
    Operative Sicht pro gewählter Zeiteinheit.
    Keine Jahreshochrechnung:
    - Eingabe Tag = Bedarf für diesen Tag
    - Eingabe Woche = Bedarf für diese Woche
    - Eingabe Monat = Bedarf für diesen Monat
    - Eingabe Jahr = Bedarf für dieses Jahr
    """
    rows = []
    factors = node_visit_factors(process)

    for node in process.nodes:
        if node.type != "task":
            continue

        positions = list(getattr(node, "assigned_positions", []) or [])
        if not positions:
            continue

        effort = node.effort_minutes or 0
        if effort <= 0:
            continue

        visit_factor = factors.get(node.id, 1.0)
        expected_cases = period_cases * visit_factor

        required_minutes = expected_cases * effort
        capacity_minutes = node_capacity_minutes(node, period)
        capacity_cases = capacity_minutes / effort if effort else 0

        missing_minutes = max(0, required_minutes - capacity_minutes)
        missing_cases = max(0, expected_cases - capacity_cases)
        ok = missing_minutes <= 0.01

        rows.append({
            "node": node,
            "positions": positions,
            "visit_factor": visit_factor,
            "expected_cases": expected_cases,
            "effort": effort,
            "required_minutes": required_minutes,
            "required_hours": required_minutes / 60,
            "capacity_minutes": capacity_minutes,
            "capacity_hours": capacity_minutes / 60,
            "capacity_cases": capacity_cases,
            "missing_minutes": missing_minutes,
            "missing_hours": missing_minutes / 60,
            "missing_cases": missing_cases,
            "ok": ok,
        })

    rows.sort(key=lambda row: (row["ok"], -row["missing_minutes"] if not row["ok"] else row["capacity_cases"]))
    problem_rows = [row for row in rows if not row["ok"]]

    return {
        "process": process,
        "rows": rows,
        "problem_rows": problem_rows,
        "ok": len(problem_rows) == 0,
    }
