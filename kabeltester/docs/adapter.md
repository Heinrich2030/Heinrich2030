# Adapter bauen

Der Kabeltester hat zwei universelle Steckplätze (Seite A und Seite B, je 64 Testpunkte).
Für jeden Steckertyp wird eine kleine Adapterplatine gebaut. Das hält das Grundgerät kompakt
und macht es für beliebige Kabel nutzbar.

## Aufbau einer Adapterplatine

1. DIN-41612-Messerleiste (Bauform C, 96-polig, gerade) an der Unterkante.
2. Oben die Buchse(n) für das Kabel, z. B. RJ45, D-Sub, M12, USB-C, Harting, JST, Molex …
3. Jeden Buchsenkontakt mit einem Testpunkt (Reihe a/c) verbinden – **kurz und breit**, weil
   die Leiterbahn außerhalb des Kelvin-Punktes liegt (wird durch den Nullabgleich erfasst).
4. Kontakt **b32 mit GND** verbinden → das Gerät erkennt den gesteckten Adapter.
5. EEPROM 24AA02 (SOT-23-5, feste Adresse 0x50): VCC an b5, GND an b1, SDA an b7, SCL an b8,
   WP an GND. 4,7-kΩ-Pull-ups sitzen auf der Messkarte; jede Seite hat einen eigenen I²C-Bus.
   Fertige Vorlage mit 2× RJ45: [`../hardware/kicad/adapter_rj45`](../hardware/kicad/README.md).
6. Schirm-/Gehäusekontakte als eigenen Testpunkt auflegen – so wird auch der Schirm geprüft.

Mehrere Stecker auf einem Adapter sind erlaubt (z. B. RJ45 + RJ11 + USB-A auf einer Platine).

## EEPROM beschreiben

Der Adaptername steht als ASCII-Text ab Adresse 0, mit `0` abgeschlossen, maximal 32 Zeichen,
z. B. `RJ45 8P8C geschirmt`. Er erscheint im Display unter „Adapter A/B“.

Beschreiben lässt er sich mit jedem Arduino oder direkt mit der Messkarte (USB) per kleinem
Hilfssketch; ein Schreibbefehl in der Messkarten-Firmware ist als Erweiterung vorgesehen.

## Kurzschlussadapter (Nullabgleich)

Eine Adapterplatine, auf der **alle 64 Testpunkte auf eine massive Kupferfläche** gehen
(kein Stecker). Auf Seite A und/oder B stecken, im Setup „Nullabgleich“ antippen.
Das Gerät misst je Seite jeden Pin gegen den ersten Pin (A1 bzw. B1), bestimmt dessen eigenen
Anteil über eine Dreiecksmessung und speichert den Restwiderstand je Pin.

## Beispiele für Pinbelegungen

| Kabel | Seite A | Seite B | typisches Profil |
|---|---|---|---|
| Patchkabel Cat5e/6 (T568B ↔ T568B) | A1–A8 + Schirm A9 | B1–B8 + Schirm B9 | 1:1, 9 Verbindungen |
| Crossover (T568A ↔ T568B) | A1–A8 | B1–B8 | 1↔3, 2↔6 vertauscht – einlernen! |
| D-Sub 25 (seriell/parallel) | A1–A25 | B1–B25 | 1:1 oder gemäß Datenblatt |
| Kabelbaum mit Verteiler | mehrere Stecker auf A | mehrere Stecker auf B | Netze mit > 2 Pins |
