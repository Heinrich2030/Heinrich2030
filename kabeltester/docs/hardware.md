# Hardware – Schaltungskonzept

Dieses Dokument beschreibt die Schaltung so weit, dass daraus ein Schaltplan in KiCad
gezeichnet werden kann. Bauteile und Preise: [`../hardware/stueckliste.csv`](../hardware/stueckliste.csv).

## 1. Blockschaltbild

```
                    ┌──────────────────────────────────────────────┐
  USB-C 5 V/3 A ───►│ Messkarte                                    │
                    │                                              │      Flachband
                    │  Pico 2 (RP2350) ──SPI──► 74HC595-Kette ─────┼──────────────┐
                    │      │  │                                    │              │
                    │      │  └─SPI──► ADS1220 (24 Bit) ◄── S+/S-  │              ▼
  ESP32-S3 7" ◄─UART┤      │                                       │   ┌─────────────────────┐
  (Display-Einheit) │      ├─ADC0 ◄── Scan-Puffer ◄── S-           │   │ Kanalkarte A (64)   │──► DIN 41612 Seite A
                    │      ├─I²C ──► PCA9511A ──► Adapter-EEPROMs  │   │ 8× ADG1606 (Force)  │
                    │      └─GPIO ─► Summer, LEDs, Start-Taster    │   │ 8× HCT4067 (Sense)  │
                    │                                              │   └─────────────────────┘
                    │  Frontend:                                   │   ┌─────────────────────┐
                    │   REF5025 → Puffer → HI-Force   (2,500 V)     │   │ Kanalkarte B (64)   │──► DIN 41612 Seite B
                    │   Stromsenke 10 mA…10 µA ← LO-Force           │   └─────────────────────┘
                    │   Scan: 1 kΩ→3,3 V / 10 kΩ→GND                │   (optional C, D: 256 Pins)
                    │   ISO:  1 MΩ→AVDD, LO→GND                     │
                    └──────────────────────────────────────────────┘
        4 Analogbusse quer über alle Kanalkarten:  HI-Force · HI-Sense · LO-Force · LO-Sense
```

**Arbeitsteilung:** Die Messkarte macht ausschließlich Messtechnik in Echtzeit. Die
Display-Einheit macht Bedienung, Auswertung, Speicher und WLAN. Beide reden über ein
einfaches Textprotokoll (UART, 921 600 Baud), das auch per USB am PC funktioniert.

## 2. Warum diese Bauteile?

| Aufgabe | Wahl | Begründung | verworfen |
|---|---|---|---|
| Display + Bedienrechner | **Waveshare ESP32-S3-Touch-LCD-7** | 7″, 800×480, kapazitiver Touch, 8 MB PSRAM, WLAN, fertig verschraubbar, ca. 45 € | Raspberry Pi + HDMI-Display (Boot-Zeit, SD-Karten-Korruption, Stromaufnahme); Nextion (geschlossen, teuer) |
| Mess-Controller | **Raspberry Pi Pico 2 (RP2350)** | 26 GPIO, schnelles SPI, 500-kS/s-ADC für den Schnellscan, PIO, sehr günstig, gut lötbar | ESP32-S3 allein: am 7″-Board fast alle GPIO durch das RGB-Display belegt |
| Präzisions-ADC | **TI ADS1220** | 24 Bit, PGA bis 128, 50/60-Hz-Filter, interner Temperatursensor, ratiometrisch | ADS1115 (16 Bit, kein mΩ-Bereich) |
| Force-Multiplexer | **ADI ADG1606** | 16:1, nur 4,5 Ω Ron, geringer Leckstrom → 10 mA Messstrom möglich | CD74HC4067 (70 Ω Ron, zu viel Spannungsabfall bei 10 mA) |
| Sense-Multiplexer | **TI CD74HCT4067** | Ron spielt bei 4-Leiter-Messung keine Rolle, TTL-Pegel passen zu 3,3 V, < 1 € | ADG1606 auch hier (doppelte Kosten ohne Nutzen) |
| Referenz | **REF5025** | 0,05 %, 3 ppm/K, rauscharm | – |
| Adapter-Stecker | **DIN 41612 Bauform C, 96-polig** | robust, 64 Testpunkte (Reihe a+c) + 32 Hilfskontakte (Reihe b) für GND/3,3 V/I²C/Erkennung, günstig, steckzyklenfest | IDC-Wannenstecker (nicht robust genug), Nullkraftsockel (teuer) |

