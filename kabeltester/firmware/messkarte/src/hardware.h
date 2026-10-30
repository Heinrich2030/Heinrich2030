// Pinbelegung und Hardware-Konstanten der Messkarte (siehe docs/hardware.md)
#pragma once
#include <stdint.h>

namespace hw {

// --- SPI0: Schieberegister-Kette (74HC595) und ADS1220 -----------------------
constexpr uint8_t PIN_SPI_SCK   = 18;
constexpr uint8_t PIN_SPI_MOSI  = 19;
constexpr uint8_t PIN_SPI_MISO  = 16;
constexpr uint8_t PIN_ADS_CS    = 17;
constexpr uint8_t PIN_ADS_DRDY  = 20;
constexpr uint8_t PIN_595_LATCH = 21;
constexpr uint8_t PIN_595_OE    = 22;   // low = Ausgänge aktiv (Pull-up -> beim Start alles aus)

// --- Schnellscan: gepufferter LO-Sense-Bus am internen ADC ------------------
constexpr uint8_t PIN_SCAN_ADC  = 26;   // ADC0
constexpr uint8_t PIN_VBUS_ADC  = 27;   // ADC1: Monitor REF5025/2 über OPV-Puffer (Selbsttest)

// --- UART zum Display (ESP32-S3) ------------------------------------------
constexpr uint8_t PIN_UART_TX   = 0;
constexpr uint8_t PIN_UART_RX   = 1;
constexpr uint32_t UART_BAUD    = 921600;

// --- I²C zu den Adapter-EEPROMs (Reihe b der DIN-41612-Leisten) -------------
// Je Seite ein eigener Bus: alle Adapter-EEPROMs (24AA02, SOT-23) haben die feste Adresse 0x50.
constexpr uint8_t PIN_I2C_A_SDA = 12;   // I2C0 -> Kanalkarte A
constexpr uint8_t PIN_I2C_A_SCL = 13;
constexpr uint8_t PIN_I2C_B_SDA = 2;    // I2C1 -> Kanalkarte B
constexpr uint8_t PIN_I2C_B_SCL = 3;
constexpr uint8_t ADAPTER_EEPROM = 0x50;

// --- Bedienung / Signalisierung ---------------------------------------------
constexpr uint8_t PIN_START     = 14;   // Start-Taster / Fußschalter (gegen GND)
constexpr uint8_t PIN_BUZZER    = 15;
constexpr uint8_t PIN_LED_GUT   = 10;   // grüner LED-Streifen über MOSFET
constexpr uint8_t PIN_LED_FEHL  = 11;   // roter LED-Streifen über MOSFET
constexpr uint8_t PIN_ADAPT_A   = 6;    // Adapter steckt in Seite A (Kontakt b32 -> GND)
constexpr uint8_t PIN_ADAPT_B   = 7;
constexpr uint8_t PIN_KARTEN_CD = 8;    // Brücke nach GND = Erweiterungskarten C+D gesteckt

// --- Kanalkarten -------------------------------------------------------------
constexpr int PINS_PRO_KARTE  = 64;     // 4 Blöcke à 16
constexpr int MAX_KARTEN      = 4;      // 2 = Grundausbau (A+B), 4 = Vollausbau (256 Pins)

// --- Schieberegister-Kette (Reihenfolge = zuerst geschobenes Byte zuletzt) ---
// Byte 0: Adressen  [3:0] HI-Kanal, [7:4] LO-Kanal (gemeinsam für Force+Sense)
// Byte 1: Modus-Bits des Mess-Frontends
// Byte 2+2k: Force-Enables Karte k  [3:0] HI-Block 0..3, [7:4] LO-Block 0..3 (ADG1606, aktiv high)
// Byte 3+2k: Sense-Enables Karte k  gleiche Bitlage (CD74HCT4067, aktiv low -> Firmware invertiert)
constexpr uint8_t MODUS_HI_QUELLE   = 1 << 0;  // HI-Force -> 2,500-V-Quelle (REF5025 + Puffer)
constexpr uint8_t MODUS_LO_SENKE    = 1 << 1;  // LO-Force -> Präzisions-Stromsenke
constexpr uint8_t MODUS_SHUNT_MASK  = 3 << 2;  // Shunt-Auswahl im Regelkreis (ADG1404)
constexpr uint8_t MODUS_SCAN_PU     = 1 << 4;  // HI-Force -> 3,3 V über 1 kΩ
constexpr uint8_t MODUS_SCAN_PD     = 1 << 5;  // LO-Force -> GND über 10 kΩ
constexpr uint8_t MODUS_ISO         = 1 << 6;  // HI-Force -> AVDD über 1 MΩ (0,1 %)
constexpr uint8_t MODUS_LO_GND      = 1 << 7;  // LO-Force -> GND (niederohmig)

// Strombereiche: Sollspannung 100 mV am Shunt -> I = 0,1 V / R_shunt
struct Bereich { float strom; float shunt; uint8_t bits; };
constexpr Bereich BEREICHE[] = {
  {10e-3f,  10.0f,    0 << 2},   // 0 … ~120 Ω (Spannungsreserve), Auflösung 0,1 mΩ
  {1e-3f,   100.0f,   1 << 2},   // … 2 kΩ
  {100e-6f, 1000.0f,  2 << 2},   // … 20 kΩ
  {10e-6f,  10000.0f, 3 << 2},   // … 200 kΩ
};
constexpr int ANZAHL_BEREICHE = 4;

constexpr float R_ISO        = 1.0e6f;   // Referenz für Isolationsmessung
constexpr float SCAN_SCHWELLE = 0.55f;   // Anteil von 3,3 V: > Schwelle = Verbindung (< ca. 7 kΩ)
constexpr float FREMD_MAX_V   = 0.30f;   // ab hier Fremdspannung -> Abbruch

}  // namespace hw
