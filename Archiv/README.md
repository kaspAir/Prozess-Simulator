# Open Legal Lab MVP – Strafbefehl Prozesssimulator

3-Tier Architektur:

- Presentation Layer: HTML/CSS in `app/templates` und `app/static`
- Function Layer: Python/Flask in `app/app.py`
- Data Layer: PostgreSQL

## Installation unter Windows

Projekt nach `C:\Projekte\legal_lab_strafbefehl_mvp` entpacken.

```powershell
cd C:\Projekte\legal_lab_strafbefehl_mvp
py -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

In `.env` Benutzer, Passwort und Datenbank anpassen.

Postgres-Datenbank erstellen:

```powershell
createdb -U postgres strafbefehl_lab
```

Oder in `psql`:

```sql
CREATE DATABASE strafbefehl_lab;
```

Datenbank initialisieren und Demodaten laden:

```powershell
python init_db.py
```

App starten:

```powershell
python run.py
```

Danach öffnen:

```text
http://127.0.0.1:5000
```

## Was das MVP kann

- Prozessaktivitäten anzeigen
- Aktivitäten hinzufügen, bearbeiten und löschen
- Aufwand und Rechtsgrundlage pflegen
- Rollen, Funktionen und Personen pflegen
- Rollen Funktionen zuordnen
- Personen Rollen zuordnen
- Rollen Aktivitäten zuordnen
- Organigramm als Baum anzeigen
- Kosten pro Aktivität berechnen
- Kapazität pro Aktivität berechnen
- Flaschenhals ermitteln
- Anzahl möglicher Strafbefehle pro Jahr schätzen

## Vereinfachte Annahmen

- 1 FTE = 1'800 produktive Stunden pro Jahr
- Kostenberechnung: Jahresgehalt / 108'000 produktive Minuten
- Wenn mehrere Rollen einer Aktivität zugeordnet sind, werden die Kosten der zugeordneten Personen gemittelt.
- Die Kapazität je Aktivität ergibt sich aus den verfügbaren Personen-FTE der zugeordneten Rollen.