**Kanalzahl:** Grundausbau 128 Testpunkte (2 × 64), Vollausbau **256** (4 Kanalkarten).
Mehr ist mit dieser Architektur möglich, aber Buskapazität und Leckströme steigen; 256 ist der
sinnvolle Kompromiss für ein kompaktes Tischgerät.

## 3. Kanalkarte – ein Testpunkt

Jeder Testpunkt hängt an vier Multiplexern. Force und Sense werden **erst direkt am
Steckerpin** zusammengeführt (Kelvin-Punkt K). Dadurch fallen Ron der Multiplexer,
Schutzbauteile und Leiterbahnen aus der Messung heraus.

```
                         ┌── 33 Ω ── PTC ──┬── ADG1606 (HI-Force, Kanal n)
 Steckerpin ──┬── K ─────┤                 ├── ADG1606 (LO-Force, Kanal n)
              │          │               BAV199 → 0 V / 5 V
          PESD2CAN       │
           (ESD)         └── 1 kΩ ───────┬── CD74HCT4067 (HI-Sense, Kanal n)
                                         ├── CD74HCT4067 (LO-Sense, Kanal n)
                                       BAV199 → 0 V / 5 V
```

- 64 Testpunkte = 4 Blöcke à 16. Pro Block: 1× ADG1606 HI-Force, 1× ADG1606 LO-Force,
  1× HCT4067 HI-Sense, 1× HCT4067 LO-Sense → **16 Multiplexer pro Kanalkarte**.
- Adressleitungen: HI-Adresse (4 Bit) gemeinsam für alle HI-Multiplexer, LO-Adresse (4 Bit)
  für alle LO-Multiplexer – kommen von der Messkarte.
- Enables: 2× 74HC595 pro Karte (Byte 1: Force-EN, aktiv high; Byte 2: Sense-/E, aktiv low).
  **Pull-downs an Force-EN, Pull-ups an Sense-/E**, damit beim Einschalten alles offen ist.
- Versorgung der Multiplexer: 5,0 V (AVDD). Logik der 595 auf 3,3 V; ADG1606 und HCT4067
  erkennen 3,3 V sicher als High.
- Masse: durchgehende Massefläche, Analogbusse als Leiterbahnpaar (Force/Sense nebeneinander).

## 4. Messkarte – Frontend

Moduswahl über Byte 1 der Schieberegisterkette (siehe `firmware/messkarte/src/hardware.h`):

| Bit | Name | Schaltung |
|---|---|---|
| 0 | `HI_QUELLE` | HI-Force ← 2,500 V (REF5025 → OPA2388 als Puffer, liefert ≥ 15 mA) |
| 1 | `LO_SENKE` | LO-Force → Drain DMN3404L; Source → Shunt → GND; OPA2388 regelt U_Shunt auf 100 mV |
| 2–3 | Shunt | 2× ADG1408 (getrennter Force- und Sense-Pfad) wählen 10 Ω / 100 Ω / 1 kΩ / 10 kΩ (0,1 %) → 10 mA / 1 mA / 100 µA / 10 µA |
| 4 | `SCAN_PU` | HI-Force ← 3,3 V über 1 kΩ |
| 5 | `SCAN_PD` | LO-Force → GND über 10 kΩ |
| 6 | `ISO` | HI-Force ← AVDD über 1 MΩ (0,1 %) |
| 7 | `LO_GND` | LO-Force → GND (TMUX1101) |

