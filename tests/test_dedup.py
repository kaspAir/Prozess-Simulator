"""Duplikate zusammenführen: gleichnamige Rollen/Funktionen verschmelzen,
Verweise (Personen, BPMN) umhängen, Deckungslücken durch ID-Mismatch verschwinden."""


def test_merge_duplicates(app):
    from app.models import db, Account, Organization, OrgUnit, Role, Function, Person, Process
    from app.services.dedup_service import merge_duplicates
    from app.services.bpmn_simulation import analyze_bpmn

    with app.app_context():
        acc = Account(name="D"); db.session.add(acc); db.session.flush()
        f1 = Function(name="Prüfen", account_id=acc.id)      # kanonisch (kleinere id)
        f2 = Function(name="Prüfen", account_id=acc.id)      # Dublette
        db.session.add_all([f1, f2]); db.session.flush()
        r1 = Role(name="Jurist", account_id=acc.id); r1.functions = [f1]   # kanonisch
        r2 = Role(name="Jurist", account_id=acc.id); r2.functions = [f2]   # Dublette
        db.session.add_all([r1, r2]); db.session.flush()
        org = Organization(name="O", account_id=acc.id); db.session.add(org); db.session.flush()
        person = Person(name="P", account_id=acc.id, organization_id=org.id,
                        fte=1.0, annual_salary=126000)
        person.roles = [r1]                                   # Person hat die kanonische Rolle
        db.session.add(person); db.session.flush()
        pos = OrgUnit(organization_id=org.id, name="Stelle", unit_type="Stelle",
                      person_id=person.id)
        db.session.add(pos); db.session.flush()
        # Aktivität verlangt die DUBLETTEN (r2/f2) -> vor Merge Deckungslücke
        xml = (
            '<?xml version="1.0"?><bpmn:definitions '
            'xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
            'xmlns:pros="http://ditwi.ch/bpmn/pros" id="D" targetNamespace="x">'
            '<bpmn:process id="P"><bpmn:startEvent id="s0"/>'
            f'<bpmn:task id="A" name="A" pros:effortMinutes="10" '
            f'pros:positionIds="{pos.id}" pros:functionIds="{f2.id}" pros:roleIds="{r2.id}"/>'
            '<bpmn:sequenceFlow id="f" sourceRef="s0" targetRef="A"/>'
            '</bpmn:process></bpmn:definitions>'
        )
        proc = Process(name="Pr", account_id=acc.id, bpmn_xml=xml)
        db.session.add(proc); db.session.commit()

        assert analyze_bpmn(proc)["activities"][0]["gaps"], "vor Merge sollte eine Lücke bestehen"

        counts = merge_duplicates(acc.id)
        assert counts == {"functions_merged": 1, "roles_merged": 1, "persons_merged": 0}
        assert Function.query.filter_by(account_id=acc.id).count() == 1
        assert Role.query.filter_by(account_id=acc.id).count() == 1

        proc2 = db.session.get(Process, proc.id)
        # BPMN zeigt jetzt auf die kanonischen IDs …
        assert ('pros:functionIds="%d"' % f1.id) in proc2.bpmn_xml
        assert ('pros:roleIds="%d"' % r1.id) in proc2.bpmn_xml
        # … und die Deckungslücke ist weg (Person deckt r1/f1)
        assert analyze_bpmn(proc2)["activities"][0]["gaps"] == []


def test_merge_duplicate_persons(app):
    """Gleichnamige Personen werden zusammengeführt; Stelle und pros:personIds
    zeigen danach auf die kanonische Person."""
    from app.models import db, Account, Organization, OrgUnit, Person, Process
    from app.services.dedup_service import merge_duplicates
    with app.app_context():
        acc = Account(name="DP"); db.session.add(acc); db.session.flush()
        org = Organization(name="O", account_id=acc.id); db.session.add(org); db.session.flush()
        a1 = Person(name="Anna", account_id=acc.id, organization_id=org.id, fte=1.0, annual_salary=100)
        a2 = Person(name="Anna", account_id=acc.id, organization_id=org.id, fte=1.0, annual_salary=100)
        db.session.add_all([a1, a2]); db.session.flush()
        st = OrgUnit(organization_id=org.id, name="Stelle", unit_type="Stelle", person_id=a2.id)
        db.session.add(st); db.session.flush()
        xml = (
            '<?xml version="1.0"?><bpmn:definitions '
            'xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
            'xmlns:pros="http://ditwi.ch/bpmn/pros" id="D" targetNamespace="x">'
            '<bpmn:process id="P"><bpmn:startEvent id="s0"/>'
            f'<bpmn:task id="A" name="A" pros:effortMinutes="10" pros:personIds="{a2.id}"/>'
            '<bpmn:sequenceFlow id="f" sourceRef="s0" targetRef="A"/>'
            '</bpmn:process></bpmn:definitions>'
        )
        pr = Process(name="P", account_id=acc.id, bpmn_xml=xml)
        db.session.add(pr); db.session.commit()

        counts = merge_duplicates(acc.id)
        assert counts["persons_merged"] == 1
        assert Person.query.filter_by(account_id=acc.id, name="Anna").count() == 1
        st2 = db.session.get(OrgUnit, st.id)
        assert st2.person_id == a1.id                       # Stelle auf kanonische Person
        assert ('pros:personIds="%d"' % a1.id) in db.session.get(Process, pr.id).bpmn_xml
