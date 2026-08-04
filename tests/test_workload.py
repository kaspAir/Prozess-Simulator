"""Punkt 3: prozessübergreifende Personen-Auslastung."""


def _task_xml(effort, pos_id):
    return (
        '<?xml version="1.0"?><bpmn:definitions '
        'xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
        'xmlns:pros="http://ditwi.ch/bpmn/pros" id="D" targetNamespace="x">'
        '<bpmn:process id="P"><bpmn:startEvent id="s0"/>'
        f'<bpmn:task id="A" name="A" pros:effortMinutes="{effort}" pros:positionIds="{pos_id}"/>'
        '<bpmn:sequenceFlow id="f" sourceRef="s0" targetRef="A"/>'
        '</bpmn:process></bpmn:definitions>'
    )


def test_workload_sums_person_across_processes(app):
    from app.models import db, Account, Organization, OrgUnit, Person, Process
    from app.services.workload_service import cross_process_workload
    with app.app_context():
        acc = Account(name="W"); db.session.add(acc); db.session.flush()
        org = Organization(name="O", account_id=acc.id); db.session.add(org); db.session.flush()
        person = Person(name="Anna", account_id=acc.id, organization_id=org.id,
                        fte=1.0, annual_salary=126000)
        db.session.add(person); db.session.flush()
        pos = OrgUnit(organization_id=org.id, name="Stelle", unit_type="Stelle",
                      person_id=person.id)
        db.session.add(pos); db.session.flush()
        p1 = Process(name="P1", account_id=acc.id, bpmn_xml=_task_xml(60, pos.id))
        p2 = Process(name="P2", account_id=acc.id, bpmn_xml=_task_xml(60, pos.id))
        db.session.add_all([p1, p2]); db.session.commit()

        res = cross_process_workload(acc.id, {p1.id: 1200, p2.id: 1200})
        assert len(res["persons"]) == 1
        r = res["persons"][0]
        # (60*1200 + 60*1200) Min = 144000 Min = 2400 h/Jahr
        assert abs(r["load_h"] - 2400) < 0.1
        assert abs(r["capacity_h"] - 2100) < 0.1      # 1.0 FTE * 2100 h
        assert r["util"] > 1.0 and r["status"] == "Engpass"


def test_workload_splits_effort_among_assigned_persons(app):
    """Zwei zugeordnete Personen teilen sich den Aufwand einer Aktivität."""
    from app.models import db, Account, Organization, OrgUnit, Person, Process
    from app.services.workload_service import cross_process_workload
    with app.app_context():
        acc = Account(name="W2"); db.session.add(acc); db.session.flush()
        org = Organization(name="O", account_id=acc.id); db.session.add(org); db.session.flush()
        a = Person(name="A", account_id=acc.id, organization_id=org.id, fte=1.0, annual_salary=1)
        b = Person(name="B", account_id=acc.id, organization_id=org.id, fte=1.0, annual_salary=1)
        db.session.add_all([a, b]); db.session.flush()
        sa = OrgUnit(organization_id=org.id, name="SA", unit_type="Stelle", person_id=a.id)
        sb = OrgUnit(organization_id=org.id, name="SB", unit_type="Stelle", person_id=b.id)
        db.session.add_all([sa, sb]); db.session.flush()
        xml = _task_xml(60, "%d,%d" % (sa.id, sb.id))
        pr = Process(name="P", account_id=acc.id, bpmn_xml=xml)
        db.session.add(pr); db.session.commit()

        res = cross_process_workload(acc.id, {pr.id: 100})
        loads = {r["name"]: r["load_h"] for r in res["persons"]}
        # 60 Min * 100 = 6000 Min, geteilt -> je 3000 Min = 50 h
        assert abs(loads["A"] - 50) < 0.1
        assert abs(loads["B"] - 50) < 0.1
