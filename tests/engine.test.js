import { test } from "node:test";
import assert from "node:assert/strict";
import { grundtarif, tarifSteuer, soli, berechne, werbungskosten } from "../src/engine/tax.js";
import { TAX_YEARS, KNOWN_YEARS, getYearParams } from "../src/data/tax-years.js";

// Der Tarif muss an jeder Zonengrenze stetig sein. Das fängt Tippfehler
// in neu eingetragenen Jahresparametern zuverlässig ab.
for (const year of KNOWN_YEARS) {
  const t = TAX_YEARS[year].tarif;
  test(`${year}: Tarif ist an allen Zonengrenzen stetig`, () => {
    for (const grenze of [t.grundfreibetrag, t.zone2.bis, t.zone3.bis, t.zone4.bis]) {
      const diff = grundtarif(grenze + 1, t) - grundtarif(grenze, t);
      assert.ok(diff >= 0 && diff <= 1, `Sprung an ${grenze}: ${diff}`);
    }
  });

  test(`${year}: Tarif ist monoton und Grundfreibetrag steuerfrei`, () => {
    assert.equal(grundtarif(t.grundfreibetrag, t), 0);
    let prev = 0;
    for (let x = 0; x <= 400000; x += 997) {
      const st = grundtarif(x, t);
      assert.ok(st >= prev, `nicht monoton bei ${x}`);
      prev = st;
    }
  });

  test(`${year}: Pflichtfelder vorhanden`, () => {
    const p = TAX_YEARS[year];
    for (const key of ["tarif", "soli", "kinder", "entfernungspauschale", "status", "quellen"]) {
      assert.ok(p[key] !== undefined, `${key} fehlt`);
    }
  });
}

test("2025: bekannte Tarifwerte", () => {
  const t = TAX_YEARS[2025].tarif;
  assert.equal(grundtarif(12096, t), 0);
  assert.equal(grundtarif(50000, t), 10691);
  assert.equal(grundtarif(100000, t), 31088);
  assert.equal(grundtarif(300000, t), 115753);
});

test("Splitting: doppelte Steuer auf halbes Einkommen", () => {
  const t = TAX_YEARS[2025].tarif;
  assert.equal(tarifSteuer(100000, t, true), 2 * grundtarif(50000, t));
});

test("Soli: Freigrenze und Milderungszone", () => {
  const p = TAX_YEARS[2025];
  assert.equal(soli(19950, p, false), 0);
  assert.equal(soli(20000, p, false), 5.95); // 11,9 % von 50 €
  assert.equal(soli(100000, p, false), 5500);
  assert.equal(soli(39900, p, true), 0);
});

test("Werbungskosten: Pauschbetrag greift, wenn höher", () => {
  const p = TAX_YEARS[2025];
  assert.equal(werbungskosten({ brutto: 40000 }, p).abzug, 1230);
  const wk = werbungskosten({ brutto: 40000, entfernungKm: 30, arbeitstage: 220 }, p);
  assert.equal(wk.fahrt, 220 * (20 * 0.3 + 10 * 0.38));
  assert.equal(wk.abzug, wk.fahrt);
});

test("Gesamtberechnung: Lediger mit 50.000 € brutto", () => {
  const p = TAX_YEARS[2025];
  const r = berechne(
    { veranlagung: "einzel", personen: [{ brutto: 50000, lohnsteuer: 8000 }] },
    p,
  );
  assert.equal(r.summeEinkuenfte, 48770);
  assert.equal(r.zvE, 48734);
  assert.equal(r.est, grundtarif(48734, p.tarif));
  assert.equal(r.ergebnis, 8000 - r.festgesetzt);
});

test("Kinder: Kindergeld günstiger bei kleinem Einkommen", () => {
  const p = TAX_YEARS[2025];
  const r = berechne({ veranlagung: "zusammen", kinder: 1, personen: [{ brutto: 40000 }, {}] }, p);
  assert.equal(r.kinder.freibetragGuenstiger, false);
});

test("Kinder: Freibetrag günstiger bei hohem Einkommen", () => {
  const p = TAX_YEARS[2025];
  const r = berechne({ veranlagung: "zusammen", kinder: 1, personen: [{ brutto: 200000 }, {}] }, p);
  assert.equal(r.kinder.freibetragGuenstiger, true);
});

test("Kapitalerträge: Sparerpauschbetrag und Abgeltungsteuer", () => {
  const p = TAX_YEARS[2025];
  const r = berechne({ veranlagung: "einzel", personen: [{}], kap: { ertraege: 2000 } }, p);
  assert.equal(r.kap.kapESt, 250);
  assert.equal(r.kap.soli, 13.75);
});

test("Unbekanntes Jahr fällt auf neuestes bekanntes Jahr zurück", () => {
  const latest = KNOWN_YEARS[KNOWN_YEARS.length - 1];
  const r = getYearParams(latest + 5);
  assert.equal(r.fallback, true);
  assert.equal(r.year, latest);
});
