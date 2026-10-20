# KI-Überwachung der Steuerwerte

Damit die App jahresunabhängig aktuell bleibt, gibt es zwei Ebenen:

1. **GitHub Action `Steuerwerte-Überwachung`** (monatlich, `.github/workflows/tax-monitor.yml`)
   – prüft mit `scripts/check-years.js`, ob Werte für Vorjahr, laufendes Jahr und (ab Oktober)
   das Folgejahr vorhanden und verifiziert sind. Bei Problemen öffnet sie das Issue
   „Steuerwerte aktualisieren“.

2. **Geplante Claude-Aufgabe** (monatlich, in Claude Code eingerichtet)
   – recherchiert in offiziellen Quellen nach Änderungen (Grundfreibetrag, Tarif,
   Soli-Freigrenze, Kindergeld/Kinderfreibetrag, Pauschbeträge, Entfernungspauschale),
   trägt sie in `src/data/tax-years.js` ein, lässt `npm test` laufen und öffnet einen
   Pull Request mit Quellenangaben. Ohne Änderungen passiert nichts.

Pull Requests der KI immer kurz prüfen, bevor sie gemergt werden – die App ersetzt
keine Steuerberatung.
