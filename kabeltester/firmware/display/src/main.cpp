// Kabeltester – Firmware der Display-Einheit (Waveshare ESP32-S3-Touch-LCD-7)
//
// Aufgaben: Bedienoberfläche, Soll/Ist-Vergleich, Prüfprofile und Protokolle im Flash
// (LittleFS), WLAN-Access-Point mit Weboberfläche für Download/Upload.
// Die Messkarte hängt an Serial1 (Textprotokoll, siehe firmware/messkarte/src/main.cpp).
#include <Arduino.h>
#include <ESP_Panel_Library.h>
#include <LittleFS.h>
#include <WiFi.h>
#include <WebServer.h>
#include <lvgl.h>
#include "lvgl_port_v8.h"
#include "kabel_analyse.h"
#include "ui.h"

// UART zur Messkarte – Stecker "UART" der Waveshare-Platine
constexpr int PIN_MK_RX = 44;
constexpr int PIN_MK_TX = 43;
constexpr uint32_t MK_BAUD = 921600;

constexpr const char* WLAN_NAME = "Kabeltester";
constexpr const char* WLAN_PASS = "kabel1234";   // im Setup ändern!

static WebServer web(80);

// --- Zustand -----------------------------------------------------------------
static kt::Profil profil;              // aktives Prüfprofil
static bool profilGeladen = false;
static kt::Messung messungen[kt::MAX_MESSUNGEN];
static int anzahlMessungen = 0;
static kt::Ergebnis ergebnis;
static int pinAnzahl = 128;
static float tempC = NAN;
static uint32_t zaehlerGut = 0, zaehlerFehler = 0, wackelAnzahl = 0;
static bool mitIsolation = false, serienModus = false;
static float durchgangOhm = 10.0f;

enum class Auftrag { Keiner, Pruefen, Einlernen, Messen, Abgleich, Warten };
static volatile Auftrag auftrag = Auftrag::Keiner;
static char lernName[32];
static uint32_t auftragSeit = 0;

// Serienprüfung: Messkarte zyklisch nach eingestecktem Kabel fragen
enum class Serie { Leer, Erkannt, Geprueft };
static Serie serie = Serie::Leer;
static uint32_t serieZeit = 0;

static void mk(const char* zeile) { Serial1.println(zeile); }

// --- Dateien -----------------------------------------------------------------
static String profilPfad(const char* name) {
  String n = name;
  n.replace("/", "_");
  return "/profile/" + n + ".txt";
}

static void profilListeAnzeigen() {
  String liste;
  File dir = LittleFS.open("/profile");
  for (File f = dir.openNextFile(); f; f = dir.openNextFile()) {
    String n = f.name();
    if (!n.endsWith(".txt")) continue;
    n.remove(n.length() - 4);
    if (liste.length()) liste += "\n";
    liste += n;
  }
  ui::profile(liste.c_str(), profilGeladen ? profil.name : nullptr);
}

static bool profilLaden(const char* name) {
  File f = LittleFS.open(profilPfad(name), "r");
  if (!f) return false;
  String text = f.readString();
  profilGeladen = kt::profilLesen(profil, text.c_str());
  if (profilGeladen) {
    durchgangOhm = profil.durchgangOhm;
    File a = LittleFS.open("/aktiv.txt", "w");
    a.print(name);
  }
  return profilGeladen;
}

static void profilSpeichern() {
  static char buf[16384];
  if (kt::profilSchreiben(profil, buf, sizeof buf) < 0) return;
  File f = LittleFS.open(profilPfad(profil.name), "w");
  f.print(buf);
}

// Protokoll als CSV: lfd. Nr.;Laufzeit s;Profil;Ergebnis;Befunde
static void protokolliere() {
  bool neu = !LittleFS.exists("/protokoll.csv");
  File f = LittleFS.open("/protokoll.csv", "a");
  if (!f) return;
  if (neu) f.println("Nr;Zeit_s;Profil;Ergebnis;Befunde");
  f.printf("%lu;%lu;%s;%s;", (unsigned long)(zaehlerGut + zaehlerFehler),
           (unsigned long)(millis() / 1000), profilGeladen ? profil.name : "-",
           ergebnis.ok ? "GUT" : "FEHLER");
  char pa[8], pb[8], w[24];
  for (int i = 0; i < ergebnis.anzahl; ++i) {
    const kt::Fehler& e = ergebnis.f[i];
    kt::pinName(e.a, pa, sizeof pa); kt::pinName(e.b, pb, sizeof pb);
    kt::ohmText(e.ohm, w, sizeof w);
    f.printf("%s%s %s-%s %s", i ? ", " : "", kt::fehlerText(e.typ), pa, pb, w);
  }
  f.println();
}

