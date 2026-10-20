# Steuer-Rechner – Regeln für KI-Updates

Web-App ohne Build-Schritt (Vanilla JS, ES-Module). Tests: `npm test`. Lokal starten: `npm start`.

## Aufbau
- `src/engine/tax.js` – jahresunabhängige Rechenlogik. **Keine Jahreszahlen oder Beträge hart codieren.**
- `src/data/tax-years.js` – alle jahresabhängigen Werte (Tarif § 32a EStG, Soli-Freigrenze,
  Kinderfreibetrag, Kindergeld, Pauschbeträge, Entfernungspauschale).
- `tests/engine.test.js` – prüft u. a. Stetigkeit des Tarifs an allen Zonengrenzen für jedes Jahr.
- `scripts/check-years.js` – meldet fehlende/vorläufige Jahre.

## Steuerwerte aktualisieren
1. Nur offizielle Quellen: Bundesgesetzblatt (recht.bund.de), gesetze-im-internet.de, BMF
   (bundesfinanzministerium.de, inkl. Programmablaufplan Lohnsteuer), Bundestag-Drucksachen.
   Keine Blogs/Ratgeber als alleinige Quelle.
2. Neues Jahr als eigenen Eintrag in `TAX_YEARS` anlegen, Quellen in `quellen` eintragen.
3. `status: "vorläufig"`, solange das Gesetz nicht im Bundesgesetzblatt verkündet ist,
   sonst `"verifiziert"`.
4. Die Tarifformel muss stetig sein – `npm test` muss grün sein.
5. Änderungen nie direkt auf `main`, sondern als Pull Request mit Quellenangaben.
6. Ändert sich die *Struktur* des Steuerrechts (neue Tarifzone, neues Verfahren), Engine
   anpassen und Tests ergänzen – im PR klar beschreiben.
