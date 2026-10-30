// Messverfahren: Fremdspannungsprüfung, Schnellscan, 4-Leiter-Widerstand, Isolation
#pragma once
#include <Arduino.h>
#include <EEPROM.h>
#include "hardware.h"
#include "matrix.h"
#include "ads1220.h"
#include "kabel_analyse.h"

class Messgeraet {
 public:
  Matrix matrix;
  ADS1220 adc;
  float offset[kt::MAX_PINS] = {};   // Nullabgleich je Pin (Ω), aus Kurzschlussadapter

  void begin(int karten) {
    matrix.begin(karten);
    adc.begin();
    analogReadResolution(12);
    ladeKalibrierung();
  }

  int pins() const { return matrix.pinAnzahl(); }

  // --- Fremdspannung ---------------------------------------------------------
  // Jeder Pin wird über den LO-Sense-Bus gegen GND gemessen (10-kΩ-Last).
  // Rückgabe: erster Pin mit Spannung > FREMD_MAX_V oder -1.
  int fremdspannung(float& volt) {
    for (int p = 0; p < pins(); ++p) {
      matrix.waehle(Matrix::KEIN, p, hw::MODUS_SCAN_PD);
      delayMicroseconds(20);
      volt = scanSpannung();
      if (volt > hw::FREMD_MAX_V) { matrix.alles_aus(); return p; }
    }
    matrix.alles_aus();
    return -1;
  }

  // --- Schnellscan -----------------------------------------------------------
  // Prüft alle Pinpaare digital-schnell (1 kΩ Pull-up / 10 kΩ Pull-down, RP2350-ADC).
  // 128 Pins = 8128 Paare in ca. 80 ms. Ergebnis: Netze (Union-Find).
  void schnellscan(kt::Netze& netze, uint32_t& dauerMs) {
    uint32_t t0 = millis();
    netze.reset();
    const int n = pins();
    for (int i = 0; i < n; ++i) {
      for (int j = i + 1; j < n; ++j) {
        if (netze.wurzel(i) == netze.wurzel(j)) continue;   // schon bekannt: überspringen
        if (verbunden(i, j)) netze.verbinde(i, j);
      }
    }
    matrix.alles_aus();
    dauerMs = millis() - t0;
  }

  bool verbunden(int a, int b) {
    matrix.waehle(a, b, hw::MODUS_SCAN_PU | hw::MODUS_SCAN_PD);
    delayMicroseconds(4);   // Busse ca. 300 pF, 1 kΩ -> τ = 0,3 µs; Rest für Kabelkapazität
    return scanSpannung() > hw::SCAN_SCHWELLE * 3.3f;
  }

  // --- 4-Leiter-Widerstandsmessung mit Stromumkehr ---------------------------
  // Misst a->b und b->a; Mittelwert hebt Thermospannungen auf, die Differenz
  // zeigt Dioden/Halbleiter. Automatische Bereichswahl 10 mA … 10 µA.
  // praezise = 20 SPS mit 50/60-Hz-Filter (ca. 0,4 s), sonst 330 SPS (ca. 25 ms) für Serien.
  kt::Messung widerstand(int a, int b, int* bereichAus = nullptr, bool praezise = false) {
    int bereich = 0;
    float hin = einzelmessung(a, b, bereich, praezise);
    int bereichRueck = bereich;   // Rückrichtung startet im gefundenen Bereich
    float rueck = einzelmessung(b, a, bereichRueck, praezise);
    matrix.alles_aus();
    if (bereichAus) *bereichAus = bereich;
    float korr = offset[a] + offset[b];
    kt::Messung m;
    m.a = (uint16_t)a; m.b = (uint16_t)b;
    if (isinf(hin) && isinf(rueck)) {            // offen
      m.ohm = m.ohmRueck = INFINITY;
    } else if (isinf(hin) || isinf(rueck)) {     // eine Richtung sperrt: Diode, a = Anode
      if (isinf(hin)) { m.a = (uint16_t)b; m.b = (uint16_t)a; }
      m.ohm = fmaxf(fminf(hin, rueck) - korr, 0.0f);
      m.ohmRueck = INFINITY;
    } else {
      m.ohm = fmaxf((hin + rueck) / 2.0f - korr, 0.0f);
      m.ohmRueck = fmaxf(rueck - korr, 0.0f);
    }
    return m;
  }

