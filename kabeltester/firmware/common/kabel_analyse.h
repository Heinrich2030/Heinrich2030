// Kabeltester – gemeinsamer Analyse-Kern (Messkarte, Display und PC-Tests)
//
// Hardware-unabhängig, ohne dynamische Arduino-Abhängigkeiten. Wird auf dem PC
// mit `make -C kabeltester/tests` geprüft.
//
// Begriffe:
//   Pin       – globaler Testpunkt 0..MAX_PINS-1 (Seite A = 0..63, Seite B = 64..127, ...)
//   Messung   – gefundene Verbindung zweier Pins mit gemessenem Widerstand
//   Netz      – Menge von Pins, die untereinander leitend verbunden sind
//   Profil    – Soll-Zustand eines Kabels (eingelernt oder von Hand erstellt)
#pragma once

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

namespace kt {

constexpr int MAX_PINS = 256;          // 4 Kanalkarten à 64 Pins
constexpr int PINS_PRO_SEITE = 64;
constexpr int MAX_MESSUNGEN = 512;
constexpr int MAX_FEHLER = 64;
constexpr float OHM_OFFEN = INFINITY;

// ---------------------------------------------------------------------------
// Pin-Namen: "A1" .. "A64", "B1" .. "B64", "C1" ..
// ---------------------------------------------------------------------------
inline void pinName(int pin, char* buf, size_t len) {
  snprintf(buf, len, "%c%d", 'A' + pin / PINS_PRO_SEITE, pin % PINS_PRO_SEITE + 1);
}

inline int pinAusName(const char* s) {
  if (!s || !*s) return -1;
  char c = s[0];
  if (c >= 'a' && c <= 'z') c = (char)(c - 'a' + 'A');
  if (c < 'A' || c >= 'A' + MAX_PINS / PINS_PRO_SEITE) return -1;
  char* end = nullptr;
  long n = strtol(s + 1, &end, 10);
  if (end == s + 1 || n < 1 || n > PINS_PRO_SEITE) return -1;
  return (c - 'A') * PINS_PRO_SEITE + (int)(n - 1);
}

// ---------------------------------------------------------------------------
// Union-Find für Netzbildung
// ---------------------------------------------------------------------------
struct Netze {
  int16_t eltern[MAX_PINS];
  void reset() { for (int i = 0; i < MAX_PINS; ++i) eltern[i] = (int16_t)i; }
  int wurzel(int p) {
    while (eltern[p] != p) { eltern[p] = eltern[eltern[p]]; p = eltern[p]; }
    return p;
  }
  void verbinde(int a, int b) {
    a = wurzel(a); b = wurzel(b);
    if (a == b) return;
    if (a < b) eltern[b] = (int16_t)a; else eltern[a] = (int16_t)b;  // kleinster Pin = Netz-ID
  }
};

struct Messung {
  uint16_t a, b;
  float ohm;          // Mittelwert beider Stromrichtungen
  float ohmRueck;     // Gegenrichtung b->a (Diodenerkennung), NAN = nicht gemessen,
                      // INFINITY = gesperrt (dann ist a die Anode)
};

// ---------------------------------------------------------------------------
// Prüfprofil (Soll-Zustand)
// ---------------------------------------------------------------------------
struct SollVerbindung {
  uint16_t a, b;
  float maxOhm;       // Grenzwert für diese Verbindung
};

struct Profil {
  char name[32];
  uint16_t pinAnzahl;              // berücksichtigte Pins (0..pinAnzahl-1)
  float durchgangOhm;              // ab hier gilt eine Verbindung als "Durchgang"
  float isolationMinOhm;           // Mindest-Isolationswiderstand zwischen Netzen
  uint16_t anzahl;
  SollVerbindung v[MAX_MESSUNGEN];

