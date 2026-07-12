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
