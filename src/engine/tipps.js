// Analysiert die Eingaben und schlägt Wege zum Steuersparen vor.
// Jeder Tipp mit Betrag wird per Vergleichsrechnung ("Was wäre, wenn …")
// mit derselben Engine ermittelt – keine Schätzwerte aus Faustregeln.
import { berechne } from "./tax.js";

const wert = (v) => Math.max(0, Number(v) || 0);
const clone = (o) => structuredClone(o);

/** Ersparnis in Euro, wenn `aendern` auf die Eingaben angewendet wird. */
function ersparnis(input, p, basis, aendern) {
  const neu = clone(input);
  aendern(neu);
  return Math.round((berechne(neu, p).festgesetzt - basis.festgesetzt) * -1);
}

/** Grenzsteuersatz inkl. Soli und Kirchensteuer: Steuer auf die nächsten 100 € Einkommen. */
export function grenzsteuersatz(input, p, basis) {
  const neu = clone(input);
  neu.sonstigeEinkuenfte = (Number(neu.sonstigeEinkuenfte) || 0) + 100;
  const r = berechne(neu, p);
  const diff = r.festgesetzt - r.kap.kapESt - r.kap.soli - r.kap.kist -
    (basis.festgesetzt - basis.kap.kapESt - basis.kap.soli - basis.kap.kist);
  return Math.max(0, diff / 100);
}

