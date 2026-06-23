# Schritt 2: BPMN-Light Visualisierung

Dieser Patch ersetzt die einfache Prozess-Graphansicht durch eine BPMN-artige Ansicht:

- Start- und End-Ereignis als Kreis
- Tasks als Rechtecke
- XOR als Diamant
- Subprozess als klickbare doppelt umrandete Box
- Pfeile als SVG-Kurven
- Bedingungen an Sequenzflüssen

## Installation

1. `app/templates/process_graph.html` überschreiben.
2. Inhalt von `style_additions.css` ans Ende von `app/static/style.css` kopieren.
3. Flask neu starten:

```powershell
CTRL + C
python run.py
```

4. Öffnen:

```text
http://127.0.0.1:5000/process/1
```
