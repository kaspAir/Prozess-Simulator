"""Rechen-Service: Aufwand/Kosten aus dem BPMN-Modell (roh & erwartet)."""
from app.services.bpmn_simulation import analyze_bpmn

XOR_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
    'xmlns:pros="http://ditwi.ch/bpmn/pros" id="D" targetNamespace="x">'
    '<bpmn:process id="P">'
    '<bpmn:startEvent id="S"/>'
    '<bpmn:exclusiveGateway id="G"/>'
    '<bpmn:task id="A" name="A" pros:effortMinutes="100"/>'
    '<bpmn:task id="B" name="B" pros:effortMinutes="50"/>'
    '<bpmn:sequenceFlow id="s1" sourceRef="S" targetRef="G"/>'
    '<bpmn:sequenceFlow id="f1" sourceRef="G" targetRef="A" pros:probability="60"/>'
    '<bpmn:sequenceFlow id="f2" sourceRef="G" targetRef="B" pros:probability="40"/>'
    '</bpmn:process></bpmn:definitions>'
)


class _Proc:
    def __init__(self, xml, account_id=None):
        self.bpmn_xml = xml
        self.account_id = account_id


def test_effort_raw_and_expected():
    res = analyze_bpmn(_Proc(XOR_XML))
    assert res["has_model"]
    assert abs(res["total_effort"] - 150) < 1e-6          # 100 + 50
    assert abs(res["expected_effort"] - 80) < 1e-6        # 100*0.6 + 50*0.4
    assert res["total_cost"] == 0 and res["expected_cost"] == 0   # keine Stellen -> 0


def test_xor_merge_sums_to_full_visit():
    """Zwei XOR-Zweige (60/40), die wieder zusammenlaufen: der Merge-Node wird von
    100% der Fälle besucht, nicht nur vom stärkeren Zweig."""
    xml = (
        '<?xml version="1.0"?><bpmn:definitions '
        'xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
        'xmlns:pros="http://ditwi.ch/bpmn/pros" id="D" targetNamespace="x">'
        '<bpmn:process id="P"><bpmn:startEvent id="s0"/>'
        '<bpmn:exclusiveGateway id="g"/>'
        '<bpmn:task id="ja" name="Direkt" pros:effortMinutes="10"/>'
        '<bpmn:task id="nein" name="Umweg" pros:effortMinutes="10"/>'
        '<bpmn:task id="m" name="Merge" pros:effortMinutes="50"/>'
        '<bpmn:sequenceFlow id="a" sourceRef="s0" targetRef="g"/>'
        '<bpmn:sequenceFlow id="b" sourceRef="g" targetRef="ja" pros:probability="60"/>'
        '<bpmn:sequenceFlow id="c" sourceRef="g" targetRef="nein" pros:probability="40"/>'
        '<bpmn:sequenceFlow id="d" sourceRef="ja" targetRef="m"/>'
        '<bpmn:sequenceFlow id="e" sourceRef="nein" targetRef="m"/>'
        '</bpmn:process></bpmn:definitions>'
    )
    res = analyze_bpmn(_Proc(xml))
    m = next(a for a in res["activities"] if a["id"] == "m")
    assert abs(m["visit_factor"] - 1.0) < 1e-6            # 0.6 + 0.4
    assert abs(res["expected_effort"] - 60) < 1e-6        # 10*.6 + 10*.4 + 50*1


def test_xor_unset_probs_split_equally():
    """XOR ohne gesetzte Prozente: die Zweige teilen sich 100% gleichmässig (50/50),
    an der Zusammenführung ergibt das 100% – nicht 200%."""
    xml = (
        '<?xml version="1.0"?><bpmn:definitions '
        'xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
        'xmlns:pros="http://ditwi.ch/bpmn/pros" id="D" targetNamespace="x">'
        '<bpmn:process id="P"><bpmn:startEvent id="s0"/>'
        '<bpmn:exclusiveGateway id="g"/>'
        '<bpmn:task id="ja" name="A" pros:effortMinutes="10"/>'
        '<bpmn:task id="nein" name="B" pros:effortMinutes="10"/>'
        '<bpmn:task id="m" name="M" pros:effortMinutes="50"/>'
        '<bpmn:sequenceFlow id="a" sourceRef="s0" targetRef="g"/>'
        '<bpmn:sequenceFlow id="b" sourceRef="g" targetRef="ja"/>'
        '<bpmn:sequenceFlow id="c" sourceRef="g" targetRef="nein"/>'
        '<bpmn:sequenceFlow id="d" sourceRef="ja" targetRef="m"/>'
        '<bpmn:sequenceFlow id="e" sourceRef="nein" targetRef="m"/>'
        '</bpmn:process></bpmn:definitions>'
    )
    res = analyze_bpmn(_Proc(xml))
    m = next(a for a in res["activities"] if a["id"] == "m")
    assert abs(m["visit_factor"] - 1.0) < 1e-6            # 0.5 + 0.5, nicht 2.0
    assert abs(res["expected_effort"] - 60) < 1e-6        # 10*.5 + 10*.5 + 50*1


