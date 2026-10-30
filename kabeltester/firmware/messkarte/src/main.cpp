// Kabeltester – Firmware der Messkarte (Raspberry Pi Pico 2 / RP2350)
//
// Textprotokoll (eine Zeile pro Nachricht, '\n'), gleich über UART (Display) und USB (PC).
// Pins werden als Namen übertragen: A1 … A64, B1 … B64, C1 …, D64.
//
//   INFO                      -> INFO pins=128 karten=2 fw=1.0 temp=23.4 adapterA=1 adapterB=0
//   SCAN [ISO]                -> V <pin> <volt>   (nur bei Fremdspannung, danach ERR)
//                                C <a> <b> <ohm> <ohmRueck>   je Verbindung (Spannbaum je Netz)
//                                I <a> <b> <ohm>              Isolation zwischen Netzen (mit ISO)
//                                ENDE SCAN <verbindungen> <ms>
//   QSCAN                     -> ENDE QSCAN <verbundene_pins> <ms>   (nur Schnellscan)
//   R <a> <b>                 -> R <a> <b> <ohm> <ohmRueck> <bereich>   (Präzisionsmessung)
//   ISO <a> <b>               -> ISO <a> <b> <ohm>
//   WACKEL START | STOP       -> W <a> <b> <dauer_us>   bei jeder Unterbrechung (Wackeltest)
//   KAL NULL | LOESCHEN       -> OK KAL <seiten> / ERR …   (Nullabgleich je Seite)
//   SIGNAL GUT | FEHLER | AUS -> OK
//   Ereignisse:  TASTE  ·  ADAPTER <A|B> <0|1> <name>
#include <Arduino.h>
#include <SPI.h>
#include <Wire.h>
#include "hardware.h"
#include "messung.h"
#include "kabel_analyse.h"

static Messgeraet geraet;
static int karten = 2;

// Wackeltest: Liste der gefundenen Verbindungen, die zyklisch überwacht werden
static bool wackelAktiv = false;
static uint16_t wackelA[kt::MAX_MESSUNGEN], wackelB[kt::MAX_MESSUNGEN];
static uint32_t wackelSeit[kt::MAX_MESSUNGEN];
static int wackelN = 0;

// Ausgabe an beide Schnittstellen
static void sende(const char* zeile) {
  Serial1.println(zeile);
  if (Serial) Serial.println(zeile);
}

static void pinStr(int p, char* b) { kt::pinName(p, b, 8); }

static void sendeOhm(char* buf, size_t len, const char* prefix, int a, int b, float r1, float r2) {
  char na[8], nb[8];
  pinStr(a, na); pinStr(b, nb);
  snprintf(buf, len, "%s %s %s %.7g %.7g", prefix, na, nb, (double)r1, (double)r2);
  sende(buf);
}

// ---------------------------------------------------------------------------
// Adapter-Erkennung: EEPROM 24AA02 auf jedem Adapter, Adresse 0x50, je Seite ein eigener I²C-Bus.
// Inhalt: ASCII-Name, mit 0 abgeschlossen (z. B. "RJ45 8P8C", "D-Sub 25").
// ---------------------------------------------------------------------------
static void adapterName(TwoWire& bus, char* name, size_t len) {
  name[0] = 0;
  bus.beginTransmission(hw::ADAPTER_EEPROM);
  bus.write((uint8_t)0);
  if (bus.endTransmission() != 0) return;
  size_t n = bus.requestFrom(hw::ADAPTER_EEPROM, (uint8_t)(len - 1));
  size_t i = 0;
  while (bus.available() && i < n) {
    char c = (char)bus.read();
    if (c == 0 || c == (char)0xFF) break;
    name[i++] = c;
  }
  name[i] = 0;
}

static bool adapterSteckt[2] = {false, false};
static void pruefeAdapter(bool immerMelden) {
  const uint8_t pin[2] = {hw::PIN_ADAPT_A, hw::PIN_ADAPT_B};
  for (int s = 0; s < 2; ++s) {
    bool da = digitalRead(pin[s]) == LOW;
    if (da == adapterSteckt[s] && !immerMelden) continue;
    adapterSteckt[s] = da;
    char name[33] = "";
    if (da) adapterName(s == 0 ? Wire : Wire1, name, sizeof name);
    char buf[64];
    snprintf(buf, sizeof buf, "ADAPTER %c %d %s", 'A' + s, da ? 1 : 0, name);
    sende(buf);
  }
}

// ---------------------------------------------------------------------------
// Befehle
// ---------------------------------------------------------------------------
static void befehlInfo() {
  char buf[128];
  snprintf(buf, sizeof buf, "INFO pins=%d karten=%d fw=1.0 temp=%.1f adapterA=%d adapterB=%d",
           geraet.pins(), karten, (double)geraet.temperatur(), adapterSteckt[0], adapterSteckt[1]);
  sende(buf);
}

