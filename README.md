# Steuer-Rechner

Eigene Web-App zur Schätzung der Einkommensteuer in Deutschland – jahresunabhängig,
läuft komplett im Browser (keine Datenübertragung), mit KI-gestützter Aktualisierung
der Steuerwerte.

## Funktionen
- Einkommensteuer nach § 32a EStG, Grund- und Splittingtarif
- Solidaritätszuschlag (Freigrenze, Milderungszone), Kirchensteuer 8 %/9 %
- Anlage N für 1–2 Personen: Entfernungspauschale, Homeoffice, Arbeitsmittel,
  Arbeitnehmer-Pauschbetrag, Renten- und Basis-Kranken-/Pflegeversicherung
- Kinder: Günstigerprüfung Kindergeld/Kinderfreibetrag, Entlastungsbetrag Alleinerziehende
- Spenden, haushaltsnahe Dienstleistungen und Handwerkerleistungen (§ 35a)
- Anlage KAP: Abgeltungsteuer mit Sparerpauschbetrag
- Erstattung/Nachzahlung im Vergleich zu einbehaltenen Steuern
- Steuerwerte für 2023–2026 (2026 vorläufig); unbekannte Jahre nutzen das neueste Jahr mit Warnhinweis

## Starten
```bash
npm start      # http://localhost:8080
npm test
```
Ohne Build-Schritt – die Dateien können auch direkt auf GitHub Pages oder jedem Webspace liegen.

## Jahresunabhängigkeit & KI-Überwachung
Alle Jahreswerte stehen in `src/data/tax-years.js`, die Rechenlogik in `src/engine/tax.js`
ist jahresneutral. Wie neue Jahre automatisch nachgetragen werden: [docs/KI-UEBERWACHUNG.md](docs/KI-UEBERWACHUNG.md).

## Noch nicht enthalten
Außergewöhnliche Belastungen, Selbständigkeit/Gewerbe, Vermietung, Höchstbeträge der
Vorsorgeaufwendungen, Progressionsvorbehalt, ELSTER-Übermittlung (ERiC).

> Schätzung ohne Gewähr – keine Steuerberatung.

## Spartipps
Die App analysiert deine Eingaben und zeigt Spartipps, sortiert nach Ersparnis in Euro.
Jeder Betrag ist eine echte Vergleichsrechnung mit der Engine („Was wäre, wenn …“), z. B.
Homeoffice-Tage, Handwerkerkosten, Basisrente, Spenden, Splitting-Vorteil, Günstigerprüfung
und Freistellungsauftrag bei Kapitalerträgen. Logik: `src/engine/tipps.js`.
