"""Zusammenführen gleichnamiger Rollen und Funktionen eines Accounts.

Mehrfach-Importe legen Rollen/Funktionen additiv an -> gleiche Namen mehrfach mit
verschiedenen IDs. Das verfälscht die Deckungsprüfung (Bedarf zeigt auf Kopie A,
die Person hat Kopie B) und bläht die Organisation auf. Diese Funktion behält je
Name den ältesten Datensatz (kanonisch), hängt ALLE Verweise darauf um
(Rollen->Funktionen, Personen, Stellen, Nodes und die pros:-IDs im BPMN) und
löscht die Dubletten.
"""
from app.models import (
    db, Organization, OrgUnit, Role, Function, Person, Process, Node,
)
from app.services.bpmn_remap import remap_pros_ids


def _canon_map(objs):
    """objs nach id sortiert -> (map old_id->canon_id, {id: obj}, [dubletten])."""
    canon_by_name, id_map, obj_by_id, dups = {}, {}, {}, []
    for o in objs:
        obj_by_id[o.id] = o
        key = (o.name or "").strip().lower()
        if key not in canon_by_name:
            canon_by_name[key] = o
        canon = canon_by_name[key]
        id_map[o.id] = canon.id
        if canon.id != o.id:
            dups.append(o)
    return id_map, obj_by_id, dups


def merge_duplicates(account_id):
    funcs = Function.query.filter_by(account_id=account_id).order_by(Function.id).all()
    roles = Role.query.filter_by(account_id=account_id).order_by(Role.id).all()
    fmap, fobj, dup_funcs = _canon_map(funcs)
    rmap, robj, dup_roles = _canon_map(roles)

    def canon_functions(items):
        seen, out = set(), []
        for f in items:
            cid = fmap.get(f.id, f.id)
            if cid not in seen:
                seen.add(cid)
                out.append(fobj[cid])
        return out

    def canon_roles(items):
        seen, out = set(), []
        for r in items:
            cid = rmap.get(r.id, r.id)
            if cid not in seen:
                seen.add(cid)
                out.append(robj[cid])
        return out

    # Rollen: ihre Funktionen (kanonisch) + parent-Selbstbezug
    for r in roles:
        if r.functions:
            r.functions = canon_functions(r.functions)
        if r.parent_id in rmap:
            r.parent_id = rmap[r.parent_id]
    # Personen: Rollen + Funktionen
    for p in Person.query.filter_by(account_id=account_id).all():
        if p.roles:
            p.roles = canon_roles(p.roles)
        if p.functions:
            p.functions = canon_functions(p.functions)
    # Stellen/Einheiten: Rollen
    for u in (OrgUnit.query.join(Organization)
              .filter(Organization.account_id == account_id).all()):
        if u.roles:
            u.roles = canon_roles(u.roles)
    # Nodes (altes Modell): Rollen + benötigte Funktionen
    for n in (Node.query.join(Process, Node.process_id == Process.id)
              .filter(Process.account_id == account_id).all()):
        if n.roles:
            n.roles = canon_roles(n.roles)
        if n.required_functions:
            n.required_functions = canon_functions(n.required_functions)
    db.session.flush()

    # BPMN-Modelle: pros:functionIds/roleIds auf die kanonischen IDs umschreiben
    for pr in Process.query.filter_by(account_id=account_id).all():
        xml = (pr.bpmn_xml or "").strip()
        if xml:
            pr.bpmn_xml = remap_pros_ids(xml, func=fmap, role=rmap)

    for o in dup_funcs + dup_roles:
        db.session.delete(o)
    db.session.commit()
    return {"functions_merged": len(dup_funcs), "roles_merged": len(dup_roles)}
