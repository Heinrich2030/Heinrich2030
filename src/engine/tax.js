// Jahresunabhängige Rechen-Engine für die Einkommensteuer.
// Alle Werte kommen aus den Jahresparametern (src/data/tax-years.js).

const floor = Math.floor;
const cents = (v) => Math.floor(v * 100 + 1e-9) / 100;
const num = (v) => (Number.isFinite(Number(v)) ? Number(v) : 0);
const pos = (v) => Math.max(0, num(v));

/** Einkommensteuer-Grundtarif nach § 32a Abs. 1 EStG (volle Euro). */
export function grundtarif(zvE, tarif) {
  const x = floor(pos(zvE));
  const { grundfreibetrag, zone2, zone3, zone4, zone5 } = tarif;
  let st;
  if (x <= grundfreibetrag) st = 0;
  else if (x <= zone2.bis) {
    const y = (x - grundfreibetrag) / 10000;
    st = (zone2.a * y + zone2.b) * y;
  } else if (x <= zone3.bis) {
    const z = (x - zone2.bis) / 10000;
    st = (zone3.a * z + zone3.b) * z + zone3.c;
  } else if (x <= zone4.bis) st = zone4.satz * x - zone4.abzug;
  else st = zone5.satz * x - zone5.abzug;
  return floor(st + 1e-9);
}

/** Tarif mit Splittingverfahren (§ 32a Abs. 5 EStG) bei Zusammenveranlagung. */
export function tarifSteuer(zvE, tarif, zusammen) {
  if (!zusammen) return grundtarif(zvE, tarif);
  return 2 * grundtarif(floor(pos(zvE) / 2), tarif);
}

/** Solidaritätszuschlag mit Freigrenze und Milderungszone. */
export function soli(est, p, zusammen) {
  const grenze = p.soli.freigrenze * (zusammen ? 2 : 1);
  if (est <= grenze) return 0;
  return cents(Math.min(est * p.soli.satz, (est - grenze) * p.soli.milderung));
}

/** Werbungskosten aus nichtselbständiger Arbeit (Anlage N). */
export function werbungskosten(n, p) {
  const km = floor(pos(n.entfernungKm));
  const tage = pos(n.arbeitstage);
  const e = p.entfernungspauschale;
  const fahrt = tage * (Math.min(km, 20) * e.bis20km + Math.max(0, km - 20) * e.ab21km);
  const homeoffice = Math.min(pos(n.homeofficeTage), p.homeoffice.maxTage) * p.homeoffice.proTag;
  const tatsaechlich = fahrt + homeoffice + pos(n.arbeitsmittel) + pos(n.sonstigeWK);
  const brutto = pos(n.brutto);
  const abzug = Math.max(tatsaechlich, Math.min(p.arbeitnehmerPauschbetrag, brutto));
  return { fahrt: cents(fahrt), homeoffice, tatsaechlich: cents(tatsaechlich), abzug: cents(abzug) };
}

/** Abgeltungsteuer auf Kapitalerträge inkl. Kirchensteuer-Ermäßigung (§ 32d Abs. 1 EStG). */
export function kapitalertragsteuer(kap, p, personen, kistSatz) {
  const basis = Math.max(0, pos(kap.ertraege) - p.sparerPauschbetrag * personen);
  const k = kistSatz || 0;
  const kapESt = cents(basis / (4 + k) * (4 * p.abgeltungsteuer.satz));
  return {
    basis,
    kapESt,
    soli: cents(kapESt * p.soli.satz),
    kist: cents(kapESt * k),
  };
}

/**
 * Hauptberechnung. `input` siehe README (Felder der Web-App).
 * Liefert alle Zwischenschritte, damit die UI sie anzeigen kann.
 */
