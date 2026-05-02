from sqlalchemy import text
from app.app import app, db
from app.models import Organization, Person

with app.app_context():
    db.create_all()

    with db.engine.begin() as conn:
        conn.execute(text("ALTER TABLE persons ADD COLUMN IF NOT EXISTS organization_id INTEGER"))
        conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM information_schema.table_constraints
                    WHERE constraint_name = 'persons_organization_id_fkey'
                ) THEN
                    ALTER TABLE persons
                    ADD CONSTRAINT persons_organization_id_fkey
                    FOREIGN KEY (organization_id) REFERENCES organizations(id);
                END IF;
            END
            $$;
        """))

    default_org = Organization.query.order_by(Organization.id).first()

    if default_org:
        persons_without_org = Person.query.filter(Person.organization_id.is_(None)).all()
        for person in persons_without_org:
            person.organization_id = default_org.id
            db.session.add(person)
        db.session.commit()
        print(f"OK: Personen ohne Organisation wurden '{default_org.name}' zugeordnet.")
    else:
        print("OK: Spalte organization_id erstellt. Keine Organisation vorhanden.")