// --- Rückrufe der Oberfläche (LVGL-Task) ---------------------------------------
static bool starteScan(Auftrag a) {
  if (auftrag != Auftrag::Keiner) {          // Messkarte ist beschäftigt
    ui::status(ui::Zustand::Warnung, "BITTE WARTEN");
    return false;
  }
  auftrag = a;
  auftragSeit = millis();
  anzahlMessungen = 0;
  mk(mitIsolation ? "SCAN ISO" : "SCAN");
  return true;
}

static void cbPruefen() {
  if (!profilGeladen) { ui::status(ui::Zustand::Warnung, "Kein Profil"); return; }
  if (starteScan(Auftrag::Pruefen)) ui::status(ui::Zustand::Laeuft, "PRUEFE ...");
}
static void cbEinlernen(const char* name) {
  strncpy(lernName, name, sizeof(lernName) - 1);
  if (starteScan(Auftrag::Einlernen)) ui::status(ui::Zustand::Laeuft, "LERNE ...");
}
static void cbMessen(int a, int b) {
  char z[32], na[8], nb[8];
  kt::pinName(a, na, sizeof na); kt::pinName(b, nb, sizeof nb);
  snprintf(z, sizeof z, "R %s %s", na, nb);
  auftrag = Auftrag::Messen;
  auftragSeit = millis();
  mk(z);
}
static void cbWackel(bool start) { wackelAnzahl = 0; mk(start ? "WACKEL START" : "WACKEL STOP"); }
static void cbAbgleich() {
  auftrag = Auftrag::Abgleich;
  auftragSeit = millis();
  ui::info("Nullabgleich laeuft ...");
  mk("KAL NULL");
}
static void cbProfil(const char* n) { profilLaden(n); ui::status(ui::Zustand::Bereit, "BEREIT"); }
static void cbIso(bool an) { mitIsolation = an; }
static void cbSerie(bool an) { serienModus = an; serie = Serie::Leer; }
static void cbDurchgang(float ohm) {
  durchgangOhm = ohm;
  if (profilGeladen) { profil.durchgangOhm = ohm; profilSpeichern(); }
}

// --- Auswertung --------------------------------------------------------------
static void scanFertig() {
  // Isolationswerte als Messungen übernehmen, damit der Vergleich sie als "hochohmig" meldet
  if (auftrag == Auftrag::Einlernen) {
    profil.leeren(lernName, (uint16_t)pinAnzahl);
    profil.durchgangOhm = durchgangOhm;
    kt::lerneProfil(profil, messungen, anzahlMessungen);
    profilGeladen = true;
    profilSpeichern();
    profilListeAnzeigen();
    char t[48];
    snprintf(t, sizeof t, "%u Verb. gelernt", (unsigned)profil.anzahl);
    ui::status(ui::Zustand::Gut, t);
    kt::Ergebnis leer = {};
    leer.ok = true;
    ui::ergebnis(leer, messungen, anzahlMessungen);
    return;
  }
  kt::vergleiche(profil, messungen, anzahlMessungen, ergebnis);
  if (ergebnis.ok) ++zaehlerGut; else ++zaehlerFehler;
  ui::status(ergebnis.ok ? ui::Zustand::Gut : ui::Zustand::Fehler, ergebnis.ok ? "GUT" : "FEHLER");
  ui::ergebnis(ergebnis, messungen, anzahlMessungen);
  ui::zaehler(zaehlerGut, zaehlerFehler);
  mk(ergebnis.ok ? "SIGNAL GUT" : "SIGNAL FEHLER");
  protokolliere();
}

static bool liesPins(char*& rest, int& a, int& b) {
  char* sa = strtok_r(rest, " ", &rest);
  char* sb = strtok_r(rest, " ", &rest);
  a = kt::pinAusName(sa); b = kt::pinAusName(sb);
  return a >= 0 && b >= 0;
}