def test_empty_model():
    res = analyze_bpmn(_Proc(""))
    assert res["has_model"] is False
    assert res["total_effort"] == 0


def test_cost_from_assigned_position(app):
    from app.models import db, Account, Organization, OrgUnit, Person, Process
    with app.app_context():
        acc = Account(name="Acc"); db.session.add(acc); db.session.flush()
        org = Organization(name="Org", account_id=acc.id); db.session.add(org); db.session.flush()
        person = Person(name="P", account_id=acc.id, organization_id=org.id,
                        fte=1.0, annual_salary=126000, active=True)   # -> 1.0 CHF/Min
        db.session.add(person); db.session.flush()
        pos = OrgUnit(organization_id=org.id, name="Stelle", unit_type="Stelle",
                      person_id=person.id)
        db.session.add(pos); db.session.flush()
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
            'xmlns:pros="http://ditwi.ch/bpmn/pros" id="D" targetNamespace="x">'
            '<bpmn:process id="P"><bpmn:startEvent id="S"/>'
            f'<bpmn:task id="A" name="A" pros:effortMinutes="60" pros:positionIds="{pos.id}"/>'
            '<bpmn:sequenceFlow id="s1" sourceRef="S" targetRef="A"/>'
            '</bpmn:process></bpmn:definitions>'
        )
        proc = Process(name="Proc", account_id=acc.id, bpmn_xml=xml)
        db.session.add(proc); db.session.commit()

        res = analyze_bpmn(proc)
        assert abs(res["total_effort"] - 60) < 1e-6
        assert abs(res["total_cost"] - 60) < 1e-6         # 60 Min x 1.0 CHF/Min
        assert abs(res["expected_cost"] - 60) < 1e-6      # kein Gateway -> Faktor 1
        assert res["activities"][0]["positions"] == ["Stelle"]


def test_analyze_falls_back_to_node_model(app):
    """Prozess ohne gespeichertes BPMN, aber mit Node-Modell -> Analyse rechnet
    (der Generator springt ein, wie im Editor)."""
    from app.models import db, Account, Process, Node, Edge
    with app.app_context():
        acc = Account(name="AccN"); db.session.add(acc); db.session.flush()
        proc = Process(name="NodeProc", account_id=acc.id)      # kein bpmn_xml
        db.session.add(proc); db.session.flush()
        n1 = Node(process_id=proc.id, type="start", name="Start", x=50, y=50, sort_order=0)
        n2 = Node(process_id=proc.id, type="task", name="T", effort_minutes=25,
                  x=180, y=50, sort_order=1)
        n3 = Node(process_id=proc.id, type="end", name="Ende", x=320, y=50, sort_order=2)
        db.session.add_all([n1, n2, n3]); db.session.flush()
        db.session.add_all([Edge(source_node_id=n1.id, target_node_id=n2.id),
                            Edge(source_node_id=n2.id, target_node_id=n3.id)])
        db.session.commit()
        res = analyze_bpmn(proc)
        assert res["has_model"]
        assert abs(res["total_effort"] - 25) < 1e-6