  // --- Isolationswiderstand (5 V über 1 MΩ, ratiometrisch zu AVDD) -----------
  float isolation(int a, int b, uint16_t einschwingMs = 5) {
    matrix.waehle(a, b, hw::MODUS_ISO | hw::MODUS_LO_GND);
    delay(einschwingMs);
    float v = adc.messe(ADS1220::AIN0_AIN1, 0, ADS1220::REF_AVDD, true, 4 /* 330 SPS */);
    matrix.alles_aus();
    float x = v / adc.avdd;
    if (isnan(x)) return NAN;
    if (x >= 0.9995f) return INFINITY;   // > ca. 2 GΩ: nicht mehr auflösbar
    if (x < 0) x = 0;
    return hw::R_ISO * x / (1.0f - x);
  }

  // --- Nullabgleich mit Kurzschlussadapter (alle 64 Pins einer Seite auf eine Kupferschiene) ---
  // Je Seite: R(p,q) = off[p] + off[q]. off[erster Pin] aus drei Pins, dann off[p] = R(erster,p) - off[erster].
  // Seiten ohne Kurzschlussadapter bleiben unverändert. Rückgabe: Anzahl abgeglichener Seiten.
  int nullabgleich() {
    int seiten = 0;
    for (int basis = 0; basis < pins(); basis += hw::PINS_PRO_KARTE) {
      float neu[hw::PINS_PRO_KARTE];
      float alt[hw::PINS_PRO_KARTE];
      memcpy(alt, offset + basis, sizeof alt);
      memset(offset + basis, 0, sizeof alt);   // Rohwerte messen
      float r01 = widerstand(basis, basis + 1, nullptr, true).ohm;
      float r02 = widerstand(basis, basis + 2, nullptr, true).ohm;
      float r12 = widerstand(basis + 1, basis + 2, nullptr, true).ohm;
      float o0 = (r01 + r02 - r12) / 2.0f;
      bool ok = r01 < 5.0f && r02 < 5.0f && r12 < 5.0f && o0 >= 0.0f;
      neu[0] = o0;
      for (int k = 1; ok && k < hw::PINS_PRO_KARTE; ++k) {
        float r = widerstand(basis, basis + k, nullptr, true).ohm;
        ok = r < 5.0f;
        neu[k] = r - o0;
      }
      memcpy(offset + basis, ok ? neu : alt, sizeof alt);
      if (ok) ++seiten;
    }
    if (seiten) speichereKalibrierung();
    return seiten;
  }

  void loescheKalibrierung() { memset(offset, 0, sizeof offset); speichereKalibrierung(); }

  float temperatur() { return adc.temperatur(); }

 private:
  static constexpr uint32_t KAL_MAGIC = 0x4B414C31;   // "KAL1"

  float scanSpannung() {
    // LO-Sense -> OPA-Puffer -> Teiler 1:2 -> ADC0
    return (float)analogRead(hw::PIN_SCAN_ADC) * (3.3f / 4095.0f) * 2.0f;
  }

  // Eine Stromrichtung. bereich wird bei Überlauf erhöht (kleinerer Strom).
  float einzelmessung(int hiPin, int loPin, int& bereich, bool praezise) {
    for (; bereich < hw::ANZAHL_BEREICHE; ++bereich) {
      const hw::Bereich& b = hw::BEREICHE[bereich];
      matrix.waehle(hiPin, loPin, hw::MODUS_HI_QUELLE | hw::MODUS_LO_SENKE | b.bits);
      delay(bereich < 2 ? 2 : 10);
      uint8_t rate = praezise ? 0 : 4;       // 0 = 20 SPS + 50/60-Hz-Filter, 4 = 330 SPS
      float vShunt = adc.messe(ADS1220::AIN2_AVSS, 0, ADS1220::REF_INTERN, true, rate);
      if (isnan(vShunt)) return NAN;
      if (vShunt < 0.08f) continue;          // Senke kann Strom nicht halten -> Bereich zu groß
      float strom = vShunt / b.shunt;
      float vGrob = adc.messe(ADS1220::AIN0_AIN1, 0, ADS1220::REF_INTERN, false, 6);
      if (fabsf(vGrob) > 1.8f) continue;     // Messbereich überschritten
      uint8_t g = 0;
      while (g < 7 && fabsf(vGrob) * (float)(2 << g) < 1.8f) ++g;   // höchste passende Verstärkung
      float vDut = adc.messe(ADS1220::AIN0_AIN1, g, ADS1220::REF_INTERN, false, rate);
      return vDut / strom;
    }
    bereich = hw::ANZAHL_BEREICHE - 1;
    return INFINITY;
  }

  void ladeKalibrierung() {
    EEPROM.begin(4096);
    uint32_t magic = 0;
    EEPROM.get(0, magic);
    if (magic == KAL_MAGIC) EEPROM.get(4, offset);
  }
  void speichereKalibrierung() {
    EEPROM.put(0, KAL_MAGIC);
    EEPROM.put(4, offset);
    EEPROM.commit();
  }
};