**ADS1220-Beschaltung**

| Eingang | Signal |
|---|---|
| AIN0 | HI-Sense (über 100 Ω + 10 nF Filter) |
| AIN1 | LO-Sense (über 100 Ω + 10 nF Filter) |
| AIN2 | Shunt-Spannung (oberes Ende, unteres an AGND) |
| AIN3 | 2,5-V-Quelle über Teiler 1:2 (Selbsttest) |
| REFP/REFN | nicht genutzt: intern 2,048 V bzw. AVDD (Isolationsmessung) |

**Scan-Puffer:** LO-Sense → OPA2388 (Spannungsfolger, pA-Eingangsstrom) → Teiler 10 k/10 k →
GP26 (ADC0). Der hochohmige Puffer belastet den Sense-Pfad nicht.

## 5. Messverfahren

1. **Fremdspannungsprüfung** – jeder Pin wird gegen GND (10 kΩ) gemessen, > 0,3 V → Abbruch.
2. **Schnellscan** – alle Pinpaare (128 Pins: 8 128 Paare) mit 1 kΩ/10 kΩ und dem
   RP2350-ADC; Paare innerhalb schon bekannter Netze werden übersprungen. Dauer ca. 80 ms.
   Erkennt Verbindungen bis ca. 7 kΩ.
3. **4-Leiter-Widerstand** – für jedes Netz ein Spannbaum (jeder Pin gegen den kleinsten Pin
   des Netzes). Messung in beiden Stromrichtungen:
   - R = U_Sense / (U_Shunt / R_Shunt) – ratiometrisch, Referenzfehler kürzt sich heraus.
   - Mittelwert beider Richtungen hebt Thermospannungen auf.
   - Starker Unterschied → **Diode/Halbleiter** (z. B. LED-beleuchtete Stecker, Freilaufdioden).
   - Automatische Bereichs- und Verstärkungswahl (PGA 1 … 128).
4. **Isolation (optional)** – zwischen allen Netzen mit 5 V über 1 MΩ. Ratiometrisch zu AVDD:
   R = 1 MΩ · x / (1 − x), x = U / AVDD.
5. **Wackeltest** – nur die gefundenen Verbindungen werden im Kreis überwacht (mehrere kHz);
   jede Unterbrechung wird mit Dauer in µs gemeldet.

### Erwartete Leistungsdaten (Richtwerte, vor Kalibrierung am Prototyp zu bestätigen)

| Größe | Bereich | Auflösung | Genauigkeit (nach Nullabgleich) |
|---|---|---|---|
| Widerstand 10 mA | 0 … 120 Ω | 0,1 mΩ | ± (0,1 % + 2 mΩ) |
| Widerstand 1 mA | … 2 kΩ | 1 mΩ | ± (0,1 % + 20 mΩ) |
| Widerstand 100 µA | … 20 kΩ | 10 mΩ | ± 0,2 % |
| Widerstand 10 µA | … 200 kΩ | 0,1 Ω | ± 0,5 % |
| Isolation 5 V | 100 kΩ … ca. 500 MΩ | – | ± 5 % bis 100 MΩ |
| Durchgang/Scan | 128 Pins | – | ca. 80 ms |

Grenzen: Die Genauigkeit hängt von den 0,1-%-Shunts und vom Nullabgleich ab. Der
Übergangswiderstand Adapter ↔ Prüfling liegt außerhalb des Kelvin-Punktes und wird durch den
Nullabgleich mit dem Kurzschlussadapter erfasst, nicht aber Abnutzung der Kontakte danach.

## 6. Schutzkonzept

