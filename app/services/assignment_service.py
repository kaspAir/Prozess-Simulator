"""Auflösung einer Drag'n'Drop-Zuordnung Person/Organisationseinheit → Aktivität.

Regeln (vom Nutzer vorgegeben):
- Person: die Person selbst; ihre Funktionen; ihre Rollen.
- Organisationseinheit: ALLE Personen im Teilbaum (die Einheit und alle
  untergeordneten Einheiten) werden zugeordnet. Für die Funktionen gilt der
  «kleinste gemeinsame Nenner» = die SCHNITTMENGE der Funktionen dieser
  Personen (nur was wirklich alle können). Für die Rollen gilt die
  VEREINIGUNG = alle Rollen, die diese Personen zusammen abdecken.

Rein lesend; account-scoped. Die Logik ist bewusst hier (nicht im Browser),
damit sie deterministisch testbar bleibt.
"""
from app.models import OrgUnit, Organization, Person


def _subtree_units(unit):
    """Die Einheit und alle (transitiven) Unter-Einheiten."""
    result, stack = [], [unit]
    seen = set()
    while stack:
        u = stack.pop()
        if u.id in seen:
            continue
        seen.add(u.id)
        result.append(u)
        stack.extend(u.children)
    return result


def _persons_of_units(units):
    """Distinct Personen, die die Einheiten (Stellen) besetzen – Reihenfolge stabil."""
    persons, seen = [], set()
    for u in units:
        if u.person_id and u.person_id not in seen and u.person is not None:
            seen.add(u.person_id)
            persons.append(u.person)
    return persons


def resolve_assignment(account_id, source_type, source_id):
    """Gibt ein dict {person_ids, function_ids, role_ids, label, person_count}
    zurück oder None, wenn die Quelle nicht (im Account) existiert."""
    if source_type == "person":
        p = Person.query.filter_by(id=source_id).first()
        if p is None or (account_id is not None and p.account_id != account_id):
            return None
        return {
            "person_ids": [p.id],
            "function_ids": sorted({f.id for f in p.functions}),
            "role_ids": sorted({r.id for r in p.roles}),
            "label": p.name,
            "person_count": 1,
        }

    if source_type == "unit":
        q = OrgUnit.query.join(Organization).filter(OrgUnit.id == source_id)
        if account_id is not None:
            q = q.filter(Organization.account_id == account_id)
        unit = q.first()
        if unit is None:
            return None
        persons = _persons_of_units(_subtree_units(unit))
        func_sets = [{f.id for f in p.functions} for p in persons]
        common = set.intersection(*func_sets) if func_sets else set()
        roles = set()
        for p in persons:
            roles.update(r.id for r in p.roles)
        return {
            "person_ids": [p.id for p in persons],
            "function_ids": sorted(common),
            "role_ids": sorted(roles),
            "label": unit.name,
            "person_count": len(persons),
        }

    return None