def test_subprocess_rolled_into_parent(app):
    """CallActivity mit pros:subprocessId zieht Aufwand/Kosten des Subprozesses in
    den Elternprozess (erwartet mit der Besuchshäufigkeit gewichtet)."""
    from app.models import db, Account, Process
    with app.app_context():
        acc = Account(name="AccSub"); db.session.add(acc); db.session.flush()
        child = Process(name="Abklärungen", account_id=acc.id, bpmn_xml=(
            '<?xml version="1.0"?><bpmn:definitions '
            'xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
            'xmlns:pros="http://ditwi.ch/bpmn/pros" id="D" targetNamespace="x">'
            '<bpmn:process id="S"><bpmn:startEvent id="s0"/>'
            '<bpmn:task id="ct" name="Abklärung" pros:effortMinutes="30"/>'
            '<bpmn:sequenceFlow id="sf" sourceRef="s0" targetRef="ct"/>'
            '</bpmn:process></bpmn:definitions>'))
        db.session.add(child); db.session.flush()
        parent = Process(name="Haupt", account_id=acc.id, bpmn_xml=(
            '<?xml version="1.0"?><bpmn:definitions '
            'xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
            'xmlns:pros="http://ditwi.ch/bpmn/pros" id="D" targetNamespace="x">'
            '<bpmn:process id="P"><bpmn:startEvent id="p0"/>'
            '<bpmn:task id="pt" name="Erstellen" pros:effortMinutes="20"/>'
            f'<bpmn:callActivity id="ca" name="Zusätzliche" pros:subprocessId="{child.id}"/>'
            '<bpmn:sequenceFlow id="f1" sourceRef="p0" targetRef="pt"/>'
            '<bpmn:sequenceFlow id="f2" sourceRef="pt" targetRef="ca"/>'
            '</bpmn:process></bpmn:definitions>'))
        db.session.add(parent); db.session.commit()

        res = analyze_bpmn(parent)
        assert abs(res["total_effort"] - 50) < 1e-6      # 20 + Subprozess 30
        assert abs(res["expected_effort"] - 50) < 1e-6   # CallActivity-Faktor 1
        assert any(a.get("subprocess") for a in res["activities"])


def _proc_xml(pid, effort, call_to=None):
    call = ('<bpmn:callActivity id="c_%s" name="ruf" pros:subprocessId="%d"/>'
            % (pid, call_to)) if call_to else ""
    return (
        '<?xml version="1.0"?><bpmn:definitions '
        'xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
        'xmlns:pros="http://ditwi.ch/bpmn/pros" id="D" targetNamespace="x">'
        '<bpmn:process id="%s"><bpmn:startEvent id="s_%s"/>'
        '<bpmn:task id="t_%s" name="T_%s" pros:effortMinutes="%d"/>'
        '%s</bpmn:process></bpmn:definitions>' % (pid, pid, pid, pid, effort, call))


def test_subprocess_nested_and_cycle_safe(app):
    """Generisch & rekursiv: A ruft B ruft C (verschachtelt); ein Ringverweis
    C->A darf nicht endlos laufen. Aufwand = 20+5+10 = 35."""
    from app.models import db, Account, Process
    with app.app_context():
        acc = Account(name="AccNest"); db.session.add(acc); db.session.flush()
        a = Process(name="A", account_id=acc.id); db.session.add(a)
        b = Process(name="B", account_id=acc.id); db.session.add(b)
        c = Process(name="C", account_id=acc.id); db.session.add(c)
        db.session.flush()
        a.bpmn_xml = _proc_xml("A", 20, call_to=b.id)
        b.bpmn_xml = _proc_xml("B", 5, call_to=c.id)
        c.bpmn_xml = _proc_xml("C", 10, call_to=a.id)   # Ringverweis
        db.session.commit()
        res = analyze_bpmn(a)
        assert abs(res["total_effort"] - 35) < 1e-6     # A + B + C, jeder einmal


def test_coverage_gap_flags_missing_function(app):
    """Punkt 1: hat die zugeordnete Person die benötigte Funktion nicht, wird eine
    Lücke gemeldet; hat sie sie, verschwindet die Lücke."""
    from app.models import db, Account, Organization, OrgUnit, Person, Function, Process
    with app.app_context():
        acc = Account(name="AccCov"); db.session.add(acc); db.session.flush()
        org = Organization(name="O", account_id=acc.id); db.session.add(org); db.session.flush()
        f_need = Function(name="Prüfen", account_id=acc.id)
        f_have = Function(name="Tippen", account_id=acc.id)
        db.session.add_all([f_need, f_have]); db.session.flush()
        person = Person(name="P", account_id=acc.id, organization_id=org.id,
                        fte=1.0, annual_salary=126000)
        person.functions = [f_have]                      # hat NICHT «Prüfen»
        db.session.add(person); db.session.flush()
        pos = OrgUnit(organization_id=org.id, name="Stelle", unit_type="Stelle",
                      person_id=person.id)
        db.session.add(pos); db.session.flush()
        xml = (
            '<?xml version="1.0"?><bpmn:definitions '
            'xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
            'xmlns:pros="http://ditwi.ch/bpmn/pros" id="D" targetNamespace="x">'
            '<bpmn:process id="P"><bpmn:startEvent id="s0"/>'
            f'<bpmn:task id="A" name="A" pros:effortMinutes="10" '
            f'pros:positionIds="{pos.id}" pros:functionIds="{f_need.id}"/>'
            '<bpmn:sequenceFlow id="f" sourceRef="s0" targetRef="A"/>'
            '</bpmn:process></bpmn:definitions>'
        )
        proc = Process(name="Pr", account_id=acc.id, bpmn_xml=xml)
        db.session.add(proc); db.session.commit()

        a = analyze_bpmn(proc)["activities"][0]
        assert any("Prüfen" in g for g in a["gaps"])       # Lücke gemeldet

        person.functions = [f_have, f_need]; db.session.commit()
        a2 = analyze_bpmn(proc)["activities"][0]
        assert a2["gaps"] == []                            # Lücke geschlossen