  void leeren(const char* n, uint16_t pins) {
    memset(this, 0, sizeof(*this));
    strncpy(name, n, sizeof(name) - 1);
    pinAnzahl = pins;
    durchgangOhm = 10.0f;
    isolationMinOhm = 10e6f;
  }
  bool hinzu(uint16_t a, uint16_t b, float maxOhm) {
    if (anzahl >= MAX_MESSUNGEN || a == b) return false;
    if (a > b) { uint16_t t = a; a = b; b = t; }
    v[anzahl++] = {a, b, maxOhm};
    return true;
  }
};

// Referenzkabel einlernen: gemessene Verbindungen -> Profil.
// Grenzwert = Messwert * (1 + reserve) + absolut (fängt Übergangswiderstände ab).
inline void lerneProfil(Profil& p, const Messung* m, int n,
                        float reserveRel = 0.5f, float reserveAbs = 0.2f) {
  p.anzahl = 0;
  for (int i = 0; i < n; ++i) {
    if (m[i].ohm > p.durchgangOhm) continue;   // hochohmige Pfade nicht als Soll übernehmen
    p.hinzu(m[i].a, m[i].b, m[i].ohm * (1.0f + reserveRel) + reserveAbs);
  }
}

// ---------------------------------------------------------------------------
// Profil als Text (SD-Karte / Web-Download)
//   KABELPROFIL 1
//   name=Patchkabel Cat6
//   pins=128
//   durchgang=10
//   isolation=10000000
//   A1-B1 0.5
// ---------------------------------------------------------------------------
inline int profilSchreiben(const Profil& p, char* buf, size_t len) {
  size_t o = 0;
  auto add = [&](const char* fmt, auto... args) {
    if (o < len) o += (size_t)snprintf(buf + o, len - o, fmt, args...);
  };
  add("KABELPROFIL 1\nname=%s\npins=%u\ndurchgang=%g\nisolation=%g\n",
      p.name, (unsigned)p.pinAnzahl, (double)p.durchgangOhm, (double)p.isolationMinOhm);
  char na[8], nb[8];
  for (int i = 0; i < p.anzahl; ++i) {
    pinName(p.v[i].a, na, sizeof na);
    pinName(p.v[i].b, nb, sizeof nb);
    add("%s-%s %g\n", na, nb, (double)p.v[i].maxOhm);
  }
  return o < len ? (int)o : -1;
}

inline bool profilLesen(Profil& p, const char* text) {
  p.leeren("", PINS_PRO_SEITE * 2);
  if (strncmp(text, "KABELPROFIL 1", 13) != 0) return false;
  const char* z = text;
  char zeile[96];
  while (*z) {
    size_t l = strcspn(z, "\r\n");
    size_t k = l < sizeof(zeile) - 1 ? l : sizeof(zeile) - 1;
    memcpy(zeile, z, k); zeile[k] = 0;
    z += l; while (*z == '\r' || *z == '\n') ++z;
    if (!zeile[0] || zeile[0] == '#') continue;
    if (!strncmp(zeile, "name=", 5)) { strncpy(p.name, zeile + 5, sizeof(p.name) - 1); continue; }
    if (!strncmp(zeile, "pins=", 5)) { p.pinAnzahl = (uint16_t)atoi(zeile + 5); continue; }
    if (!strncmp(zeile, "durchgang=", 10)) { p.durchgangOhm = (float)atof(zeile + 10); continue; }
    if (!strncmp(zeile, "isolation=", 10)) { p.isolationMinOhm = (float)atof(zeile + 10); continue; }
    char* strich = strchr(zeile, '-');
    if (!strich) continue;
    *strich = 0;
    char* rest = strich + 1;
    char* leer = strchr(rest, ' ');
    float maxOhm = p.durchgangOhm;
    if (leer) { *leer = 0; maxOhm = (float)atof(leer + 1); }
    int a = pinAusName(zeile), b = pinAusName(rest);
    if (a < 0 || b < 0) return false;
    p.hinzu((uint16_t)a, (uint16_t)b, maxOhm);
  }
  return p.pinAnzahl > 0 && p.pinAnzahl <= MAX_PINS;
}

// ---------------------------------------------------------------------------
// Soll/Ist-Vergleich
// ---------------------------------------------------------------------------
enum class FehlerTyp : uint8_t {
  Unterbrechung,      // Soll-Verbindung fehlt
  Kurzschluss,        // zwei Soll-Netze vollständig miteinander verbunden
  Fehlverdrahtung,    // Pin hängt am falschen Netz
  Vertauscht,         // zwei Adern vertauscht (Sonderfall Fehlverdrahtung)
  Widerstand,         // Verbindung vorhanden, aber zu hochohmig
  Hochohmig,          // unerwarteter Pfad oberhalb Durchgangsgrenze (Feuchte, Schmutz, Bauteil)
  Diode,              // richtungsabhängiger Pfad
};

inline const char* fehlerText(FehlerTyp t) {
  switch (t) {
    case FehlerTyp::Unterbrechung:   return "Unterbrechung";
    case FehlerTyp::Kurzschluss:     return "Kurzschluss";
    case FehlerTyp::Fehlverdrahtung: return "Fehlverdrahtung";
    case FehlerTyp::Vertauscht:      return "Vertauscht";
    case FehlerTyp::Widerstand:      return "Widerstand zu hoch";
    case FehlerTyp::Hochohmig:       return "Hochohmiger Pfad";
    case FehlerTyp::Diode:           return "Diode/Halbleiter";
  }
  return "?";
}

struct Fehler {
  FehlerTyp typ;
  uint16_t a, b;
  float ohm;          // Messwert (falls sinnvoll)
  float grenze;       // Grenzwert (falls sinnvoll)
};

struct Ergebnis {
  bool ok;
  uint16_t anzahl;
  Fehler f[MAX_FEHLER];
  void add(FehlerTyp t, int a, int b, float ohm = NAN, float grenze = NAN) {
    ok = false;
    if (anzahl < MAX_FEHLER) f[anzahl++] = {t, (uint16_t)a, (uint16_t)b, ohm, grenze};
  }
};

// Diode: Durchlass deutlich kleiner als Sperrrichtung.
// ohmRueck = INFINITY bei endlichem ohm: Sperrrichtung nicht messbar -> Diode (a = Anode).
inline bool istDiode(const Messung& m, float faktor = 3.0f) {
  if (isnan(m.ohmRueck) || isinf(m.ohm)) return false;
  if (isinf(m.ohmRueck)) return true;
  float hin = 2.0f * m.ohm - m.ohmRueck;   // m.ohm ist Mittelwert
  float lo = fminf(hin, m.ohmRueck), hi = fmaxf(hin, m.ohmRueck);
  return lo > 0.0f && hi / lo > faktor;
}

inline float gemessenerWiderstand(const Messung* m, int n, int a, int b) {
  if (a > b) { int t = a; a = b; b = t; }
  for (int i = 0; i < n; ++i)
    if ((m[i].a == a && m[i].b == b) || (m[i].a == b && m[i].b == a)) return m[i].ohm;
  return NAN;
}

inline void vergleiche(const Profil& p, const Messung* m, int n, Ergebnis& e) {
  memset(&e, 0, sizeof(e));
  e.ok = true;
  static Netze soll, ist;   // statisch: spart Stack auf Mikrocontrollern
  soll.reset(); ist.reset();

  for (int i = 0; i < p.anzahl; ++i) soll.verbinde(p.v[i].a, p.v[i].b);
  for (int i = 0; i < n; ++i) {
    if (m[i].a >= p.pinAnzahl || m[i].b >= p.pinAnzahl) continue;
    if (istDiode(m[i])) { e.add(FehlerTyp::Diode, m[i].a, m[i].b, m[i].ohm); continue; }
    if (m[i].ohm <= p.durchgangOhm) ist.verbinde(m[i].a, m[i].b);
    else if (soll.wurzel(m[i].a) != soll.wurzel(m[i].b))
      e.add(FehlerTyp::Hochohmig, m[i].a, m[i].b, m[i].ohm, p.isolationMinOhm);
  }

  // 1) Vertauschungen: zwei 2-Pin-Sollnetze {a1,b1},{a2,b2} gemessen als {a1,b2},{a2,b1}
  static bool erledigt[MAX_PINS];
  memset(erledigt, 0, sizeof(erledigt));
  for (int i = 0; i < p.anzahl; ++i) {
    for (int j = i + 1; j < p.anzahl; ++j) {
      int a1 = p.v[i].a, b1 = p.v[i].b, a2 = p.v[j].a, b2 = p.v[j].b;
      if (erledigt[a1] || erledigt[a2]) continue;
      if (ist.wurzel(a1) == ist.wurzel(b1) || ist.wurzel(a2) == ist.wurzel(b2)) continue;
      if (ist.wurzel(a1) == ist.wurzel(b2) && ist.wurzel(a2) == ist.wurzel(b1)) {
        e.add(FehlerTyp::Vertauscht, b1, b2);
        erledigt[a1] = erledigt[b1] = erledigt[a2] = erledigt[b2] = true;
      }
    }
  }

  // 2) Unterbrechungen: Soll-Verbindung, deren Pins in verschiedenen Ist-Netzen liegen
  for (int i = 0; i < p.anzahl; ++i) {
    int a = p.v[i].a, b = p.v[i].b;
    if (erledigt[a] && erledigt[b]) continue;
    if (ist.wurzel(a) != ist.wurzel(b)) {
      // nur melden, wenn kein anderer Soll-Pfad die beiden schon verbindet
      e.add(FehlerTyp::Unterbrechung, a, b, gemessenerWiderstand(m, n, a, b), p.v[i].maxOhm);
    } else {
      float r = gemessenerWiderstand(m, n, a, b);
      if (!isnan(r) && r > p.v[i].maxOhm) e.add(FehlerTyp::Widerstand, a, b, r, p.v[i].maxOhm);
    }
  }

  // 3) Falsche Verbindungen: Ist-Netz verbindet Pins verschiedener Soll-Netze
  //    (jedes Paar von Soll-Netzen nur einmal melden)
  static uint16_t gemeldet[MAX_FEHLER][2];
  int nGemeldet = 0;
  for (int i = 0; i < n; ++i) {
    int a = m[i].a, b = m[i].b;
    if (a >= p.pinAnzahl || b >= p.pinAnzahl || m[i].ohm > p.durchgangOhm) continue;
    if (erledigt[a] && erledigt[b]) continue;
    int sa = soll.wurzel(a), sb = soll.wurzel(b);
    if (sa == sb) continue;
    bool doppelt = false;
    for (int g = 0; g < nGemeldet; ++g)
      if ((gemeldet[g][0] == sa && gemeldet[g][1] == sb) ||
          (gemeldet[g][0] == sb && gemeldet[g][1] == sa)) doppelt = true;
    if (doppelt) continue;
    if (nGemeldet < MAX_FEHLER) { gemeldet[nGemeldet][0] = (uint16_t)sa; gemeldet[nGemeldet][1] = (uint16_t)sb; ++nGemeldet; }
    // Kurzschluss, wenn beide Sollnetze in diesem Ist-Netz vollständig enthalten sind
    bool komplett = true;
    int netz = ist.wurzel(a);
    for (int q = 0; q < p.pinAnzahl && komplett; ++q) {
      int s = soll.wurzel(q);
      if ((s == sa || s == sb) && ist.wurzel(q) != netz) komplett = false;
    }
    e.add(komplett ? FehlerTyp::Kurzschluss : FehlerTyp::Fehlverdrahtung, a, b, m[i].ohm);
  }
}

// ---------------------------------------------------------------------------
// Leitungslänge aus Widerstand (Kupfer), temperaturkompensiert
//   rho_Cu(20 °C) = 0,017241 Ohm·mm²/m, alpha = 0,00393 1/K
// ---------------------------------------------------------------------------
inline float laengeKupfer(float ohm, float querschnittMm2, float tempC = 20.0f) {
  const float rho20 = 0.017241f, alpha = 0.00393f;
  float rho = rho20 * (1.0f + alpha * (tempC - 20.0f));
  return ohm * querschnittMm2 / rho;
}

// AWG -> Querschnitt in mm²
inline float awgZuMm2(int awg) {
  float d = 0.127f * powf(92.0f, (36.0f - (float)awg) / 39.0f);
  return 3.14159265f * d * d / 4.0f;
}

// Lesbare Widerstandsangabe: "12.3 mΩ", "4.70 kΩ", "offen"
inline void ohmText(float r, char* buf, size_t len) {
  if (isnan(r)) { snprintf(buf, len, "-"); return; }
  if (isinf(r) || r > 1e9f) { snprintf(buf, len, "offen"); return; }
  if (r < 1.0f)       snprintf(buf, len, "%.1f mOhm", (double)(r * 1e3f));
  else if (r < 1e3f)  snprintf(buf, len, "%.3g Ohm", (double)r);
  else if (r < 1e6f)  snprintf(buf, len, "%.3g kOhm", (double)(r / 1e3f));
  else                snprintf(buf, len, "%.3g MOhm", (double)(r / 1e6f));
}

}  // namespace kt