static void befehlScan(bool mitIso) {
  char buf[96];
  uint32_t t0 = millis();
  float volt = 0;
  int p = geraet.fremdspannung(volt);
  if (p >= 0) {
    char n[8]; pinStr(p, n);
    snprintf(buf, sizeof buf, "V %s %.2f", n, (double)volt);
    sende(buf);
    sende("ERR fremdspannung");
    return;
  }

  static kt::Netze netze;
  uint32_t scanMs;
  geraet.schnellscan(netze, scanMs);

  // Präzise Messung entlang eines Spannbaums: jeder Pin gegen den kleinsten Pin seines Netzes
  int anzahl = 0;
  wackelN = 0;
  for (int q = 0; q < geraet.pins(); ++q) {
    int w = netze.wurzel(q);
    if (w == q) continue;
    kt::Messung m = geraet.widerstand(w, q);
    sendeOhm(buf, sizeof buf, "C", m.a, m.b, m.ohm, m.ohmRueck);
    ++anzahl;
    if (wackelN < kt::MAX_MESSUNGEN) { wackelA[wackelN] = (uint16_t)w; wackelB[wackelN] = (uint16_t)q; ++wackelN; }
  }

  if (mitIso) {
    // Isolation zwischen allen Netzen (je ein Vertreter-Pin), nur genutzte Netze
    static int16_t vertreter[kt::MAX_PINS];
    static bool genutzt[kt::MAX_PINS];
    memset(genutzt, 0, sizeof genutzt);
    for (int q = 0; q < geraet.pins(); ++q) if (netze.wurzel(q) != q) genutzt[netze.wurzel(q)] = true;
    int nv = 0;
    for (int q = 0; q < geraet.pins(); ++q) if (genutzt[q]) vertreter[nv++] = (int16_t)q;
    for (int i = 0; i < nv; ++i) {
      for (int j = i + 1; j < nv; ++j) {
        float r = geraet.isolation(vertreter[i], vertreter[j]);
        char na[8], nb[8]; pinStr(vertreter[i], na); pinStr(vertreter[j], nb);
        snprintf(buf, sizeof buf, "I %s %s %.4g", na, nb, (double)r);
        sende(buf);
      }
    }
  }
  snprintf(buf, sizeof buf, "ENDE SCAN %d %lu", anzahl, (unsigned long)(millis() - t0));
  sende(buf);
}

static bool zweiPins(char* args, int& a, int& b) {
  char* s1 = strtok(args, " ");
  char* s2 = strtok(nullptr, " ");
  a = kt::pinAusName(s1);
  b = kt::pinAusName(s2);
  return a >= 0 && b >= 0 && a != b && a < geraet.pins() && b < geraet.pins();
}

static void signal(const char* art) {
  bool gut = !strcmp(art, "GUT"), fehl = !strcmp(art, "FEHLER");
  digitalWrite(hw::PIN_LED_GUT, gut);
  digitalWrite(hw::PIN_LED_FEHL, fehl);
  if (gut) tone(hw::PIN_BUZZER, 2400, 120);
  if (fehl) tone(hw::PIN_BUZZER, 600, 600);
}

static void verarbeite(char* zeile) {
  char* cmd = strtok(zeile, " ");
  if (!cmd) return;
  char* rest = strtok(nullptr, "");
  char buf[96];
  if (!strcmp(cmd, "INFO")) befehlInfo();
  else if (!strcmp(cmd, "SCAN")) befehlScan(rest && !strcmp(rest, "ISO"));
  else if (!strcmp(cmd, "QSCAN")) {
    static kt::Netze netze;
    uint32_t ms;
    geraet.schnellscan(netze, ms);
    int verbunden = 0;
    for (int q = 0; q < geraet.pins(); ++q) if (netze.wurzel(q) != q) ++verbunden;
    snprintf(buf, sizeof buf, "ENDE QSCAN %d %lu", verbunden, (unsigned long)ms);
    sende(buf);
  }
  else if (!strcmp(cmd, "R") || !strcmp(cmd, "ISO")) {
    int a, b;
    if (!rest || !zweiPins(rest, a, b)) { sende("ERR pins"); return; }
    if (cmd[0] == 'R') {
      int bereich = 0;
      kt::Messung m = geraet.widerstand(a, b, &bereich, true);
      char na[8], nb[8]; pinStr(m.a, na); pinStr(m.b, nb);
      snprintf(buf, sizeof buf, "R %s %s %.7g %.7g %d", na, nb, (double)m.ohm, (double)m.ohmRueck, bereich);
      sende(buf);
    } else {
      char na[8], nb[8]; pinStr(a, na); pinStr(b, nb);
      snprintf(buf, sizeof buf, "ISO %s %s %.4g", na, nb, (double)geraet.isolation(a, b, 20));
      sende(buf);
    }
  }
  else if (!strcmp(cmd, "WACKEL")) {
    wackelAktiv = rest && !strcmp(rest, "START") && wackelN > 0;
    for (int i = 0; i < wackelN; ++i) wackelSeit[i] = 0;
    sende(wackelAktiv ? "OK WACKEL" : (rest && !strcmp(rest, "START") ? "ERR erst SCAN" : "OK"));
    if (!wackelAktiv) geraet.matrix.alles_aus();
  }
  else if (!strcmp(cmd, "KAL")) {
    if (rest && !strcmp(rest, "NULL")) {
      int seiten = geraet.nullabgleich();
      if (seiten) { snprintf(buf, sizeof buf, "OK KAL %d", seiten); sende(buf); }
      else sende("ERR kurzschlussadapter");
    }
    else if (rest && !strcmp(rest, "LOESCHEN")) { geraet.loescheKalibrierung(); sende("OK KAL"); }
    else sende("ERR kal");
  }
  else if (!strcmp(cmd, "SIGNAL")) { signal(rest ? rest : "AUS"); sende("OK"); }
  else sende("ERR unbekannt");
}