static void zeileVonMesskarte(char* z) {
  char* rest = nullptr;
  char* cmd = strtok_r(z, " ", &rest);
  if (!cmd) return;
  int a, b;
  if (!strcmp(cmd, "C") && liesPins(rest, a, b)) {
    if (anzahlMessungen < kt::MAX_MESSUNGEN) {
      float r1 = strtof(strtok_r(rest, " ", &rest), nullptr);
      char* s2 = strtok_r(rest, " ", &rest);
      messungen[anzahlMessungen++] = {(uint16_t)a, (uint16_t)b, r1, s2 ? strtof(s2, nullptr) : NAN};
    }
  } else if (!strcmp(cmd, "I") && liesPins(rest, a, b)) {
    float r = strtof(strtok_r(rest, " ", &rest), nullptr);
    if (profilGeladen && r < profil.isolationMinOhm && anzahlMessungen < kt::MAX_MESSUNGEN)
      messungen[anzahlMessungen++] = {(uint16_t)a, (uint16_t)b, r, NAN};
  } else if (!strcmp(cmd, "ENDE")) {
    char* was = strtok_r(rest, " ", &rest);
    if (was && !strcmp(was, "SCAN")) { scanFertig(); auftrag = Auftrag::Keiner; }
    if (was && !strcmp(was, "QSCAN")) {
      int verbunden = atoi(strtok_r(rest, " ", &rest));
      // Serienmodus: Kabel erkannt -> kurz warten (Stecker sitzt) -> prüfen; danach Abziehen abwarten
      if (serie == Serie::Leer && verbunden > 0) { serie = Serie::Erkannt; serieZeit = millis(); }
      else if (serie == Serie::Geprueft && verbunden == 0) { serie = Serie::Leer; mk("SIGNAL AUS");
        ui::status(ui::Zustand::Bereit, "BEREIT"); }
      else if (serie == Serie::Erkannt && verbunden == 0) serie = Serie::Leer;
      if (auftrag == Auftrag::Warten) auftrag = Auftrag::Keiner;
    }
  } else if (!strcmp(cmd, "R") && liesPins(rest, a, b)) {
    kt::Messung m;
    m.a = (uint16_t)a; m.b = (uint16_t)b;
    m.ohm = strtof(strtok_r(rest, " ", &rest), nullptr);
    m.ohmRueck = strtof(strtok_r(rest, " ", &rest), nullptr);
    int bereich = atoi(strtok_r(rest, " ", &rest));
    ui::messwert(m, bereich, tempC);
    auftrag = Auftrag::Keiner;
  } else if (!strcmp(cmd, "W") && liesPins(rest, a, b)) {
    char t[64], na[8], nb[8];
    kt::pinName(a, na, sizeof na); kt::pinName(b, nb, sizeof nb);
    snprintf(t, sizeof t, "%7.1f s  %s - %s  unterbrochen %s us", millis() / 1000.0, na, nb, rest);
    ui::wackelEreignis(t, ++wackelAnzahl);
  } else if (!strcmp(cmd, "V")) {
    char t[48];
    snprintf(t, sizeof t, "Fremdspannung %s", rest);
    ui::status(ui::Zustand::Warnung, "SPANNUNG!");
    ui::info(t);
  } else if (!strcmp(cmd, "ERR")) {
    if (auftrag == Auftrag::Abgleich) ui::info("Nullabgleich fehlgeschlagen: Kurzschlussadapter?");
    else if (auftrag == Auftrag::Pruefen || auftrag == Auftrag::Einlernen)
      ui::status(ui::Zustand::Warnung, "ABBRUCH");
    auftrag = Auftrag::Keiner;
  } else if (!strcmp(cmd, "OK")) {
    if (auftrag == Auftrag::Abgleich) ui::info("Nullabgleich gespeichert");
    if (auftrag == Auftrag::Abgleich) auftrag = Auftrag::Keiner;
  } else if (!strcmp(cmd, "INFO")) {
    char* p = strstr(rest, "pins=");
    if (p) pinAnzahl = atoi(p + 5);
    p = strstr(rest, "temp=");
    if (p) tempC = strtof(p + 5, nullptr);
    char t[160];
    snprintf(t, sizeof t, "Messkarte: %s\nWLAN: %s  http://%s", rest, WLAN_NAME,
             WiFi.softAPIP().toString().c_str());
    ui::info(t);
  } else if (!strcmp(cmd, "ADAPTER")) {
    char* seite = strtok_r(rest, " ", &rest);
    char* steckt = strtok_r(rest, " ", &rest);
    if (seite && steckt) ui::adapter(seite[0], steckt[0] == '1', rest);
  } else if (!strcmp(cmd, "TASTE")) {
    cbPruefen();
  }
}

