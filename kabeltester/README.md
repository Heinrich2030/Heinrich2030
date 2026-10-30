# Kabeltester – Tischgerät mit 7″-Touchdisplay

Kompakter Kabel- und Kabelbaumtester mit **128 Testpunkten (erweiterbar auf 256)**,
**4-Leiter-Widerstandsmessung bis 0,1 mΩ Auflösung** und großem Touchdisplay.
Jeder Testpunkt ist gleichzeitig Ein- und Ausgang – es gibt keine feste Aufteilung.

```
        ┌───────────────────────────────────────────┐
       ╱   [ A ▭▭▭▭▭▭▭▭ ]      [ B ▭▭▭▭▭▭▭▭ ]       ╱│   ← Adapterschächte (je 64 Pins)
      ╱───────────────────────────────────────────╱ │
     ╱  ┌─────────────────────────────┐   ( ● )  ╱  │   ← Start-Taster
    ╱   │   7″ Touch  800 × 480       │   ▮ ▮   ╱   │   ← Gut/Fehler-Leuchte
   ╱    │   GUT ✔  Cat6 1:1  2,1 s    │        ╱    │
  ╱     └─────────────────────────────┘       ╱    ╱
 └────────────────────────────────────────────┘   ╱      ca. 250 × 200 × 88 mm
 └────────────────────────────────────────────┘──╱
```

## Hardware-Auswahl (Kurzfassung)

| Baugruppe | Bauteil | Warum |
|---|---|---|
| Display + Bedienung | **Waveshare ESP32-S3-Touch-LCD-7** (7″, 800×480, kapazitiv) | großes Display, WLAN, 8 MB PSRAM, günstig (ca. 45 €) |
| Messsteuerung | **Raspberry Pi Pico 2 (RP2350)** | viele GPIO, schnelles SPI + ADC, ca. 6 € |
| Präzisionsmessung | **TI ADS1220** 24 Bit + **REF5025** | mΩ-Auflösung, 50/60-Hz-Filter, Temperatursensor |
| Testpunkt-Matrix | **ADG1606** (Force, 4,5 Ω) + **CD74HCT4067** (Sense) | echte 4-Leiter-Messung an jedem Pin |
| Adapter-Schnittstelle | **DIN 41612 C, 96-polig** | robust; 64 Testpunkte + Erkennung + I²C pro Seite |

Ausführliche Begründung, Schaltungskonzept und Leistungsdaten: [docs/hardware.md](docs/hardware.md).
Stückliste mit Bestellnummern: [hardware/stueckliste.csv](hardware/stueckliste.csv).

**Kosten (Richtwert):** ca. 330 € für den Grundausbau mit 128 Pins, ca. +190 € für den
Vollausbau mit 256 Pins, ca. 5–15 € je Steckeradapter.

## Funktionen

**Prüfen**
- Automatisches Erkennen der kompletten Verdrahtung (alle Pins gegen alle) in ca. 80 ms.
- **Einlernen mit Referenzkabel** („Golden Sample“): Kabel einstecken, Namen eingeben, fertig.
- Gut/Schlecht-Prüfung mit großer grün/roter Anzeige, Ton und LED-Leuchte.
- Fehlerarten im Klartext: *Unterbrechung, Kurzschluss, Vertauscht, Fehlverdrahtung,
  Widerstand zu hoch, hochohmiger Pfad (Feuchte/Schmutz), Diode/Halbleiter*.
- **Serienprüfung**: Kabel einstecken → Prüfung startet automatisch → abziehen → nächstes.
  Zähler für Gut/Fehler und Ausbeute in %.
- Start auch per Taster am Gerät oder **Fußschalter** (beide Hände frei).
- Optionale **Isolationsprüfung** zwischen allen Netzen (5 V, bis ca. 500 MΩ).

**Messen**
- 4-Leiter-Widerstandsmessung zwischen zwei beliebigen Pins, 0,1 mΩ … 200 kΩ, automatische
  Bereichswahl.
- **Stromumkehr**: hebt Thermospannungen auf und erkennt Dioden inkl. Polarität.
- **Längenberechnung** aus dem Widerstand (Kupfer, Querschnitt in mm² oder AWG),
  temperaturkompensiert über den Temperatursensor des ADC.
- **Nullabgleich** mit Kurzschlussadapter – Restwiderstände pro Pin werden gespeichert.

