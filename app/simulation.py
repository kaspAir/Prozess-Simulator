from collections import defaultdict

ANNUAL_WORKING_HOURS_PER_FTE = 2100
ANNUAL_WORKING_MINUTES_PER_FTE = ANNUAL_WORKING_HOURS_PER_FTE * 60


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


def connected_process_chain(start_process):
    result = []
    seen = set()

    def walk(process):
        if not process or process.id in seen:
            return
        seen.add(process.id)
        result.append(process)

        for child in sorted(process.subprocesses, key=lambda p: p.id):
            walk(child)

    walk(start_process)
    return result


def collect_process_and_bpmn_subprocesses(process):
    result = []
    seen = set()

    def walk(p):
        if not p or p.id in seen:
            return
        seen.add(p.id)
        result.append(p)

        for node in p.nodes:
            if node.type == "subprocess" and node.subprocess:
                walk(node.subprocess)

    walk(process)
    return result


def collect_end_to_end_processes(start_process):
    result = []
    seen = set()

    for map_process in connected_process_chain(start_process):
        for p in collect_process_and_bpmn_subprocesses(map_process):
            if p.id not in seen:
                seen.add(p.id)
                result.append(p)

    return result


def split_minutes_by_fte(total_minutes, persons):
    active_persons = [p for p in persons if p and (p.fte or 0) > 0]

    if not active_persons:
        return {}

    total_fte = sum(p.fte or 0 for p in active_persons)
    if total_fte <= 0:
        return {}

    return {
        person.id: total_minutes * ((person.fte or 0) / total_fte)
        for person in active_persons
    }


def simulate_end_to_end(start_process, case_count):
    processes = collect_end_to_end_processes(start_process)

    person_minutes = defaultdict(float)
    activity_rows = []
    unassigned_activity_rows = []

    total_expected_minutes = 0.0
    assigned_minutes_total = 0.0
    unassigned_minutes_total = 0.0
    total_expected_costs = 0.0

    persons_by_id = {}

    for process in processes:
        factors = node_visit_factors(process)

        for node in process.nodes:
            if node.type != "task":
                continue

            visit_factor = factors.get(node.id, 1.0)
            expected_cases = case_count * visit_factor
            effort_per_case = node.effort_minutes or 0
            total_minutes = expected_cases * effort_per_case

            total_expected_minutes += total_minutes

            positions = list(node.assigned_positions or [])
            persons = [position.person for position in positions if position.person and (position.person.fte or 0) > 0]

            for person in persons:
                persons_by_id[person.id] = person

            split = split_minutes_by_fte(total_minutes, persons)
            assigned_minutes_for_activity = sum(split.values())
            unassigned_minutes_for_activity = max(0.0, total_minutes - assigned_minutes_for_activity)

            assigned_minutes_total += assigned_minutes_for_activity
            unassigned_minutes_total += unassigned_minutes_for_activity

            for person_id, minutes in split.items():
                person = persons_by_id[person_id]
                person_minutes[person_id] += minutes

                minute_cost = (person.annual_salary or 0) / ANNUAL_WORKING_MINUTES_PER_FTE
                total_expected_costs += minutes * minute_cost

            row = {
                "process": process,
                "node": node,
                "visit_factor": visit_factor,
                "expected_cases": expected_cases,
                "effort_per_case": effort_per_case,
                "total_minutes": total_minutes,
                "positions": positions,
                "persons": persons,
                "split": split,
                "assigned_minutes": assigned_minutes_for_activity,
                "unassigned_minutes": unassigned_minutes_for_activity,
                "assigned_ok": unassigned_minutes_for_activity <= 0.01,
            }

            activity_rows.append(row)

            if unassigned_minutes_for_activity > 0.01:
                unassigned_activity_rows.append(row)

    person_rows = []
    people_feasible = True
    total_fte = 0.0
    total_capacity_minutes = 0.0

    for person_id, minutes in sorted(person_minutes.items(), key=lambda item: persons_by_id[item[0]].name):
        person = persons_by_id[person_id]
        person_fte = person.fte or 0
        capacity = person_fte * ANNUAL_WORKING_MINUTES_PER_FTE
        utilization = minutes / capacity if capacity else 0

        total_fte += person_fte
        total_capacity_minutes += capacity

        if utilization > 1.0:
            people_feasible = False

        person_rows.append({
            "person": person,
            "minutes": minutes,
            "hours": minutes / 60,
            "capacity_minutes": capacity,
            "capacity_hours": capacity / 60,
            "utilization": utilization,
            "ok": utilization <= 1.0,
        })

    assigned_utilization = (
        assigned_minutes_total / total_capacity_minutes
        if total_capacity_minutes
        else 0
    )

    has_unassigned_work = unassigned_minutes_total > 0.01
    feasible = people_feasible and not has_unassigned_work

    return {
        "processes": processes,
        "activity_rows": activity_rows,
        "unassigned_activity_rows": unassigned_activity_rows,
        "person_rows": person_rows,
        "case_count": case_count,

        "total_expected_minutes": total_expected_minutes,
        "total_expected_hours": total_expected_minutes / 60,

        "assigned_minutes_total": assigned_minutes_total,
        "assigned_hours_total": assigned_minutes_total / 60,

        "unassigned_minutes_total": unassigned_minutes_total,
        "unassigned_hours_total": unassigned_minutes_total / 60,
        "has_unassigned_work": has_unassigned_work,

        "total_expected_costs": total_expected_costs,
        "total_fte": total_fte,
        "total_fte_percent": total_fte * 100,
        "total_capacity_minutes": total_capacity_minutes,
        "total_capacity_hours": total_capacity_minutes / 60,
        "assigned_utilization": assigned_utilization,

        "people_feasible": people_feasible,
        "annual_working_hours_per_fte": ANNUAL_WORKING_HOURS_PER_FTE,
        "feasible": feasible,
    }
