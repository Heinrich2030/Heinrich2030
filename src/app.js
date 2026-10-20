import { berechne } from "./engine/tax.js";
import { KNOWN_YEARS, getYearParams } from "./data/tax-years.js";

const STORAGE_KEY = "steuer-app:eingaben:v1";
const form = document.getElementById("form");
const eur = new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" });
const pct = new Intl.NumberFormat("de-DE", { style: "percent", maximumFractionDigits: 1 });

// Jahresauswahl: alle bekannten Jahre plus das aktuelle Kalenderjahr
const aktuellesJahr = new Date().getFullYear();
const jahre = [...new Set([...KNOWN_YEARS, aktuellesJahr - 1, aktuellesJahr])].sort((a, b) => b - a);
const jahrSelect = document.getElementById("jahr");
for (const j of jahre) jahrSelect.add(new Option(String(j), String(j)));
jahrSelect.value = String(KNOWN_YEARS.includes(aktuellesJahr - 1) ? aktuellesJahr - 1 : KNOWN_YEARS.at(-1));

// Personenfelder aus Vorlage erzeugen
const tpl = document.getElementById("person-fields");
document.querySelectorAll("[data-person]").forEach((sec) => {
  sec.querySelector(".person").append(tpl.content.cloneNode(true));
});

function lesen() {
  const fd = new FormData(form);
  const v = (k) => fd.get(k);
  const input = {
    jahr: Number(v("jahr")),
    veranlagung: v("veranlagung"),
    kirche: v("kirche") !== "0",
    kistSatz: Number(v("kirche")),
    kinder: Number(v("kinder")) || 0,
    alleinerziehend: fd.has("alleinerziehend"),
    spenden: v("spenden"),
    haushaltsnah: v("haushaltsnah"),
    handwerker: v("handwerker"),
    sonstigeEinkuenfte: v("sonstigeEinkuenfte"),
    kap: {
      ertraege: v("kap.ertraege"),
      kapEStEinbehalten: v("kap.kapEStEinbehalten"),
      soliEinbehalten: v("kap.soliEinbehalten"),
      kistEinbehalten: v("kap.kistEinbehalten"),
    },
    personen: [...document.querySelectorAll("[data-person]")].map((sec) => {
      const p = {};
      sec.querySelectorAll("[data-f]").forEach((el) => (p[el.dataset.f] = el.value));
      return p;
    }),
  };
  return input;
}

function speichern() {
  try {
    const data = {};
    form.querySelectorAll("input, select").forEach((el, i) => {
      data[i] = el.type === "checkbox" ? el.checked : el.value;
    });
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch { /* Speicher nicht verfügbar – App funktioniert trotzdem */ }
}

function laden() {
  try {
    const data = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    if (!data) return;
    form.querySelectorAll("input, select").forEach((el, i) => {
      if (!(i in data)) return;
      if (el.type === "checkbox") el.checked = data[i];
      else el.value = data[i];
    });
  } catch { /* ignorieren */ }
}

function zeile(dl, label, wert, cls) {
  const dt = document.createElement("dt");
  const dd = document.createElement("dd");
  dt.textContent = label;
  dd.textContent = wert;
  if (cls) { dt.className = cls; dd.className = cls; }
  dl.append(dt, dd);
}

function render() {
  const input = lesen();
  const zusammen = input.veranlagung === "zusammen";
  document.querySelector('[data-person="1"]').hidden = !zusammen;

  const { year, params, fallback } = getYearParams(input.jahr);
  const hinweis = document.getElementById("jahr-hinweis");
  if (fallback) {
    hinweis.hidden = false;
    hinweis.textContent = `Für ${input.jahr} sind noch keine Steuerwerte hinterlegt. Gerechnet wird vorläufig mit den Werten von ${year}.`;
  } else if (params.status !== "verifiziert") {
    hinweis.hidden = false;
    hinweis.textContent = `Die Werte für ${year} sind vorläufig und werden noch geprüft.`;
  } else hinweis.hidden = true;

  const r = berechne(input, params);
  const big = document.getElementById("ergebnis");
  big.textContent = r.ergebnis >= 0 ? `Erstattung ${eur.format(r.ergebnis)}` : `Nachzahlung ${eur.format(-r.ergebnis)}`;
  big.className = "big " + (r.ergebnis >= 0 ? "good" : "bad");

  const dl = document.getElementById("details");
  dl.replaceChildren();
  r.anlageN.forEach((n, i) => {
    if (!n.brutto) return;
    zeile(dl, `Werbungskosten P${i + 1}`, eur.format(n.wk.abzug));
  });
  zeile(dl, "Summe der Einkünfte", eur.format(r.summeEinkuenfte));
  if (r.entlastung) zeile(dl, "Entlastungsbetrag Alleinerz.", "−" + eur.format(r.entlastung));
  zeile(dl, "Sonderausgaben", "−" + eur.format(r.sonderausgaben));
  if (r.kinder.anzahl) {
    zeile(dl, "Kinder", r.kinder.freibetragGuenstiger ? "Freibetrag günstiger" : "Kindergeld günstiger");
  }
  zeile(dl, "Zu versteuerndes Einkommen", eur.format(r.zvE), "sum");
  zeile(dl, "Tarifliche Einkommensteuer", eur.format(r.tarifESt));
  if (r.ermaessigung) zeile(dl, "Ermäßigung § 35a", "−" + eur.format(r.ermaessigung));
  zeile(dl, "Einkommensteuer", eur.format(r.est));
  zeile(dl, "Solidaritätszuschlag", eur.format(r.soli));
  if (input.kirche) zeile(dl, "Kirchensteuer", eur.format(r.kist));
  if (r.kap.basis) zeile(dl, "Abgeltungsteuer + Zuschläge", eur.format(r.kap.kapESt + r.kap.soli + r.kap.kist));
  zeile(dl, "Steuer gesamt", eur.format(r.festgesetzt), "sum");
  zeile(dl, "Bereits bezahlt", eur.format(r.vorausgezahlt));
  zeile(dl, "Durchschnittssteuersatz", pct.format(r.durchschnittssatz));
  zeile(dl, "Rechenwerte", `${year}${params.status === "verifiziert" ? "" : " (vorläufig)"}`);
}

laden();
form.addEventListener("input", () => { render(); speichern(); });
document.getElementById("reset").addEventListener("click", () => {
  form.reset();
  document.querySelectorAll("[data-f]").forEach((el) => (el.value = ""));
  try { localStorage.removeItem(STORAGE_KEY); } catch { /* ignorieren */ }
  render();
});
render();