export function berechne(input, p) {
  const zusammen = input.veranlagung === "zusammen";
  const personen = zusammen ? 2 : 1;
  const kistSatz = input.kirche ? (input.kistSatz ?? 0.09) : 0;
  const personenDaten = (input.personen || []).slice(0, personen);

  // 1. Einkünfte aus nichtselbständiger Arbeit
  const anlageN = personenDaten.map((n) => {
    const wk = werbungskosten(n, p);
    return { brutto: pos(n.brutto), wk, einkuenfte: cents(pos(n.brutto) - wk.abzug) };
  });
  const sonstigeEinkuenfte = num(input.sonstigeEinkuenfte);
  const summeEinkuenfte = cents(anlageN.reduce((s, n) => s + n.einkuenfte, 0) + sonstigeEinkuenfte);

  // 2. Entlastungsbetrag für Alleinerziehende (§ 24b EStG)
  const kinder = floor(pos(input.kinder));
  let entlastung = 0;
  if (!zusammen && input.alleinerziehend && kinder > 0) {
    const e = p.entlastungAlleinerziehende;
    entlastung = e.basis + (kinder - 1) * e.jeWeiteresKind;
  }
  const gesamtbetrag = Math.max(0, summeEinkuenfte - entlastung);

  // 3. Sonderausgaben
  const vorsorge = personenDaten.reduce((s, n) => s + pos(n.rvAN) + pos(n.kvpvBasis), 0);
  const spendenAbziehbar = Math.min(pos(input.spenden), gesamtbetrag * p.spendenHoechstQuote);
  const uebrigeSA = Math.max(spendenAbziehbar, p.sonderausgabenPauschbetrag * personen);
  const sonderausgaben = cents(vorsorge + uebrigeSA);
  const einkommen = Math.max(0, cents(gesamtbetrag - sonderausgaben));

  // 4. Kinder: Günstigerprüfung Kindergeld vs. Kinderfreibeträge (§ 31 EStG)
  const anteil = zusammen ? 1 : 0.5; // Ledige: halber Freibetrag, halbes Kindergeld
  const kfb = kinder * p.kinder.freibetragJeKind * anteil;
  const kindergeldJahr = kinder * p.kinder.kindergeldMonat * 12 * anteil;
  const estOhneKFB = tarifSteuer(einkommen, p.tarif, zusammen);
  const zvEmitKFB = Math.max(0, floor(einkommen - kfb));
  const estMitKFB = tarifSteuer(zvEmitKFB, p.tarif, zusammen);
  const freibetragGuenstiger = kinder > 0 && estOhneKFB - estMitKFB > kindergeldJahr;
  const zvE = freibetragGuenstiger ? zvEmitKFB : floor(einkommen);
  const tarifESt = freibetragGuenstiger ? estMitKFB : estOhneKFB;

  // 5. Steuerermäßigungen § 35a EStG
  const a = p.paragraph35a;
  const ermHaushalt = Math.min(pos(input.haushaltsnah) * a.haushaltsnah.satz, a.haushaltsnah.max);
  const ermHandwerker = Math.min(pos(input.handwerker) * a.handwerker.satz, a.handwerker.max);
  const ermaessigung = floor(Math.min(tarifESt, ermHaushalt + ermHandwerker));

  // 6. Festzusetzende Einkommensteuer, Soli und Kirchensteuer
  const est = tarifESt - ermaessigung + (freibetragGuenstiger ? kindergeldJahr : 0);
  // Für Soli/KiSt werden Kinderfreibeträge immer berücksichtigt (§ 51a EStG)
  const estFuerZuschlag = Math.max(0, tarifSteuer(zvEmitKFB, p.tarif, zusammen) - ermaessigung);
  const soliBetrag = soli(estFuerZuschlag, p, zusammen);
  const kist = cents(estFuerZuschlag * kistSatz);

  // 7. Kapitalerträge (Abgeltungsteuer)
  const kap = kapitalertragsteuer(input.kap || {}, p, personen, kistSatz);
  const kapEinbehalten = {
    kapESt: pos(input.kap?.kapEStEinbehalten),
    soli: pos(input.kap?.soliEinbehalten),
    kist: pos(input.kap?.kistEinbehalten),
  };

  // 8. Vergleich mit einbehaltenen Steuern
  const lstEinbehalten = personenDaten.reduce((s, n) => s + pos(n.lohnsteuer), 0);
  const soliEinbehalten = personenDaten.reduce((s, n) => s + pos(n.soliEinbehalten), 0);
  const kistEinbehalten = personenDaten.reduce((s, n) => s + pos(n.kistEinbehalten), 0);

  const festgesetzt = cents(est + soliBetrag + kist + kap.kapESt + kap.soli + kap.kist);
  const vorausgezahlt = cents(
    lstEinbehalten + soliEinbehalten + kistEinbehalten +
      kapEinbehalten.kapESt + kapEinbehalten.soli + kapEinbehalten.kist,
  );
  const ergebnis = cents(vorausgezahlt - festgesetzt); // > 0 = Erstattung

  return {
    zusammen,
    anlageN,
    summeEinkuenfte,
    entlastung,
    gesamtbetrag,
    vorsorge: cents(vorsorge),
    spendenAbziehbar: cents(spendenAbziehbar),
    sonderausgaben,
    einkommen,
    kinder: { anzahl: kinder, freibetrag: kfb, kindergeldJahr, freibetragGuenstiger },
    zvE,
    tarifESt,
    ermaessigung,
    est,
    soli: soliBetrag,
    kist,
    kap,
    einbehalten: {
      lohnsteuer: lstEinbehalten,
      soli: soliEinbehalten,
      kist: kistEinbehalten,
      kap: kapEinbehalten,
    },
    festgesetzt,
    vorausgezahlt,
    ergebnis,
    durchschnittssatz: zvE > 0 ? tarifESt / zvE : 0,
  };
}
