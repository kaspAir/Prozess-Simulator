# Schritt 1: BPMN-Light Graphmodell

Kopiere die Dateien in Dein bestehendes Projekt und überschreibe:

- app/models.py
- init_db.py
- app/templates/process_graph.html neu hinzufügen

Dann app/app.py gemäss `app_app_patch_instructions.txt` anpassen.

Wichtig: `python init_db.py` löscht die bestehenden Tabellen und erzeugt Demo-Daten neu.

Start:

```powershell
python init_db.py
python run.py
```

Graph öffnen:

```text
http://127.0.0.1:5000/process/1
```