- ESD: PESD2CAN direkt am Stecker.
- Fremdspannung: 33 Ω + PTC im Force-Pfad, 1 kΩ im Sense-Pfad, BAV199 klemmen auf 0 V/5 V.
  Auslegung für **kurzzeitig bis ca. 12 V**. Das Gerät ist **nicht** für Kabel an
  spannungsführenden Anlagen gedacht – die Fremdspannungsprüfung vor jeder Messung bricht ab,
  bevor Messstrom fließt.
- Prüfspannung maximal 5 V, Prüfstrom maximal 10 mA → berührungssicher.
- Eine echte Hochspannungs-Isolationsprüfung (500 V/1 kV) ist bewusst **nicht** eingebaut
  (Sicherheit, Zulassung). Dafür ein separates Isolationsmessgerät verwenden.

## 7. Steckverbinder der Adapter (DIN 41612 C, 96-polig)

| Reihe | Kontakte | Belegung |
|---|---|---|
| a | 1–32 | Testpunkte 1–32 |
| c | 1–32 | Testpunkte 33–64 |
| b | 1–4 | GND |
| b | 5–6 | +3,3 V (max. 50 mA, für Adapter-EEPROM/LEDs) |
| b | 7 | SDA (je Seite eigener I²C-Bus, EEPROM-Adresse immer 0x50) |
| b | 8 | SCL |
| b | 9–10 | GND |
| b | 11–31 | frei (z. B. Adapter-LEDs, Schirmung) |
| b | 32 | Adapter-Erkennung (auf dem Adapter mit GND verbunden) |

Adapter bauen: [`adapter.md`](adapter.md).

## 8. Stromversorgung

- USB-C an der linken Gehäusewand, 5 V/3 A (keine PD-Aushandlung nötig, 5,1-kΩ-CC-Widerstände),
  Polyfuse 2 A, TVS-Diode SMAJ5.0CA.
- AVDD (Analogteil): die 5 V über Ferrit + 22 µF gefiltert. Ein LDO hätte aus 5 V USB keine
  Spannungsreserve. Die Genauigkeit hängt nicht an AVDD: Widerstandsmessung ist ratiometrisch zum
  Shunt, die Isolationsmessung ratiometrisch zu AVDD selbst.
- 3,3 V für die Logik vom Pico-2-Regler (Pico über Schottky-Diode aus 5 V, sein eigener USB bleibt
  für Firmware-Updates nutzbar – zweite Öffnung in der linken Wand).
- Display-Einheit: ca. 400–600 mA. Sie wird aus der Messkarte versorgt (JST-PH-Stecker „Display 5V“
  → kurzes Kabel auf USB-C-Stecker am Display).

## 9. Flachbandkabel Messkarte ↔ Kanalkarte (34-polig, IDC)

| Pin | Signal | Pin | Signal |
|---|---|---|---|
| 1 | GND | 2 | HI_F (HI-Force-Bus) |
| 3 | GND | 4 | HI_S (HI-Sense-Bus) |
| 5 | GND | 6 | LO_F |
| 7 | GND | 8 | LO_S |
| 9 | GND | 10 | 5VA |
| 11 | 5VA | 12 | 3V3 |
| 13 | 3V3 | 14 | GND |
| 15–18 | HA0–HA3 (HI-Adresse) | 19–22 | LA0–LA3 (LO-Adresse) |
| 23 | GND | 24 | SR_CLK |
| 25 | SR_LATCH | 26 | SR_OE_N |
| 27 | Schieberegister-Eingang | 28 | Schieberegister-Ausgang (weiter zur nächsten Karte) |
| 29 | GND | 30 | SDA (eigener Bus je Karte) |
| 31 | SCL | 32 | ADAPT_N (Adapter steckt) |
| 33 | GND | 34 | GND |

Die Analogbusse liegen zwischen Masseadern. Beide Kanalkarten sind identisch, die Kette der
Schieberegister läuft Messkarte → Karte A → Karte B.

## 10. KiCad-Projekte

Schaltpläne, Leiterplatten und Fertigungsdaten: [`../hardware/kicad/`](../hardware/kicad/README.md).
