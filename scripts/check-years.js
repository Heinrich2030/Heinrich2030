// Prüft, ob die Steuerwerte aktuell sind. Wird monatlich von GitHub Actions
// ausgeführt (.github/workflows/tax-monitor.yml) und öffnet bei Problemen ein Issue.
import { TAX_YEARS, KNOWN_YEARS } from "../src/data/tax-years.js";

const now = new Date();
const jahr = now.getFullYear();
const monat = now.getMonth() + 1;
const probleme = [];

if (!TAX_YEARS[jahr]) probleme.push(`Für das laufende Jahr ${jahr} fehlen die Steuerwerte.`);
if (!TAX_YEARS[jahr - 1]) probleme.push(`Für das Vorjahr ${jahr - 1} (Steuererklärung) fehlen die Steuerwerte.`);
if (monat >= 10 && !TAX_YEARS[jahr + 1]) {
  probleme.push(`Für ${jahr + 1} sind noch keine Werte hinterlegt – Gesetzgebung zum Jahreswechsel prüfen.`);
}
for (const y of KNOWN_YEARS) {
  if (y < jahr && TAX_YEARS[y].status !== "verifiziert") {
    probleme.push(`Werte für ${y} sind noch als "${TAX_YEARS[y].status}" markiert – bitte final prüfen.`);
  }
}

if (probleme.length) {
  console.log(probleme.map((p) => `- ${p}`).join("\n"));
  process.exit(1);
}
console.log(`Steuerwerte aktuell (bekannte Jahre: ${KNOWN_YEARS.join(", ")}).`);
