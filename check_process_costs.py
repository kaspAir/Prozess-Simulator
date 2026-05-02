from app.app import app
from app.models import Process, Node

with app.app_context():
    processes = Process.query.order_by(Process.id).all()

    for process in processes:
        print("=" * 80)
        print(f"Prozess {process.id}: {process.name}")
        print(f"Owner: {process.owner_org_unit.name if getattr(process, 'owner_org_unit', None) else 'kein Owner'}")

        nodes = Node.query.filter_by(process_id=process.id).order_by(Node.sort_order, Node.id).all()
        process_total = 0

        for node in nodes:
            if node.type != "task":
                continue

            print(f"\n  Aktivität {node.id}: {node.name}")
            print(f"  Aufwand: {node.effort_minutes} Min.")

            positions = list(getattr(node, "assigned_positions", []))
            if not positions:
                print("  WARNUNG: Keine Stelle zugeordnet.")
                continue

            node_total = 0
            for position in positions:
                person = getattr(position, "person", None)
                print(f"  Stelle: {position.name}")

                if not person:
                    print("    WARNUNG: Stelle ist unbesetzt.")
                    continue

                if not person.annual_salary:
                    print(f"    WARNUNG: {person.name} hat Jahresgehalt 0.")
                    continue

                minute_cost = person.annual_salary / (1800 * 60)
                cost = minute_cost * (node.effort_minutes or 0)
                node_total += cost

                print(f"    Person: {person.name}")
                print(f"    FTE: {person.fte}")
                print(f"    Jahresgehalt 100%: CHF {person.annual_salary:,.0f}")
                print(f"    Minutenkosten: CHF {minute_cost:.4f}")
                print(f"    Aktivitätskosten: CHF {cost:.2f}")

            process_total += node_total
            print(f"  Total Aktivität: CHF {node_total:.2f}")

        print(f"\nTOTAL PROZESS: CHF {process_total:.2f}")
