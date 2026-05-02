from app.app import app, db
from app.models import Organization, OrgUnit, Role

with app.app_context():
    db.create_all()

    if not Organization.query.first():
        org = Organization(name="Staatsanwaltschaft Beispiel", description="Demo-Aufbauorganisation")
        db.session.add(org)
        db.session.commit()

        root = OrgUnit(organization=org, name="Staatsanwaltschaft", unit_type="Organisation", sort_order=0)
        direktion = OrgUnit(organization=org, parent=root, name="Direktion", unit_type="Departement", sort_order=1)
        verfahren = OrgUnit(organization=org, parent=root, name="Verfahrensführung", unit_type="Abteilung", sort_order=2)
        kanzlei = OrgUnit(organization=org, parent=root, name="Kanzlei", unit_type="Team", sort_order=3)
        db.session.add_all([root, direktion, verfahren, kanzlei])
        db.session.commit()

        for role in Role.query.all():
            if "Leitende" in role.name:
                direktion.roles.append(role)
            elif "Kanzlei" in role.name:
                kanzlei.roles.append(role)
            else:
                verfahren.roles.append(role)

        db.session.commit()

    print("OK: Organisationstabellen vorhanden und Demo-Organisation angelegt, falls nötig.")