def test_distributes_by_role_all_holders(app):
    """Fordert eine Aktivität eine Rolle (ohne konkrete Person), zählen ALLE
    Personen mit dieser Rolle, die eine Stelle besetzen."""
    from app.models import db, Account, Organization, OrgUnit, Person, Role, Process
    with app.app_context():
        acc = Account(name="R"); db.session.add(acc); db.session.flush()
        org = Organization(name="O", account_id=acc.id); db.session.add(org); db.session.flush()
        role = Role(name="Staatsanwalt", account_id=acc.id); db.session.add(role); db.session.flush()
        p1 = Person(name="SA1", account_id=acc.id, organization_id=org.id, fte=1.0, annual_salary=1)
        p2 = Person(name="SA2", account_id=acc.id, organization_id=org.id, fte=1.0, annual_salary=1)
        p3 = Person(name="Ohne", account_id=acc.id, organization_id=org.id, fte=1.0, annual_salary=1)
        p1.roles = [role]; p2.roles = [role]        # p3 hat die Rolle NICHT
        db.session.add_all([p1, p2, p3]); db.session.flush()
        # p1/p2 besetzen eine Stelle; ein role-Träger ohne Stelle zählt nicht
        db.session.add_all([
            OrgUnit(organization_id=org.id, name="S1", unit_type="Stelle", person_id=p1.id),
            OrgUnit(organization_id=org.id, name="S2", unit_type="Stelle", person_id=p2.id),
        ]); db.session.flush()
        xml = (
            '<?xml version="1.0"?><bpmn:definitions '
            'xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
            'xmlns:pros="http://ditwi.ch/bpmn/pros" id="D" targetNamespace="x">'
            '<bpmn:process id="P"><bpmn:startEvent id="s0"/>'
            f'<bpmn:task id="A" name="A" pros:effortMinutes="10" pros:roleIds="{role.id}"/>'
            '<bpmn:sequenceFlow id="f" sourceRef="s0" targetRef="A"/>'
            '</bpmn:process></bpmn:definitions>'
        )
        proc = Process(name="P", account_id=acc.id, bpmn_xml=xml)
        db.session.add(proc); db.session.commit()
        a = analyze_bpmn(proc)["activities"][0]
        assert {p["name"] for p in a["persons"]} == {"SA1", "SA2"}


def test_cost_prefers_selected_person(app):
    """Sind konkrete Mitarbeitende gewählt (personIds), zählt deren Kostensatz."""
    from app.models import db, Account, Organization, OrgUnit, Person, Process
    with app.app_context():
        acc = Account(name="Acc2"); db.session.add(acc); db.session.flush()
        org = Organization(name="Org", account_id=acc.id); db.session.add(org); db.session.flush()
        p_stelle = Person(name="Günstig", account_id=acc.id, organization_id=org.id,
                          fte=1.0, annual_salary=126000)      # -> 1.0/Min
        p_selected = Person(name="Teuer", account_id=acc.id, organization_id=org.id,
                            fte=1.0, annual_salary=252000)     # -> 2.0/Min
        db.session.add_all([p_stelle, p_selected]); db.session.flush()
        pos = OrgUnit(organization_id=org.id, name="Stelle", unit_type="Stelle",
                      person_id=p_stelle.id)
        db.session.add(pos); db.session.flush()
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
            'xmlns:pros="http://ditwi.ch/bpmn/pros" id="D" targetNamespace="x">'
            '<bpmn:process id="P"><bpmn:startEvent id="S"/>'
            f'<bpmn:task id="A" name="A" pros:effortMinutes="60" '
            f'pros:positionIds="{pos.id}" pros:personIds="{p_selected.id}"/>'
            '<bpmn:sequenceFlow id="s1" sourceRef="S" targetRef="A"/>'
            '</bpmn:process></bpmn:definitions>'
        )
        proc = Process(name="Proc", account_id=acc.id, bpmn_xml=xml)
        db.session.add(proc); db.session.commit()
        res = analyze_bpmn(proc)
        assert abs(res["total_cost"] - 120) < 1e-6        # 60 x 2.0 (gewählte Person), nicht 1.0
