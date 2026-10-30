# KiCad-Projekte des Kabeltesters

Drei Platinen, erzeugt mit KiCad 7 aus einer gemeinsamen Netzliste (Python-Generator).

| Projekt | Größe | Lagen | Bauteile | Inhalt |
|---|---|---|---|---|
| [`kanalkarte/`](kanalkarte) | 118 × 74 mm | 4 | 413 | 64 Testpunkte, 8× ADG1606, 8× CD74HCT4067, Schutzbeschaltung, DIN-41612-Federleiste. Wird **zweimal** gebaut (Seite A und B). |
| [`messkarte/`](messkarte) | 120 × 90 mm | 4 | 112 | Pico 2, ADS1220, REF5025, Stromsenke, Moduswahl, USB-C, Anschlüsse für Display/Taster/LEDs |
| [`adapter_rj45/`](adapter_rj45) | 100 × 60 mm | 2 | 7 | Vorlage für Steckeradapter: 2× RJ45 + EEPROM, DIN-41612-Messerleiste |

Jedes Projekt enthält Schaltplan (`.kicad_sch`, bei der Kanalkarte mit vier Unterblättern),
Leiterplatte (`.kicad_pcb`), DRC-Bericht und im Ordner `fertigung/`:

- `*-gerber.zip` – Gerber + Bohrdaten (für JLCPCB, Aisler, Multi-CB …)
- `*-bom-jlcpcb.csv` – Stückliste, gruppiert, mit Hersteller-Nummer und (wo bekannt) LCSC-Nummer
- `*-cpl-jlcpcb.csv` – Bestückungsliste (Position, Seite, Drehung)
- `*.step.zip` – 3D-Modell der bestückten Platine

Gehäuse und Gesamtbaugruppe als STEP liegen in [`../../gehaeuse/step/`](../../gehaeuse/step).

## Stand

| Schritt | Status |
|---|---|
| Schaltpläne | fertig; KiCads eigene Netzliste stimmt mit dem Modell überein (automatisch geprüft) |
| Bauteilplatzierung | fertig; keine Überlappungen, Befestigungslöcher passen zu den Gehäusedomen |
| Masseflächen | GND (In1), 5VA (In2), GND auf Außenlagen |
| 3D-Kollisionsprüfung | Platinen, Display, Gehäuse und Boden überschneiden sich nicht |
| **Leiterbahnen** | **offen** – Kanalkarte 944, Messkarte 294, Adapter 21 Verbindungen (siehe unten) |
| Gerber | erzeugt, aber **erst nach dem Routen bestellbar** |

## Vor der Bestellung – Pflichtpunkte

1. **Leiterbahnen ziehen** (Autorouter oder von Hand), dann DRC ohne Fehler.
2. **Pinbelegungen prüfen**, die nicht aus der KiCad-Bibliothek stammen
   (Symbole in `bibliothek/kabeltester.kicad_sym`):
   - ADG1606 (TSSOP-28) – teilweise per Websuche bestätigt (VDD = 1, S16 = 4, S8 = 26, VSS = 27, D = 28),
     der Rest folgt der Pinbelegung der Familie ADG406/1206. Mit dem Datenblatt von Analog Devices abgleichen.
   - BAV199 (SOT-23: 1 = Anode D1, 2 = Kathode D2, 3 = Mitte)
   - PESD2CAN (SOT-23: 1/2 = Leitungen, 3 = gemeinsam)
   - Raspberry Pi Pico 2 (Pinbelegung wie Pico 1)
3. **DIN-41612-Ausrichtung** am ersten Muster prüfen: Messerleiste des Adapters und Federleiste der
   Kanalkarte haben Pin a1 jeweils rechts (von vorne gesehen). Ob Reihe a vorne oder hinten liegt,
   hängt vom Steckverbinder-Hersteller ab – im Zweifel die Federleiste in `layouts.py` um 180° drehen.
4. **LCSC-Nummern** ergänzen: Nur gängige Teile und der ADG1606 (C208204) sind eingetragen. Fehlende
   Nummern im JLCPCB-Teilekatalog zuordnen oder die Teile von Mouser/DigiKey selbst bestücken.
5. Die USB-C-Buchse (Footprint `GCT_USB4105`) hat laut DRC 0,19 mm zwischen Befestigungsloch und Pad
   (Regel 0,25 mm). Das steckt im Standard-Footprint und ist bei JLCPCB fertigbar.

## Leiterbahnen ziehen (Autorouter Freerouting)

In KiCad: *Plugin- und Inhaltsverwaltung* → „Freerouting“ installieren → im Leiterplatten-Editor
*Werkzeuge → Externe Plugins → Freerouting*. Danach *Flächen füllen* (Taste `B`) und *DRC*.

Oder automatisch über den Generator (Java 17+ und die Datei `freerouting-1.9.0.jar` von
github.com/freerouting/freerouting nötig):

```bash
FREEROUTING_JAR=/pfad/zu/freerouting-1.9.0.jar python3.12 generator/bauen.py --routen
```

Die Kanalkarte ist sehr dicht (413 Bauteile, 4 Lagen). Rechne mit mehreren Durchläufen und etwas
Handarbeit an den Multiplexer-Bussen.

## Neu erzeugen

Alles entsteht aus `generator/` – Änderungen dort machen, nicht in den KiCad-Dateien (sie werden
überschrieben). Voraussetzung: KiCad 7 mit Python-Modul `pcbnew` (Linux: Paket `kicad`, dazu
`kicad-symbols`, `kicad-footprints`, `kicad-packages3d`).

```bash
cd kabeltester/hardware/kicad
python3.12 generator/bauen.py              # Schaltpläne, Leiterplatten, Fertigungsdaten
python3.12 generator/bauen.py --nur-schaltplan
```

| Datei | Aufgabe |
|---|---|
| `generator/platinen.py` | Netzlisten aller Platinen (Bauteile, Werte, Footprints, Netze) |
| `generator/layouts.py` | Platzierung und Mechanik (Maße, Lochpositionen) |
| `generator/schaltplan.py` | schreibt die `.kicad_sch`-Dateien |
| `generator/leiterplatte.py` | baut die `.kicad_pcb`, Flächen, DRC, Fertigungsdaten |
| `generator/netzvergleich.py` | vergleicht KiCads Netzliste mit dem Modell |
| `generator/eigene_bibliothek.py` | eigene Symbole und den Pico-2-Footprint |

## Gehäuse als STEP

```bash
pip install cadquery
python ../../gehaeuse/gehaeuse_step.py
```

Erzeugt `gehaeuse_oberschale.step/.stl`, `gehaeuse_boden.step/.stl` und die Gesamtbaugruppe
`kabeltester_baugruppe.step.zip` (gezippt ca. 40 MB, entpackt ca. 290 MB). STEP lässt sich in
SolidWorks, Fusion 360, FreeCAD, Onshape und den meisten anderen CAD-Programmen öffnen.