// Zeilenpuffer je Schnittstelle
struct Leser {
  char buf[96];
  size_t n = 0;
  void lies(Stream& s) {
    while (s.available()) {
      char c = (char)s.read();
      if (c == '\r') continue;
      if (c == '\n') { buf[n] = 0; if (n) verarbeite(buf); n = 0; }
      else if (n < sizeof(buf) - 1) buf[n++] = c;
    }
  }
};
static Leser uartLeser, usbLeser;

// Wackeltest: überwacht nur die bekannten Verbindungen -> mehrere kHz Abtastrate,
// erkennt Unterbrechungen ab wenigen Mikrosekunden.
static void wackelSchritt() {
  static int i = 0;
  if (!wackelAktiv || wackelN == 0) return;
  bool ok = geraet.verbunden(wackelA[i], wackelB[i]);
  uint32_t jetzt = micros();
  if (!ok && wackelSeit[i] == 0) wackelSeit[i] = jetzt | 1;
  if (ok && wackelSeit[i] != 0) {
    char buf[48], na[8], nb[8];
    pinStr(wackelA[i], na); pinStr(wackelB[i], nb);
    snprintf(buf, sizeof buf, "W %s %s %lu", na, nb, (unsigned long)(jetzt - wackelSeit[i]));
    sende(buf);
    tone(hw::PIN_BUZZER, 1800, 30);
    wackelSeit[i] = 0;
  }
  i = (i + 1) % wackelN;
}

void setup() {
  Serial.begin(115200);
  Serial1.setTX(hw::PIN_UART_TX);
  Serial1.setRX(hw::PIN_UART_RX);
  Serial1.begin(hw::UART_BAUD);

  SPI.setSCK(hw::PIN_SPI_SCK);
  SPI.setTX(hw::PIN_SPI_MOSI);
  SPI.setRX(hw::PIN_SPI_MISO);
  SPI.begin();

  Wire.setSDA(hw::PIN_I2C_A_SDA);
  Wire.setSCL(hw::PIN_I2C_A_SCL);
  Wire.begin();
  Wire1.setSDA(hw::PIN_I2C_B_SDA);
  Wire1.setSCL(hw::PIN_I2C_B_SCL);
  Wire1.begin();

  pinMode(hw::PIN_START, INPUT_PULLUP);
  pinMode(hw::PIN_ADAPT_A, INPUT_PULLUP);
  pinMode(hw::PIN_ADAPT_B, INPUT_PULLUP);
  pinMode(hw::PIN_LED_GUT, OUTPUT);
  pinMode(hw::PIN_LED_FEHL, OUTPUT);
  pinMode(hw::PIN_BUZZER, OUTPUT);

  // Erweiterungskarten C/D melden sich über einen Brücken-Pin (low = 4 Karten)
  pinMode(hw::PIN_KARTEN_CD, INPUT_PULLUP);
  karten = digitalRead(hw::PIN_KARTEN_CD) == LOW ? 4 : 2;
  geraet.begin(karten);

  pruefeAdapter(true);
  befehlInfo();
}

void loop() {
  uartLeser.lies(Serial1);
  usbLeser.lies(Serial);
  wackelSchritt();

  // Start-Taster entprellt melden
  static uint32_t letzteTaste = 0;
  static bool war = false;
  bool gedrueckt = digitalRead(hw::PIN_START) == LOW;
  if (gedrueckt && !war && millis() - letzteTaste > 300) { sende("TASTE"); letzteTaste = millis(); }
  war = gedrueckt;

  static uint32_t letzterAdapterCheck = 0;
  if (millis() - letzterAdapterCheck > 250) { letzterAdapterCheck = millis(); pruefeAdapter(false); }
}