export function analysiere(input, p) {
  const tipps = [];
  const basis = berechne(input, p);
  const zusammen = basis.zusammen;
  const personen = (input.personen || []).slice(0, zusammen ? 2 : 1);
  const gs = grenzsteuersatz(input, p, basis);
  const gsText = `${Math.round(gs * 100)} %`;

  const add = (t) => tipps.push({ ersparnis: null, ...t });

  // 1. Werbungskosten unter dem Pauschbetrag
  personen.forEach((n, i) => {
    const wk = basis.anlageN[i]?.wk;
    if (!wk || !wert(n.brutto)) return;
    const wer = zusammen ? ` (Person ${i + 1})` : "";
    const luecke = p.arbeitnehmerPauschbetrag - wk.tatsaechlich;
    if (luecke > 0 && wk.tatsaechlich > p.arbeitnehmerPauschbetrag * 0.5) {
      add({
        id: `wk-buendeln-${i}`,
        kategorie: "Werbungskosten",
        titel: `Werbungskosten bündeln${wer}`,
        text: `Deine Werbungskosten (${euro(wk.tatsaechlich)}) liegen ${euro(luecke)} unter dem Pauschbetrag von ${euro(p.arbeitnehmerPauschbetrag)} und wirken sich deshalb nicht aus. Ziehe geplante Anschaffungen (Laptop, Fachliteratur, Fortbildung) in ein Jahr zusammen. Dann zählt jeder Euro über dem Pauschbetrag – im anderen Jahr bekommst du trotzdem die Pauschale.`,
      });
    }
    if (luecke < 0) {
      add({
        id: `wk-ok-${i}`,
        kategorie: "Werbungskosten",
        titel: `Werbungskosten über der Pauschale${wer}`,
        text: `Du liegst ${euro(-luecke)} über dem Pauschbetrag. Jeder weitere Euro Werbungskosten spart dir etwa ${gsText} Steuern. Vergiss nicht: Kontoführung (pauschal 16 €), Arbeitskleidung, Bewerbungen, Umzug aus beruflichen Gründen.`,
      });
    }

    // 2. Homeoffice-Tage
    const ho = wert(n.homeofficeTage);
    if (ho === 0 && wert(n.arbeitstage) < 230) {
      const s = ersparnis(input, p, basis, (x) => { x.personen[i].homeofficeTage = 50; });
      if (s > 0) {
        add({
          id: `homeoffice-${i}`,
          kategorie: "Werbungskosten",
          titel: `Homeoffice-Tage eintragen${wer}`,
          text: `Für jeden Tag, an dem du überwiegend zu Hause arbeitest, gibt es ${euro(p.homeoffice.proTag)} (max. ${p.homeoffice.maxTage} Tage). Schon 50 Tage würden dir ${euro(s)} bringen. Ein separates Arbeitszimmer ist dafür nicht nötig.`,
          ersparnis: s,
        });
      }
    }

    // 3. Entfernung ohne Arbeitstage
    if (wert(n.entfernungKm) > 0 && wert(n.arbeitstage) === 0) {
      add({
        id: `fahrt-tage-${i}`,
        kategorie: "Eingabe prüfen",
        titel: `Arbeitstage fehlen${wer}`,
        text: "Du hast eine Entfernung angegeben, aber keine Arbeitstage vor Ort. Ohne Tage wird die Pendlerpauschale nicht berechnet.",
      });
    }
  });

  // 4. Zusammenveranlagung vs. Einzelveranlagung
  if (zusammen) {
    const einzel = [0, 1].map((i) =>
      berechne({ ...clone(input), veranlagung: "einzel", alleinerziehend: false,
        kinder: input.kinder, personen: [clone(personen[i] || {})],
        kap: i === 0 ? input.kap : {}, spenden: i === 0 ? input.spenden : 0,
        haushaltsnah: i === 0 ? input.haushaltsnah : 0, handwerker: i === 0 ? input.handwerker : 0,
        sonstigeEinkuenfte: i === 0 ? input.sonstigeEinkuenfte : 0 }, p).festgesetzt);
    const vorteil = Math.round(einzel[0] + einzel[1] - basis.festgesetzt);
    if (vorteil > 0) {
      add({
        id: "splitting",
        kategorie: "Veranlagung",
        titel: "Zusammenveranlagung lohnt sich",
        text: `Der Splittingtarif spart euch gegenüber zwei Einzelveranlagungen etwa ${euro(vorteil)}. Je unterschiedlicher eure Einkommen, desto größer der Vorteil. Die Steuerklassenwahl (III/V oder IV/IV) ändert nur die monatlichen Abzüge, nicht die Jahressteuer.`,
        ersparnis: vorteil,
      });
    }
  }

  // 5. Altersvorsorge (Basisrente / Rürup) – voll als Sonderausgabe abziehbar
  if (gs > 0.2) {
    const s = ersparnis(input, p, basis, (x) => {
      x.personen[0].rvAN = wert(x.personen[0].rvAN) + 1000;
    });
    if (s > 0) {
      add({
        id: "basisrente",
        kategorie: "Altersvorsorge",
        titel: "Altersvorsorge mit Steuervorteil",
        text: `Bei deinem Grenzsteuersatz von ${gsText} bringen 1.000 € Einzahlung in eine Basisrente (Rürup) etwa ${euro(s)} Steuerersparnis, weil sie wie Rentenbeiträge voll abziehbar ist. Alternative: betriebliche Altersvorsorge (Entgeltumwandlung) – dort sparst du zusätzlich Sozialabgaben. Die Auszahlung im Alter wird versteuert; lass dich vor Abschluss beraten.`,
        ersparnis: s,
      });
    }
  }

  // 6. Spenden
  if (gs > 0) {
    const s = ersparnis(input, p, basis, (x) => { x.spenden = wert(x.spenden) + 100; });
    if (s > 0) {
      add({
        id: "spenden",
        kategorie: "Sonderausgaben",
        titel: wert(input.spenden) ? "Spenden wirken" : "Spenden absetzen",
        text: `Von 100 € Spende an eine gemeinnützige Organisation trägt das Finanzamt bei dir etwa ${euro(s)}. Bis 300 € reicht der Kontoauszug als Nachweis. Hinweis: Spenden und gezahlte Kirchensteuer wirken erst, wenn sie zusammen über ${euro(p.sonderausgabenPauschbetrag * (zusammen ? 2 : 1))} liegen.`,
        ersparnis: s,
      });
    }
  }

  // 7. Haushaltsnahe Dienstleistungen & Handwerker (§ 35a)
  const a = p.paragraph35a;
  if (basis.tarifESt > 0) {
    if (!wert(input.handwerker)) {
      const s = ersparnis(input, p, basis, (x) => { x.handwerker = 1000; });
      add({
        id: "handwerker",
        kategorie: "Steuerermäßigung",
        titel: "Handwerkerkosten absetzen",
        text: `${Math.round(a.handwerker.satz * 100)} % der Arbeits- und Fahrtkosten (nicht Material) für Reparaturen, Wartung oder Renovierung in deiner Wohnung werden direkt von der Steuer abgezogen – auch als Mieter (Nebenkostenabrechnung: Hausmeister, Wartung). 1.000 € Arbeitskosten = ${euro(s)} weniger Steuer. Wichtig: Rechnung + Überweisung, keine Barzahlung.`,
        ersparnis: s,
      });
    } else if (wert(input.handwerker) * a.handwerker.satz > a.handwerker.max) {
      add({
        id: "handwerker-max",
        kategorie: "Steuerermäßigung",
        titel: "Handwerker-Höchstbetrag überschritten",
        text: `Begünstigt sind maximal ${euro(a.handwerker.max / a.handwerker.satz)} Arbeitskosten pro Jahr. Verteile größere Aufträge auf zwei Jahre (z. B. Teilrechnungen im Dezember und Januar).`,
      });
    }
    if (!wert(input.haushaltsnah)) {
      add({
        id: "haushaltsnah",
        kategorie: "Steuerermäßigung",
        titel: "Haushaltsnahe Dienstleistungen",
        text: `Reinigungskraft, Gartenpflege, Winterdienst, Treppenhausreinigung (oft in der Nebenkostenabrechnung): ${Math.round(a.haushaltsnah.satz * 100)} % der Kosten, bis ${euro(a.haushaltsnah.max)} Ermäßigung pro Jahr, gehen direkt von der Steuer ab.`,
      });
    }
  }

  // 8. Kapitalerträge
  const kap = input.kap || {};
  const pausch = p.sparerPauschbetrag * (zusammen ? 2 : 1);
  if (wert(kap.kapEStEinbehalten) > 0 && wert(kap.ertraege) <= pausch) {
    add({
      id: "freistellungsauftrag",
      kategorie: "Kapitalerträge",
      titel: "Zu viel Kapitalertragsteuer gezahlt",
      text: `Deine Erträge liegen unter dem Sparerpauschbetrag von ${euro(pausch)}, trotzdem wurde Steuer einbehalten. Mit der Anlage KAP bekommst du sie zurück – und mit einem Freistellungsauftrag bei der Bank passiert das künftig gar nicht erst.`,
      ersparnis: Math.round(wert(kap.kapEStEinbehalten) + wert(kap.soliEinbehalten) + wert(kap.kistEinbehalten)),
    });
  }
  if (basis.kap.basis > 0 && gs < p.abgeltungsteuer.satz) {
    // Günstigerprüfung: Kapitalerträge mit persönlichem Tarif statt 25 %
    const ohneKap = clone(input);
    ohneKap.kap = { ...kap, ertraege: 0 };
    ohneKap.sonstigeEinkuenfte = (Number(input.sonstigeEinkuenfte) || 0) + basis.kap.basis;
    const s = Math.round(basis.festgesetzt - berechne(ohneKap, p).festgesetzt);
    if (s > 0) {
      add({
        id: "guenstigerpruefung",
        kategorie: "Kapitalerträge",
        titel: "Günstigerprüfung beantragen",
        text: `Dein persönlicher Steuersatz liegt unter 25 %. Kreuze in der Anlage KAP die Günstigerprüfung an: Dann werden deine Kapitalerträge mit deinem niedrigeren Satz besteuert.`,
        ersparnis: s,
      });
    }
  }

  // 9. Kinder
  if (wert(input.kinder) > 0) {
    add({
      id: "kinderbetreuung",
      kategorie: "Kinder",
      titel: "Kinderbetreuungskosten",
      text: "Kita, Tagesmutter, Hort oder Babysitter (für Kinder unter 14) sind zu 80 % als Sonderausgaben abziehbar (bis 4.800 € je Kind). Verpflegung zählt nicht. Diese App rechnet das noch nicht mit ein.",
    });
  }

  // 10. Nachzahlung hoch
  if (basis.ergebnis < -400) {
    add({
      id: "nachzahlung",
      kategorie: "Planung",
      titel: "Nachzahlung einplanen",
      text: `Es droht eine Nachzahlung von ${euro(-basis.ergebnis)}. Häufige Ursachen: Steuerklasse III/V, Nebeneinkünfte oder fehlende Abzüge. Bei regelmäßigen Nachzahlungen setzt das Finanzamt Vorauszahlungen fest – lege dir den Betrag zurück.`,
    });
  }

  tipps.sort((x, y) => (y.ersparnis ?? -1) - (x.ersparnis ?? -1));
  return { grenzsteuersatz: gs, tipps };
}

function euro(v) {
  return new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(v);
}

