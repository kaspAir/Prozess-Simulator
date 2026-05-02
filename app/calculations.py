PRODUCTIVE_MINUTES_PER_FTE_YEAR = 1800 * 60


def persons_for_activity(activity):
    persons = []
    seen = set()
    for role in activity.roles:
        for person in role.persons:
            if person.active and person.id not in seen:
                persons.append(person)
                seen.add(person.id)
    return persons


def hourly_cost(person):
    if person.fte <= 0:
        return 0
    return person.annual_salary / 1800


def minute_cost(person):
    return hourly_cost(person) / 60


def activity_cost(activity):
    persons = persons_for_activity(activity)
    if not persons:
        return 0
    avg_minute_cost = sum(minute_cost(p) for p in persons) / len(persons)
    return activity.effort_minutes * avg_minute_cost


def activity_capacity_per_year(activity):
    persons = persons_for_activity(activity)
    if not persons or activity.effort_minutes <= 0:
        return 0
    total_minutes = sum(p.fte * PRODUCTIVE_MINUTES_PER_FTE_YEAR for p in persons)
    return total_minutes / activity.effort_minutes


def bottleneck(activities):
    capacities = [(a, activity_capacity_per_year(a)) for a in activities]
    capacities = [(a, c) for a, c in capacities if c > 0]
    if not capacities:
        return None, 0
    return min(capacities, key=lambda x: x[1])

PRODUCTIVE_MINUTES_PER_FTE_YEAR = 1800 * 60


def person_minute_cost(person):
    if not person:
        return 0
    if not getattr(person, "annual_salary", 0):
        return 0

    # annual_salary ist bewusst 100%-Gehalt.
    # Die Kosten pro Arbeitsminute basieren deshalb auf dem 100%-Jahresgehalt.
    return person.annual_salary / PRODUCTIVE_MINUTES_PER_FTE_YEAR


def position_minute_cost(position):
    if not position:
        return 0
    person = getattr(position, "person", None)
    if not person:
        return 0
    return person_minute_cost(person)


def node_position_cost(node):
    positions = list(getattr(node, "assigned_positions", []) or [])
    effort = getattr(node, "effort_minutes", 0) or 0

    if not positions or effort <= 0:
        return 0

    # Mehrere zugeordnete Stellen bedeuten:
    # Alle wirken an dieser Aktivität mit.
    total = 0
    for position in positions:
        total += position_minute_cost(position) * effort

    return total


def process_position_cost(nodes):
    return sum(node_position_cost(node) for node in nodes if getattr(node, "type", None) == "task")


def process_effort_minutes(nodes):
    return sum((getattr(node, "effort_minutes", 0) or 0) for node in nodes if getattr(node, "type", None) == "task")


def node_position_capacity_per_year(node):
    positions = [
        p for p in (getattr(node, "assigned_positions", []) or [])
        if getattr(p, "person", None)
    ]
    effort = getattr(node, "effort_minutes", 0) or 0

    if not positions or effort <= 0:
        return 0

    total_minutes = sum((position.person.fte or 0) * PRODUCTIVE_MINUTES_PER_FTE_YEAR for position in positions)
    return total_minutes / effort


def process_position_bottleneck(nodes):
    capacities = [
        (node, node_position_capacity_per_year(node))
        for node in nodes
        if getattr(node, "type", None) == "task"
    ]
    capacities = [(node, capacity) for node, capacity in capacities if capacity > 0]

    if not capacities:
        return None, 0

    return min(capacities, key=lambda item: item[1])

def process_cost_summary(process):
    nodes = list(getattr(process, "nodes", []) or [])
    effort = process_effort_minutes(nodes)
    cost = process_position_cost(nodes)
    bottleneck_node, bottleneck_capacity = process_position_bottleneck(nodes)

    return {
        "effort_minutes": effort,
        "cost": cost,
        "bottleneck_node": bottleneck_node,
        "bottleneck_capacity": bottleneck_capacity,
    }

def effective_person_functions(person):
    if not person:
        return set()

    functions = set(getattr(person, "functions", []) or [])

    for role in getattr(person, "roles", []) or []:
        for function in getattr(role, "functions", []) or []:
            functions.add(function)

    return functions


def missing_functions_for_position(node, position):
    required = set(getattr(node, "required_functions", []) or [])
    if not required:
        return []

    person = getattr(position, "person", None)
    if not person:
        return list(required)

    available = effective_person_functions(person)
    return sorted(list(required - available), key=lambda f: f.name)


def node_function_validation(node):
    result = []

    for position in getattr(node, "assigned_positions", []) or []:
        person = getattr(position, "person", None)
        missing = missing_functions_for_position(node, position)

        result.append({
            "position": position,
            "person": person,
            "missing_functions": missing,
            "ok": len(missing) == 0,
        })

    return result


def node_has_function_warning(node):
    return any(not item["ok"] for item in node_function_validation(node))

def xor_probability_warnings(nodes):
    warnings = {}

    for node in nodes:
        if getattr(node, "type", None) != "xor":
            continue

        outgoing = list(getattr(node, "outgoing_edges", []) or [])

        if len(outgoing) == 0:
            continue

        if len(outgoing) == 1:
            continue

        if len(outgoing) != 2:
            warnings[node.id] = {
                "total": None,
                "message": f"XOR '{node.name}' hat {len(outgoing)} Ausgänge. Erlaubt sind genau zwei: Ja und Nein.",
            }
            continue

        total = sum((edge.probability_percent or 0) for edge in outgoing)

        if abs(total - 100) > 0.01:
            warnings[node.id] = {
                "total": total,
                "message": f"XOR '{node.name}' ergibt {total:.1f}% statt 100%.",
            }

    return warnings



def expected_node_factor(nodes, edges):
    factors = {node.id: 0 for node in nodes}
    start_nodes = [node for node in nodes if getattr(node, "type", None) == "start"]
    if start_nodes:
        for node in start_nodes:
            factors[node.id] = 1
    elif nodes:
        factors[nodes[0].id] = 1

    node_by_id = {node.id: node for node in nodes}
    sorted_edges = sorted(edges, key=lambda e: e.id)

    for _ in range(max(1, len(nodes))):
        changed = False
        for edge in sorted_edges:
            source = node_by_id.get(edge.source_node_id)
            target = node_by_id.get(edge.target_node_id)
            if not source or not target:
                continue

            source_factor = factors.get(source.id, 0)
            if source_factor == 0:
                continue

            multiplier = 1
            if getattr(source, "type", None) == "xor":
                multiplier = (edge.probability_percent or 0) / 100

            new_value = source_factor * multiplier

            if new_value > factors.get(target.id, 0):
                factors[target.id] = new_value
                changed = True

        if not changed:
            break

    return factors


def expected_process_position_cost(nodes, edges):
    factors = expected_node_factor(nodes, edges)
    return sum(
        node_position_cost(node) * factors.get(node.id, 1)
        for node in nodes
        if getattr(node, "type", None) == "task"
    )


def expected_process_effort_minutes(nodes, edges):
    factors = expected_node_factor(nodes, edges)
    return sum(
        (node.effort_minutes or 0) * factors.get(node.id, 1)
        for node in nodes
        if getattr(node, "type", None) == "task"
    )
def outgoing_probability(edge, outgoing_count):
    if outgoing_count <= 1:
        return 1.0
    return (edge.probability_percent or 0) / 100