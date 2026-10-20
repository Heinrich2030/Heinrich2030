import { test } from "node:test";
import assert from "node:assert/strict";
import { analysiere } from "../src/engine/tipps.js";
import { TAX_YEARS } from "../src/data/tax-years.js";

const p = TAX_YEARS[2025];
const ids = (r) => r.tipps.map((t) => t.id);

test("Grenzsteuersatz liegt im plausiblen Bereich", () => {
  const r = analysiere({ veranlagung: "einzel", personen: [{ brutto: 60000 }] }, p);
  assert.ok(r.grenzsteuersatz > 0.3 && r.grenzsteuersatz < 0.45, String(r.grenzsteuersatz));
});

test("Homeoffice-Tipp mit Ersparnis, wenn keine Tage eingetragen", () => {
  const r = analysiere({ veranlagung: "einzel", personen: [{ brutto: 60000, entfernungKm: 25, arbeitstage: 200 }] }, p);
  const t = r.tipps.find((x) => x.id === "homeoffice-0");
  assert.ok(t && t.ersparnis > 0);
});

test("Tipps sind nach Ersparnis sortiert", () => {
  const r = analysiere({ veranlagung: "einzel", personen: [{ brutto: 60000, entfernungKm: 25, arbeitstage: 200 }] }, p);
  const werte = r.tipps.map((t) => t.ersparnis ?? -1);
  assert.deepEqual(werte, [...werte].sort((a, b) => b - a));
});

test("Splitting-Vorteil bei ungleichen Einkommen", () => {
  const r = analysiere({ veranlagung: "zusammen", personen: [{ brutto: 80000 }, { brutto: 10000 }] }, p);
  const t = r.tipps.find((x) => x.id === "splitting");
  assert.ok(t && t.ersparnis > 1000, JSON.stringify(t));
});

test("Freistellungsauftrag-Tipp bei Steuer unter dem Sparerpauschbetrag", () => {
  const r = analysiere({ veranlagung: "einzel", personen: [{ brutto: 30000 }], kap: { ertraege: 500, kapEStEinbehalten: 125 } }, p);
  assert.ok(ids(r).includes("freistellungsauftrag"));
});

test("Günstigerprüfung bei niedrigem Einkommen", () => {
  const r = analysiere({ veranlagung: "einzel", personen: [{ brutto: 14000 }], kap: { ertraege: 5000 } }, p);
  const t = r.tipps.find((x) => x.id === "guenstigerpruefung");
  assert.ok(t && t.ersparnis > 0);
});

test("Kein Einkommen: keine Fehler, keine Steuertipps mit Betrag", () => {
  const r = analysiere({ veranlagung: "einzel", personen: [{}] }, p);
  assert.ok(r.tipps.every((t) => !t.ersparnis));
});
