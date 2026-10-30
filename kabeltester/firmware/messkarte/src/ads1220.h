// Minimaler Treiber für den 24-Bit-ADC TI ADS1220 (SPI-Modus 1)
#pragma once
#include <Arduino.h>
#include <SPI.h>
#include "hardware.h"

class ADS1220 {
 public:
  // Eingangs-Multiplexer (Register 0, Bits 7:4)
  enum Mux : uint8_t {
    AIN0_AIN1 = 0x0,   // Sense+ / Sense-  (Kelvin-Spannung am Prüfling)
    AIN2_AVSS = 0xA,   // Shunt-Spannung der Stromsenke
    AIN3_AVSS = 0xB,   // Teiler 1:2 der 2,5-V-Quelle (Selbsttest)
    AIN0_AVSS = 0x8,
  };
  enum Ref : uint8_t { REF_INTERN = 0x0, REF_AVDD = 0x3 };

  void begin() {
    pinMode(hw::PIN_ADS_CS, OUTPUT);
    digitalWrite(hw::PIN_ADS_CS, HIGH);
    pinMode(hw::PIN_ADS_DRDY, INPUT_PULLUP);
    befehl(0x06);            // RESET
    delayMicroseconds(100);
  }

  // Eine Wandlung im Single-Shot-Modus. gainExp: 0..7 -> Verstärkung 1..128.
  // Rückgabe: Spannung in Volt bezogen auf die gewählte Referenz.
  float messe(Mux mux, uint8_t gainExp, Ref ref, bool pgaBypass = false,
              uint8_t rate = 2 /* 0=20 SPS … 6=1000 SPS (Normalmodus) */) {
    uint8_t r0 = (uint8_t)(mux << 4) | (uint8_t)((gainExp & 7) << 1) | (pgaBypass ? 1 : 0);
    uint8_t r1 = (uint8_t)((rate & 7) << 5);             // Normalmodus, Single-Shot
    uint8_t r2 = (uint8_t)(ref << 6) | (1 << 4);         // 50/60-Hz-Unterdrückung bei 20 SPS
    if (rate != 0) r2 = (uint8_t)(ref << 6);              // Filter nur bei 20 SPS zulässig
    uint8_t r3 = 0x00;
    schreibe(r0, r1, r2, r3);
    befehl(0x08);                                         // START/SYNC
    uint32_t t0 = micros();
    while (digitalRead(hw::PIN_ADS_DRDY)) {
      if (micros() - t0 > 100000) return NAN;
    }
    int32_t roh = liesDaten();
    float vref = (ref == REF_INTERN) ? 2.048f : avdd;
    float gain = (float)(1 << (gainExp & 7));
    return (float)roh * vref / (gain * 8388608.0f);
  }

  // Interner Temperatursensor (0,03125 °C/LSB) – dient zur Kupfer-Temperaturkompensation
  float temperatur() {
    schreibe(0x00, 0x02 /* TS=1 */, 0x00, 0x00);
    befehl(0x08);
    uint32_t t0 = micros();
    while (digitalRead(hw::PIN_ADS_DRDY)) if (micros() - t0 > 100000) return NAN;
    int32_t roh = liesDaten() >> 10;   // 14 Bit linksbündig
    return (float)roh * 0.03125f;
  }

  float avdd = 5.0f;   // nur für REF_AVDD-Umrechnung; Isolationsmessung ist ratiometrisch

 private:
  SPISettings spi{4000000, MSBFIRST, SPI_MODE1};

  void befehl(uint8_t c) {
    SPI.beginTransaction(spi);
    digitalWrite(hw::PIN_ADS_CS, LOW);
    SPI.transfer(c);
    digitalWrite(hw::PIN_ADS_CS, HIGH);
    SPI.endTransaction();
  }
  void schreibe(uint8_t r0, uint8_t r1, uint8_t r2, uint8_t r3) {
    SPI.beginTransaction(spi);
    digitalWrite(hw::PIN_ADS_CS, LOW);
    SPI.transfer(0x43);   // WREG ab Register 0, 4 Register
    SPI.transfer(r0); SPI.transfer(r1); SPI.transfer(r2); SPI.transfer(r3);
    digitalWrite(hw::PIN_ADS_CS, HIGH);
    SPI.endTransaction();
  }
  int32_t liesDaten() {
    SPI.beginTransaction(spi);
    digitalWrite(hw::PIN_ADS_CS, LOW);
    SPI.transfer(0x10);   // RDATA
    uint32_t v = (uint32_t)SPI.transfer(0) << 16;
    v |= (uint32_t)SPI.transfer(0) << 8;
    v |= SPI.transfer(0);
    digitalWrite(hw::PIN_ADS_CS, HIGH);
    SPI.endTransaction();
    if (v & 0x800000) v |= 0xFF000000;   // Vorzeichen erweitern
    return (int32_t)v;
  }
};
