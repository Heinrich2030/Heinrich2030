// Ansteuerung der Analog-Multiplexer-Matrix über die 74HC595-Kette
//
// Jeder Testpunkt hängt an vier Multiplexern:
//   HI-Force (ADG1606)  HI-Sense (CD74HCT4067)  LO-Force (ADG1606)  LO-Sense (CD74HCT4067)
// Force und Sense eines Busses wählen immer denselben Pin (Kelvin direkt am Steckerpin).
#pragma once
#include <Arduino.h>
#include <SPI.h>
#include "hardware.h"

class Matrix {
 public:
  static constexpr int KEIN = -1;

  void begin(int karten) {
    anzahlKarten = karten;
    pinMode(hw::PIN_595_LATCH, OUTPUT);
    pinMode(hw::PIN_595_OE, OUTPUT);
    digitalWrite(hw::PIN_595_OE, HIGH);
    alles_aus();
    digitalWrite(hw::PIN_595_OE, LOW);
  }

  int pinAnzahl() const { return anzahlKarten * hw::PINS_PRO_KARTE; }

  void alles_aus() { hi = lo = KEIN; modus = 0; schieben(); }

  // Wählt Pins für HI- und LO-Bus und den Modus des Frontends in einem Schritt.
  void waehle(int hiPin, int loPin, uint8_t neuerModus) {
    hi = hiPin; lo = loPin; modus = neuerModus;
    schieben();
  }

  uint8_t aktuellerModus() const { return modus; }

 private:
  int anzahlKarten = 2;
  int hi = KEIN, lo = KEIN;
  uint8_t modus = 0;
  SPISettings spi{20000000, MSBFIRST, SPI_MODE0};

  void schieben() {
    uint8_t buf[2 + 2 * hw::MAX_KARTEN];
    buf[0] = (uint8_t)((hi >= 0 ? hi & 0x0F : 0) | ((lo >= 0 ? lo & 0x0F : 0) << 4));
    buf[1] = modus;
    for (int k = 0; k < anzahlKarten; ++k) {
      uint8_t en = 0;
      if (hi >= 0 && hi / hw::PINS_PRO_KARTE == k) en |= (uint8_t)(1 << ((hi % 64) / 16));
      if (lo >= 0 && lo / hw::PINS_PRO_KARTE == k) en |= (uint8_t)(1 << (4 + (lo % 64) / 16));
      buf[2 + 2 * k] = en;               // ADG1606: EN aktiv high
      buf[3 + 2 * k] = (uint8_t)~en;     // CD74HCT4067: /E aktiv low
    }
    int n = 2 + 2 * anzahlKarten;
    // Das zuletzt geschobene Byte landet im ersten Register der Kette (Hauptplatine).
    SPI.beginTransaction(spi);
    for (int i = n - 1; i >= 0; --i) SPI.transfer(buf[i]);
    SPI.endTransaction();
    digitalWrite(hw::PIN_595_LATCH, HIGH);
    digitalWrite(hw::PIN_595_LATCH, LOW);
  }
};