// --- Weboberfläche -----------------------------------------------------------
static void webStart() {
  web.on("/", [] {
    String h = "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
               "<title>Kabeltester</title><style>body{font-family:sans-serif;max-width:40em;margin:1em auto;"
               "padding:0 1em}</style><h1>Kabeltester</h1>";
    h += "<p>Gut: " + String(zaehlerGut) + " &middot; Fehler: " + String(zaehlerFehler) + "</p>";
    h += "<p><a href=/protokoll.csv>Pr&uuml;fprotokoll (CSV)</a></p><h2>Profile</h2><ul>";
    File dir = LittleFS.open("/profile");
    for (File f = dir.openNextFile(); f; f = dir.openNextFile())
      h += "<li><a href='/profile/" + String(f.name()) + "'>" + String(f.name()) + "</a></li>";
    h += "</ul><h2>Profil hochladen</h2><form method=post action=/upload enctype=multipart/form-data>"
         "<input type=file name=f accept=.txt> <button>Hochladen</button></form>";
    web.send(200, "text/html", h);
  });
  web.on("/protokoll.csv", [] {
    File f = LittleFS.open("/protokoll.csv", "r");
    if (!f) { web.send(404, "text/plain", "leer"); return; }
    web.streamFile(f, "text/csv");
  });
  web.onNotFound([] {
    String p = web.uri();
    if (p.startsWith("/profile/") && LittleFS.exists(p)) {
      File f = LittleFS.open(p, "r");
      web.streamFile(f, "text/plain");
    } else web.send(404, "text/plain", "nicht gefunden");
  });
  static String upload;
  web.on("/upload", HTTP_POST, [] {
    kt::Profil* neu = new kt::Profil;
    bool ok = kt::profilLesen(*neu, upload.c_str());
    if (ok) {
      File f = LittleFS.open(profilPfad(neu->name), "w");
      f.print(upload);
    }
    delete neu;
    upload = "";
    web.send(ok ? 200 : 400, "text/plain", ok ? "Profil gespeichert" : "Ungueltiges Profil");
    profilListeAnzeigen();
  }, [] {
    HTTPUpload& u = web.upload();
    if (u.status == UPLOAD_FILE_START) upload = "";
    else if (u.status == UPLOAD_FILE_WRITE && upload.length() < 20000)
      upload.concat((const char*)u.buf, u.currentSize);
  });
  web.begin();
}

// -----------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  Serial1.begin(MK_BAUD, SERIAL_8N1, PIN_MK_RX, PIN_MK_TX);
  Serial1.setRxBufferSize(8192);

  // Display + Touch (Waveshare-Board-Konfiguration aus ESP32_Display_Panel)
  ESP_Panel* panel = new ESP_Panel();
  panel->init();
  panel->begin();
  lvgl_port_init(panel->getLcd(), panel->getTouch());

  LittleFS.begin(true);
  if (!LittleFS.exists("/profile")) LittleFS.mkdir("/profile");

  WiFi.softAP(WLAN_NAME, WLAN_PASS);
  webStart();

  ui::Rueckrufe r = {cbPruefen, cbEinlernen, cbMessen, cbWackel, cbAbgleich,
                     cbProfil, cbIso, cbSerie, cbDurchgang};
  ui::aufbauen(r, pinAnzahl);

  File a = LittleFS.open("/aktiv.txt", "r");
  if (a) profilLaden(a.readString().c_str());
  profilListeAnzeigen();
  mk("INFO");
}

void loop() {
  static char zeile[128];
  static size_t n = 0;
  while (Serial1.available()) {
    char c = (char)Serial1.read();
    if (c == '\r') continue;
    if (c == '\n') { zeile[n] = 0; if (n) zeileVonMesskarte(zeile); n = 0; }
    else if (n < sizeof(zeile) - 1) zeile[n++] = c;
  }
  web.handleClient();

  // Zeitüberwachung: Messkarte antwortet nicht
  if (auftrag != Auftrag::Keiner && millis() - auftragSeit > 120000) {
    auftrag = Auftrag::Keiner;
    ui::status(ui::Zustand::Warnung, "KEINE ANTWORT");
  }

  // Serienprüfung
  if (serienModus && profilGeladen && auftrag == Auftrag::Keiner) {
    static uint32_t letzteAbfrage = 0;
    if (serie == Serie::Erkannt && millis() - serieZeit > 400) {
      serie = Serie::Geprueft;
      cbPruefen();
    } else if (millis() - letzteAbfrage > 400) {
      letzteAbfrage = millis();
      auftrag = Auftrag::Warten;
      auftragSeit = millis();
      mk("QSCAN");
    }
  }
}
