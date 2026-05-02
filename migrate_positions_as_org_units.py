from sqlalchemy import text
from app.app import app, db
from app.models import Organization, OrgUnit, Person

with app.app_context():
    db.create_all()

    with db.engine.begin() as conn:
        conn.execute(text("ALTER TABLE org_units ADD COLUMN IF NOT EXISTS person_id INTEGER"))
        conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM information_schema.table_constraints
                    WHERE constraint_name = 'org_units_person_id_fkey'
                ) THEN
                    ALTER TABLE org_units
                    ADD CONSTRAINT org_units_person_id_fkey
                    FOREIGN KEY (person_id) REFERENCES persons(id);
                END IF;
            END
            $$;
        """))

    # Für bestehende Personen ohne Stelle je eine Stelle unter der ersten passenden Organisationseinheit erzeugen.
    for org in Organization.query.all():
        root = OrgUnit.query.filter_by(organization_id=org.id, parent_id=None).order_by(OrgUnit.id).first()
        if not root:
            root = OrgUnit(organization=org, name=org.name, unit_type="Organisation", sort_order=0)
            db.session.add(root)
            db.session.commit()

        persons = Person.query.filter_by(organization_id=org.id).all()
        for person in persons:
            existing_position = OrgUnit.query.filter_by(person_id=person.id, unit_type="Stelle").first()
            if existing_position:
                continue

            position = OrgUnit(
                organization=org,
                parent=root,
                name=f"Stelle {person.name}",
                unit_type="Stelle",
                person_id=person.id,
                sort_order=100,
            )

            for role in person.roles:
                position.roles.append(role)

            db.session.add(position)

    db.session.commit()
    print("OK: Stellenmodell vorbereitet. Bestehende Personen haben bei Bedarf eine Stelle erhalten.")
