// PC-Tests für den Analyse-Kern:  make -C kabeltester/tests
#include "../firmware/common/kabel_analyse.h"
#include <stdio.h>

using namespace kt;

static int fehlschlaege = 0, tests = 0;
#define PRUEFE(bed) do { ++tests; if (!(bed)) { ++fehlschlaege; \
  printf("FEHLER %s:%d: %s\n", __FILE__, __LINE__, #bed); } } while (0)

static int zaehle(const Ergebnis& e, FehlerTyp t) {
  int n = 0;
  for (int i = 0; i < e.anzahl; ++i) if (e.f[i].typ == t) ++n;
  return n;
}

// 8-adriges 1:1-Kabel A1..A8 -> B1..B8
static Profil profil8;
static void bauProfil() {
  profil8.leeren("Cat6 1:1", 128);
  for (int i = 0; i < 8; ++i) profil8.hinzu((uint16_t)i, (uint16_t)(64 + i), 0.5f);
}

static int messe8(Messung* m, float r = 0.1f) {
  for (int i = 0; i < 8; ++i) m[i] = {(uint16_t)i, (uint16_t)(64 + i), r, NAN};
  return 8;
}

static void testPinNamen() {
  char b[8];
  pinName(0, b, sizeof b);   PRUEFE(!strcmp(b, "A1"));
  pinName(63, b, sizeof b);  PRUEFE(!strcmp(b, "A64"));
  pinName(64, b, sizeof b);  PRUEFE(!strcmp(b, "B1"));
  pinName(200, b, sizeof b); PRUEFE(!strcmp(b, "D9"));
  PRUEFE(pinAusName("B1") == 64);
  PRUEFE(pinAusName("a64") == 63);
  PRUEFE(pinAusName("A0") == -1);
  PRUEFE(pinAusName("A65") == -1);
  PRUEFE(pinAusName("Z3") == -1);
}

static void testGutKabel() {
  Messung m[16]; int n = messe8(m);
  Ergebnis e; vergleiche(profil8, m, n, e);
  PRUEFE(e.ok);
  PRUEFE(e.anzahl == 0);
}

static void testUnterbrechung() {
  Messung m[16]; int n = messe8(m);
  m[3] = m[--n];   // Ader 4 fehlt
  Ergebnis e; vergleiche(profil8, m, n, e);
  PRUEFE(!e.ok);
  PRUEFE(zaehle(e, FehlerTyp::Unterbrechung) == 1);
  PRUEFE(e.f[0].a == 3 && e.f[0].b == 67);
}

static void testVertauscht() {
  Messung m[16]; int n = messe8(m);
  m[1].b = 66; m[2].b = 65;   // Adern 2 und 3 auf Seite B vertauscht
  Ergebnis e; vergleiche(profil8, m, n, e);
  PRUEFE(!e.ok);
  PRUEFE(e.anzahl == 1);
  PRUEFE(zaehle(e, FehlerTyp::Vertauscht) == 1);
}

static void testKurzschluss() {
  Messung m[16]; int n = messe8(m);
  // Ader 1 und 2 kurzgeschlossen: Scan liefert Spannbaum ab A1
  m[n++] = {0, 1, 0.1f, NAN};
  m[n++] = {0, 65, 0.2f, NAN};
  Ergebnis e; vergleiche(profil8, m, n, e);
  PRUEFE(!e.ok);
  PRUEFE(zaehle(e, FehlerTyp::Kurzschluss) == 1);   // nur einmal gemeldet
  PRUEFE(zaehle(e, FehlerTyp::Unterbrechung) == 0);
}

static void testFehlverdrahtung() {
  Messung m[16]; int n = messe8(m);
  m[4].b = 70;   // A5 geht auf B7 statt B5, B7 hängt zusätzlich an A7
  Ergebnis e; vergleiche(profil8, m, n, e);
  PRUEFE(!e.ok);
  PRUEFE(zaehle(e, FehlerTyp::Unterbrechung) >= 1);
  PRUEFE(zaehle(e, FehlerTyp::Kurzschluss) + zaehle(e, FehlerTyp::Fehlverdrahtung) >= 1);
}

static void testWiderstand() {
  Messung m[16]; int n = messe8(m);
  m[5].ohm = 2.0f;   // Übergangswiderstand am Stecker
  Ergebnis e; vergleiche(profil8, m, n, e);
  PRUEFE(!e.ok);
  PRUEFE(zaehle(e, FehlerTyp::Widerstand) == 1);
  PRUEFE(fabsf(e.f[0].ohm - 2.0f) < 1e-6f);
}

static void testHochohmig() {
  Messung m[16]; int n = messe8(m);
  m[n++] = {2, 3, 50e3f, NAN};   // Feuchtigkeit zwischen Ader 3 und 4
  Ergebnis e; vergleiche(profil8, m, n, e);
  PRUEFE(!e.ok);
  PRUEFE(zaehle(e, FehlerTyp::Hochohmig) == 1);
}

static void testDiode() {
  Messung d = {0, 64, 0, 0};
  d.ohmRueck = 1e6f;                  // Sperrrichtung
  float hin = 1000.0f;                 // Durchlass
  d.ohm = (hin + d.ohmRueck) / 2.0f;
  PRUEFE(istDiode(d));
  Messung gesperrt = {0, 64, 1500.0f, INFINITY};
  PRUEFE(istDiode(gesperrt));
  Messung offen = {0, 64, INFINITY, INFINITY};
  PRUEFE(!istDiode(offen));
  Messung r = {0, 64, 100.0f, 100.2f};
  PRUEFE(!istDiode(r));
}

static void testLernen() {
  Messung m[16]; int n = messe8(m, 0.2f);
  Profil p; p.leeren("gelernt", 128);
  lerneProfil(p, m, n);
  PRUEFE(p.anzahl == 8);
  PRUEFE(fabsf(p.v[0].maxOhm - (0.2f * 1.5f + 0.2f)) < 1e-6f);
  Ergebnis e; vergleiche(p, m, n, e);
  PRUEFE(e.ok);
}

static void testProfilText() {
  static char buf[4096];
  int len = profilSchreiben(profil8, buf, sizeof buf);
  PRUEFE(len > 0);
  Profil p;
  PRUEFE(profilLesen(p, buf));
  PRUEFE(!strcmp(p.name, "Cat6 1:1"));
  PRUEFE(p.anzahl == 8);
  PRUEFE(p.pinAnzahl == 128);
  PRUEFE(p.v[7].a == 7 && p.v[7].b == 71);
  PRUEFE(fabsf(p.v[7].maxOhm - 0.5f) < 1e-6f);
  PRUEFE(!profilLesen(p, "irgendwas"));
}

static void testLaenge() {
  // 1,5 mm² Kupfer, 10 m bei 20 °C: R = 0,017241 * 10 / 1,5 = 0,11494 Ohm
  PRUEFE(fabsf(laengeKupfer(0.11494f, 1.5f) - 10.0f) < 0.01f);
  // bei 30 °C ist das Kupfer hochohmiger -> gleiche Länge braucht mehr Widerstand
  PRUEFE(laengeKupfer(0.11494f, 1.5f, 30.0f) < 10.0f);
  PRUEFE(fabsf(awgZuMm2(24) - 0.205f) < 0.003f);
}

static void testOhmText() {
  char b[24];
  ohmText(0.0123f, b, sizeof b); PRUEFE(!strcmp(b, "12.3 mOhm"));
  ohmText(4700.0f, b, sizeof b); PRUEFE(!strcmp(b, "4.7 kOhm"));
  ohmText(INFINITY, b, sizeof b); PRUEFE(!strcmp(b, "offen"));
}

int main() {
  bauProfil();
  testPinNamen();
  testGutKabel();
  testUnterbrechung();
  testVertauscht();
  testKurzschluss();
  testFehlverdrahtung();
  testWiderstand();
  testHochohmig();
  testDiode();
  testLernen();
  testProfilText();
  testLaenge();
  testOhmText();
  printf("%d/%d Prüfungen bestanden\n", tests - fehlschlaege, tests);
  return fehlschlaege ? 1 : 0;
}