**Wackeltest**
- Überwacht alle gefundenen Verbindungen mit mehreren kHz und meldet jeden Aussetzer mit
  Dauer in µs – findet Wackelkontakte und Kabelbrüche, die beim normalen Test durchrutschen.

**Daten**
- Prüfprofile und Prüfprotokoll (CSV) im internen Flash.
- WLAN-Access-Point „Kabeltester“: Protokolle herunterladen, Profile hoch-/herunterladen im Browser.
- Profile als lesbare Textdateien, z. B.:
  ```
  KABELPROFIL 1
  name=Cat6 1:1
  pins=128
  durchgang=10
  isolation=10000000
  A1-B1 0.5
  A2-B2 0.5
  ```
- **Adapter-Erkennung**: Jeder Adapter trägt ein kleines EEPROM mit seinem Namen
  (z. B. „RJ45 8P8C“), der im Display angezeigt wird.
- **Fremdspannungsschutz**: Vor jeder Messung wird jeder Pin auf Spannung geprüft.

## Projektstruktur

```
kabeltester/
├── docs/hardware.md          Schaltungskonzept, Bauteilwahl, Leistungsdaten, Schutzkonzept
├── docs/adapter.md           Steckeradapter und Kurzschlussadapter bauen
├── hardware/stueckliste.csv  Stückliste mit Bestellnummern und Richtpreisen
├── gehaeuse/gehaeuse.scad    Pultgehäuse für den 3D-Druck (OpenSCAD, parametrisch)
├── docs/zusammenbau-3d.html  Drehbares 3D-Modell des Zusammenbaus mit Explosionsansicht (im Browser öffnen)
├── firmware/common/          Analyse-Kern (Soll/Ist-Vergleich, Profile, Länge) – auf PC testbar
├── firmware/messkarte/       Pico 2: Matrix, ADS1220, Messverfahren, Textprotokoll
├── firmware/display/         ESP32-S3: LVGL-Oberfläche, Profile, Protokoll, Weboberfläche
└── tests/                    PC-Tests für den Analyse-Kern
```

## Bauen und Flashen

Beide Firmwares sind PlatformIO-Projekte.

Messkarte (Pico 2 per USB im BOOTSEL-Modus anschließen):

```bash
cd kabeltester/firmware/messkarte && pio run -t upload
```

Display-Einheit: Zuerst `lvgl_port_v8.cpp` und `lvgl_port_v8.h` aus dem Waveshare-Beispiel
„lvgl_v8_port“ (Waveshare-Wiki zum ESP32-S3-Touch-LCD-7) nach `firmware/display/src/`
kopieren. Dann:

```bash
cd kabeltester/firmware/display && pio run -t upload
```

Tests des Analyse-Kerns auf dem PC:

```bash
make -C kabeltester/tests
```

Die Messkarte lässt sich auch ohne Display über USB bedienen (Terminal, 115 200 Baud), z. B.
`SCAN`, `R A1 B1`, `INFO`. Alle Befehle stehen am Anfang von
[`firmware/messkarte/src/main.cpp`](firmware/messkarte/src/main.cpp).

## Inbetriebnahme

1. Messkarte ohne Kanalkarten flashen, `INFO` per USB prüfen (Temperatur plausibel?).
2. Kanalkarten anschließen, `SCAN` ohne Adapter → keine Verbindungen.
3. Kurzschlussadapter auf Seite A und/oder B stecken → im Setup „Nullabgleich“ (oder `KAL NULL`).
   Jede Seite mit gestecktem Kurzschlussadapter wird einzeln abgeglichen, die anderen bleiben.
4. Präzisionswiderstände (z. B. 0,1 Ω / 10 Ω / 1 kΩ / 100 kΩ, 0,1 %) messen und mit den
   Leistungsdaten in `docs/hardware.md` vergleichen.

## Stand und offene Punkte

- Konzept, Stückliste, Firmware und Gehäuse sind fertig. Schaltplan und Leiterplatten-Layout
  (KiCad) sind der nächste Schritt; `docs/hardware.md` ist dafür die Vorlage.
- Die Firmware ist gegen die Bibliotheken syntaktisch geprüft, aber noch nicht auf echter
  Hardware gelaufen. Die Leistungsdaten sind berechnete Richtwerte.
- Die eingebauten LVGL-Schriften haben keine Umlaute; die Oberfläche schreibt daher „ue/oe“.
  Mit `lv_font_conv` lässt sich eine Schrift mit Umlauten und Ω erzeugen.
