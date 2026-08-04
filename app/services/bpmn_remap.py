"""Schreibt die pros:-ID-Referenzen in einem BPMN-XML von alten auf neue IDs um.

Beim Import in einen anderen Account erhalten Funktionen/Rollen/Einheiten/Personen/
Prozesse neue IDs. Die im BPMN eingebetteten Referenzen (pros:functionIds usw.)
müssen entsprechend übersetzt werden. Rein textuell auf den bekannten, ganzzahligen
Attributwerten – kein Parsen von fremdem XML nötig.
"""
import re


def _remap_csv(value, m):
    out = []
    for part in value.split(","):
        part = part.strip()
        if not part.isdigit():
            continue
        old = int(part)
        if old in m:
            out.append(str(m[old]))
    return ",".join(out)


def remap_pros_ids(xml, func=None, role=None, unit=None, person=None, org=None, process=None):
    """Gibt das BPMN-XML mit umgeschriebenen pros:-ID-Referenzen zurück.
    Unbekannte IDs werden verworfen (die Referenz war im Zielaccount nicht vorhanden)."""
    func = func or {}
    role = role or {}
    unit = unit or {}
    person = person or {}
    org = org or {}
    process = process or {}

    def csv_attr(attr, m):
        return re.sub(
            r'(pros:%s=")([^"]*)(")' % attr,
            lambda mo: mo.group(1) + _remap_csv(mo.group(2), m) + mo.group(3), xml)

    xml = csv_attr("functionIds", func)
    xml = csv_attr("roleIds", role)
    xml = csv_attr("positionIds", unit)
    xml = csv_attr("personIds", person)

    def single(attr, m, prefix=""):
        def repl(mo):
            v = mo.group(2).strip()
            if v.isdigit() and int(v) in m:
                return mo.group(1) + prefix + str(m[int(v)]) + mo.group(3)
            return mo.group(1) + mo.group(3)   # unbekannt -> leeren
        return re.sub(r'(pros:%s=")([^"]*)(")' % attr, repl, xml)

    xml = single("orgUnitId", unit)
    xml = single("subprocessId", process)

    def ref(mo):
        v = mo.group(2)
        if v.startswith("unit:") and v[5:].isdigit() and int(v[5:]) in unit:
            return mo.group(1) + "unit:" + str(unit[int(v[5:])]) + mo.group(3)
        if v.startswith("org:") and v[4:].isdigit() and int(v[4:]) in org:
            return mo.group(1) + "org:" + str(org[int(v[4:])]) + mo.group(3)
        return mo.group(1) + mo.group(3)       # unbekannt -> leeren
    xml = re.sub(r'(pros:orgRef=")([^"]*)(")', ref, xml)

    return xml
