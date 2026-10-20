// Steuerparameter pro Jahr. Die Rechen-Engine enthält keine Jahreszahlen –
// alles Jahresabhängige steht hier. Neue Jahre werden nur hier ergänzt
// (siehe CLAUDE.md und docs/KI-UEBERWACHUNG.md).
//
// status: "verifiziert" = gegen Gesetzestext/BMF geprüft
//         "vorläufig"   = Gesetz beschlossen/angekündigt, noch nicht final geprüft

const BASIS = {
  sparerPauschbetrag: 1000, // je Person
  arbeitnehmerPauschbetrag: 1230,
  sonderausgabenPauschbetrag: 36, // je Person
  homeoffice: { proTag: 6, maxTage: 210 },
  spendenHoechstQuote: 0.2,
  paragraph35a: {
    haushaltsnah: { satz: 0.2, max: 4000 },
    handwerker: { satz: 0.2, max: 1200 },
  },
  abgeltungsteuer: { satz: 0.25 },
  entlastungAlleinerziehende: { basis: 4260, jeWeiteresKind: 240 },
};

export const TAX_YEARS = {
  2023: {
    ...BASIS,
    status: "verifiziert",
    quellen: ["§ 32a EStG i.d.F. Inflationsausgleichsgesetz (BGBl. 2022 I S. 2230)"],
    tarif: {
      grundfreibetrag: 10908,
      zone2: { bis: 15999, a: 979.18, b: 1400 },
      zone3: { bis: 62809, a: 192.59, b: 2397, c: 966.53 },
      zone4: { bis: 277825, satz: 0.42, abzug: 9972.98 },
      zone5: { satz: 0.45, abzug: 18307.73 },
    },
    soli: { freigrenze: 17543, satz: 0.055, milderung: 0.119 },
    kinder: { freibetragJeKind: 8952, kindergeldMonat: 250 },
    entfernungspauschale: { bis20km: 0.3, ab21km: 0.38 },
  },
  2024: {
    ...BASIS,
    status: "verifiziert",
    quellen: ["§ 32a EStG i.d.F. Steuerfortentwicklungsgesetz (BGBl. 2024 I Nr. 449)"],
    tarif: {
      grundfreibetrag: 11784,
      zone2: { bis: 17005, a: 954.8, b: 1400 },
      zone3: { bis: 66760, a: 181.19, b: 2397, c: 991.21 },
      zone4: { bis: 277825, satz: 0.42, abzug: 10636.31 },
      zone5: { satz: 0.45, abzug: 18971.06 },
    },
    soli: { freigrenze: 18130, satz: 0.055, milderung: 0.119 },
    kinder: { freibetragJeKind: 9540, kindergeldMonat: 250 },
    entfernungspauschale: { bis20km: 0.3, ab21km: 0.38 },
  },
  2025: {
    ...BASIS,
    status: "verifiziert",
    quellen: ["§ 32a EStG i.d.F. Steuerfortentwicklungsgesetz (BGBl. 2024 I Nr. 449)"],
    tarif: {
      grundfreibetrag: 12096,
      zone2: { bis: 17443, a: 932.3, b: 1400 },
      zone3: { bis: 68480, a: 176.64, b: 2397, c: 1015.13 },
      zone4: { bis: 277825, satz: 0.42, abzug: 10911.92 },
      zone5: { satz: 0.45, abzug: 19246.67 },
    },
    soli: { freigrenze: 19950, satz: 0.055, milderung: 0.119 },
    kinder: { freibetragJeKind: 9600, kindergeldMonat: 255 },
    entfernungspauschale: { bis20km: 0.3, ab21km: 0.38 },
  },
  2026: {
    ...BASIS,
    status: "vorläufig",
    quellen: [
      "§ 32a EStG i.d.F. Steuerfortentwicklungsgesetz (BGBl. 2024 I Nr. 449)",
      "Entfernungspauschale 0,38 € ab dem 1. km: Steueränderungsgesetz 2025 – bitte prüfen",
    ],
    tarif: {
      grundfreibetrag: 12348,
      zone2: { bis: 17799, a: 914.51, b: 1400 },
      zone3: { bis: 69878, a: 173.1, b: 2397, c: 1034.87 },
      zone4: { bis: 277825, satz: 0.42, abzug: 11135.63 },
      zone5: { satz: 0.45, abzug: 19470.38 },
    },
    soli: { freigrenze: 20350, satz: 0.055, milderung: 0.119 },
    kinder: { freibetragJeKind: 9756, kindergeldMonat: 259 },
    entfernungspauschale: { bis20km: 0.38, ab21km: 0.38 },
  },
};

export const KNOWN_YEARS = Object.keys(TAX_YEARS).map(Number).sort((a, b) => a - b);

/**
 * Liefert die Parameter für ein Jahr. Fehlt das Jahr, wird das neueste
 * bekannte Jahr verwendet und `fallback` gesetzt, damit die UI warnen kann.
 */
export function getYearParams(year) {
  const y = Number(year);
  if (TAX_YEARS[y]) return { year: y, params: TAX_YEARS[y], fallback: false };
  const older = KNOWN_YEARS.filter((k) => k <= y);
  const used = older.length ? older[older.length - 1] : KNOWN_YEARS[0];
  return { year: used, params: TAX_YEARS[used], fallback: true };
}
