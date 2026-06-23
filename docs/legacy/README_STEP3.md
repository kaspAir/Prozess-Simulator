# Schritt 3: BPMN-Light Editor

Dieser Patch ergänzt:

- Node hinzufügen/bearbeiten/löschen
- Flow hinzufügen/bearbeiten/löschen
- Subprozess erstellen
- Subprozess-Node mit bestehendem Subprozess verknüpfen
- Klick auf Subprozess öffnet Subprozess
- Rücknavigation vom Subprozess in den Hauptprozess

## Installation

1. Dateien kopieren:
   - `app/templates/process_graph.html` überschreiben
   - `app/templates/node_edit.html` neu
   - `app/templates/edge_edit.html` neu
   - `app/templates/process_edit.html` neu

2. Inhalt von `style_additions_step3.css` ans Ende von `app/static/style.css` kopieren.

3. `app/app.py` gemäss `app_app_patch_instructions_step3.txt` ergänzen.

4. Flask neu starten:

```powershell
CTRL + C
python run.py
```

5. Öffnen:

```text
http://127.0.0.1:5000/process/1
```
