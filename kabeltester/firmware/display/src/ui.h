// Bedienoberfläche (LVGL 8) – 7-Zoll-Touchdisplay 800×480
#pragma once
#include "kabel_analyse.h"

namespace ui {

enum class Zustand { Bereit, Laeuft, Gut, Fehler, Warnung };

// Rückrufe aus der Oberfläche (laufen im LVGL-Task, dürfen nur kurz sein)
struct Rueckrufe {
  void (*pruefen)();
  void (*einlernen)(const char* name);
  void (*messen)(int a, int b);
  void (*wackel)(bool start);
  void (*nullabgleich)();
  void (*profilWahl)(const char* name);
  void (*isolation)(bool an);
  void (*serienModus)(bool an);
  void (*durchgang)(float ohm);
};

void aufbauen(const Rueckrufe& r, int pinAnzahl);

// Alle folgenden Funktionen sperren LVGL selbst und sind aus loop() aufrufbar.
void status(Zustand z, const char* text);
void ergebnis(const kt::Ergebnis& e, const kt::Messung* m, int n);
void zaehler(uint32_t gut, uint32_t fehl);
void messwert(const kt::Messung& m, int bereich, float tempC);
void wackelEreignis(const char* text, uint32_t anzahl);
void profile(const char* liste, const char* aktiv);   // Namen durch '\n' getrennt
void info(const char* text);
void adapter(char seite, bool steckt, const char* name);

}  // namespace ui
