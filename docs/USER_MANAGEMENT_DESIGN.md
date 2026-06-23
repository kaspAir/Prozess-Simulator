# Entwurf: Benutzerverwaltung & Berechtigungen (Multi-Tenant RBAC)

> Status: **Design** (noch keine Implementierung). Referenz für die spätere Umsetzung.

## Ziel

Mehrere Kunden-Organisationen („Accounts/Mandanten") nutzen den Prozess-Simulator
getrennt voneinander. Pro Account ≥1 Account-Admin. Innerhalb eines Accounts können
mehrere modellierte Organisationen verwaltet werden. Benutzer erhalten **frei
definierbare Rollen**, optional **pro Organisation** verschieden. Der Plattform-Betreiber
(Super-Admin) hat Übersicht über alle Accounts.

## Grundprinzip: Auth-Schicht ≠ Simulations-Daten

Die bestehenden Entitäten `Organization`, `Role`, `Person` sind **Simulations-Daten**
(modellierte Organisation, fachliche Stellen-Rolle, Mitarbeiter/in mit Gehalt/FTE) –
**keine** Login-Benutzer. Die Benutzerverwaltung ist eine **separate Schicht** darüber.
Ein Login-`User` ist nicht dieselbe Entität wie eine modellierte `Person`.

## Hierarchie (4 Ebenen)

```
PLATTFORM         Super-Admin (Betreiber) – sieht/verwaltet ALLE Accounts
   │
ACCOUNT (Mandant) z.B. Beratungsfirma / Kanton – hat ≥1 Account-Admin,
   │                   enthält mehrere Organisationen
ORGANISATION      modellierte Organisation (Organigramm, Personen, Prozesse)
   │
DATEN             OrgUnit, Person, Process, Node, Edge … (scoped per Organisation)
```

## Admin-Ebenen

| Ebene | Wer | Verantwortung |
|---|---|---|
| **Super-Admin** | Plattform-Betreiber | Übersicht/Zugriff über alle Accounts; `is_super_admin`-Flag |
| **Account-Admin** | je Account ≥1 | Mitglieder, Rollen, Organisationen des Accounts verwalten |
| **Organisations-Admin** | optional, pro Organisation | volle Rechte innerhalb genau einer Organisation |
| **Editoren / Viewer** | beliebig | abgegrenzte Rechte, account- oder organisationsweit |

## Datenmodell

```
User(id, name, email, is_super_admin)
AuthIdentity(id, user_id, provider, provider_uid, password_hash?)
        provider = local | google | microsoft   (mehrere pro User möglich → "beides")

Account(id, name)                                  # Mandant
Organisation(id, account_id, name, …)              # = bestehende Organization + account_id
Membership(id, user_id, account_id)                # User ↔ Account (n:m)

Role(id, account_id, name)                         # frei definierbar, pro Account
RolePermission(role_id, permission_key)            # Rechte-Bündel
RoleAssignment(id, membership_id, role_id, organisation_id NULL)
        organisation_id = NULL  → Rolle gilt accountweit (alle Organisationen)
        organisation_id gesetzt → Rolle gilt nur für diese Organisation

Invitation(id, account_id, email, role_id, organisation_id NULL, token, status, expires_at)
```

**Tenant-Scope:** jede bestehende Tabelle erhält `organisation_id`; jede Abfrage filtert
nach der aktiven Organisation. (Account-Zugehörigkeit ergibt sich aus der Organisation.)

## Berechtigungs-Katalog (Permission-Keys)

Bausteine, aus denen Rollen zusammengestellt werden:

| Bereich | Keys |
|---|---|
| Account | `account.manage`, `account.members.manage`, `account.roles.manage` |
| Organisationen | `org.create`, `org.manage` |
| Inhalte | `orgchart.manage`, `persons.manage`, `processes.manage`, `simulation.run` |
| Lesen | `dashboard.view` (+ optionale `*.view`-Varianten) |

## Vorlagen-Rollen (zum Klonen/Anpassen)

| Permission-Key | Account-Admin | Org-Admin | Organigramm-Ed. | Mitarbeitende-Ed. | Prozess-Ed. | Viewer |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| account.manage | ✅ | – | – | – | – | – |
| account.members.manage | ✅ | – | – | – | – | – |
| account.roles.manage | ✅ | – | – | – | – | – |
| org.create | ✅ | – | – | – | – | – |
| org.manage | ✅ | ✅ | – | – | – | – |
| orgchart.manage | ✅ | ✅ | ✅ | – | – | – |
| persons.manage | ✅ | ✅ | – | ✅ | – | – |
| processes.manage | ✅ | ✅ | – | – | ✅ | – |
| simulation.run | ✅ | ✅ | – | – | ✅ | – |
| dashboard.view | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

- **Account-Admin** wird accountweit zugewiesen (`organisation_id = NULL`).
- **Org-Admin / Editoren / Viewer** typischerweise pro Organisation (`organisation_id` gesetzt),
  können aber auch accountweit vergeben werden.
- Mehrere Rollen pro Mitglied erlaubt; Berechtigungen summieren sich.

## Regeln

- **≥1 Account-Admin:** Pro Account muss immer mindestens ein Mitglied accountweit
  `account.members.manage` besitzen. Der letzte solche Admin kann nicht entfernt/herabgestuft werden.
- **Tenant-Isolation:** Daten einer Organisation sind nur für Mitglieder mit passender Rolle
  in diesem Account/dieser Organisation sichtbar.
- **Super-Admin** kann in einen Account „hineinschauen" (Übersicht; optional Impersonation mit Audit-Eintrag).

## Authentifizierung

- **Lokal:** E-Mail + Passwort (`AuthIdentity.provider = local`, `password_hash`).
- **SSO:** Google / Microsoft (OAuth, `provider_uid`).
- Pro User können mehrere Identities existieren (lokal **und** SSO).
- **Einladungen:** Account-Admin lädt per E-Mail ein (`Invitation` + Token-Link); beim Annehmen
  wird User + Membership + initiale RoleAssignment erstellt.

## Umsetzung in Phasen (Vorschlag)

| Phase | Inhalt |
|---|---|
| **1 – Fundament** | User + lokales Login, Account, Organisation(account_id), Membership, `organisation_id`-Scope überall, Super-Admin-Übersicht, Account-Admin-Rolle, ≥1-Admin-Regel |
| **2 – Rollen & Scope** | Frei definierbare Rollen + Permission-Katalog + **RoleAssignment pro Organisation**, Vorlagen-Rollen, Einladungen, Routen-/UI-Schutz |
| **3 – Komfort** | SSO (Google/Microsoft), Account-/Organisations-Wechsler-UI, Audit-Log |

> Pro-Organisation-Zuweisung ist bewusst bereits in Phase 2 (Kern), nicht „später".

## Offene Punkte für die Detailplanung

- Konkrete UI-Flows (Einladung, Rollen-Editor, Org-Wechsler).
- Routen-/Endpoint-Schutz (Decorator/Middleware, der Permission-Keys prüft).
- Migration: bestehende Daten einem initialen Account + Organisation zuordnen.
- Passwort-Reset, E-Mail-Versand (welcher Dienst).
