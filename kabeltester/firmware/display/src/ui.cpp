// Bedienoberfläche des Kabeltesters (LVGL 8.4)
//
// Hinweis Schrift: Die eingebauten Montserrat-Schriften enthalten keine Umlaute.
// Texte sind daher in ASCII geschrieben ("Pruefen"). Für Umlaute eine eigene Schrift mit
// lv_font_conv erzeugen (Bereich 0x20-0x7F,0xB0,0xC4,0xD6,0xDC,0xDF,0xE4,0xF6,0xFC,0x3A9).
#include <Arduino.h>
#include <lvgl.h>
#include "lvgl_port_v8.h"
#include "ui.h"

namespace ui {
namespace {

Rueckrufe rr;
int pins = 128;

// Prüfen
lv_obj_t *statusBox, *statusLabel, *zaehlerLabel, *profilDd, *tabelle, *adapterLabel;
// Messen
lv_obj_t *ddA, *ddB, *wertLabel, *detailLabel, *querschnittDd, *laengeLabel;
kt::Messung letzteMessung = {0, 0, NAN, NAN};
float letzteTemp = 20.0f;
// Wackeltest
lv_obj_t *wackelLog, *wackelZahl, *wackelBtnLabel;
bool wackelLaeuft = false;
// Einstellungen
lv_obj_t *infoLabel, *durchgangDd;
// Einlernen
lv_obj_t *lernDialog, *lernName;

struct Sperre {
  Sperre() { lvgl_port_lock(-1); }
  ~Sperre() { lvgl_port_unlock(); }
};

lv_obj_t* knopf(lv_obj_t* parent, const char* text, lv_event_cb_t cb, lv_color_t farbe,
                int w, int h, void* data = nullptr) {
  lv_obj_t* b = lv_btn_create(parent);
  lv_obj_set_size(b, w, h);
  lv_obj_set_style_bg_color(b, farbe, 0);
  lv_obj_add_event_cb(b, cb, LV_EVENT_CLICKED, data);
  lv_obj_t* l = lv_label_create(b);
  lv_label_set_text(l, text);
  lv_obj_center(l);
  return b;
}

const char* pinOptionen() {
  static char* opt = nullptr;
  if (opt) return opt;
  opt = (char*)malloc((size_t)pins * 5 + 1);
  size_t o = 0;
  for (int p = 0; p < pins; ++p) {
    char n[8]; kt::pinName(p, n, sizeof n);
    o += (size_t)sprintf(opt + o, p ? "\n%s" : "%s", n);
  }
  return opt;
}

void zeigeLaenge() {
  if (isnan(letzteMessung.ohm) || isinf(letzteMessung.ohm)) { lv_label_set_text(laengeLabel, ""); return; }
  static const float mm2[] = {0.14f, 0.25f, 0.5f, 0.75f, 1.0f, 1.5f, 2.5f, 4.0f, 6.0f,
                              kt::awgZuMm2(24), kt::awgZuMm2(26), kt::awgZuMm2(28)};
  float a = mm2[lv_dropdown_get_selected(querschnittDd)];
  float l = kt::laengeKupfer(letzteMessung.ohm, a, letzteTemp);
  lv_label_set_text_fmt(laengeLabel, "Laenge Kupfer: %.2f m  (bei %.1f C)", (double)l, (double)letzteTemp);
}

// --- Ereignisse --------------------------------------------------------------
void evPruefen(lv_event_t*) { if (rr.pruefen) rr.pruefen(); }
void evLernenOeffnen(lv_event_t*) { lv_obj_clear_flag(lernDialog, LV_OBJ_FLAG_HIDDEN); }
void evLernenAbbruch(lv_event_t*) { lv_obj_add_flag(lernDialog, LV_OBJ_FLAG_HIDDEN); }
void evLernenOk(lv_event_t*) {
  const char* name = lv_textarea_get_text(lernName);
  if (name && *name && rr.einlernen) rr.einlernen(name);
  lv_obj_add_flag(lernDialog, LV_OBJ_FLAG_HIDDEN);
}
void evProfil(lv_event_t*) {
  char n[40];
  lv_dropdown_get_selected_str(profilDd, n, sizeof n);
  if (rr.profilWahl) rr.profilWahl(n);
}
void evMessen(lv_event_t*) {
  int a = (int)lv_dropdown_get_selected(ddA), b = (int)lv_dropdown_get_selected(ddB);
  if (a == b) { lv_label_set_text(detailLabel, "Bitte zwei verschiedene Pins waehlen"); return; }
  lv_label_set_text(wertLabel, "...");
  if (rr.messen) rr.messen(a, b);
}
void evQuerschnitt(lv_event_t*) { zeigeLaenge(); }
void evWackel(lv_event_t*) {
  wackelLaeuft = !wackelLaeuft;
  lv_label_set_text(wackelBtnLabel, wackelLaeuft ? LV_SYMBOL_STOP " Stopp" : LV_SYMBOL_PLAY " Start");
  if (wackelLaeuft) lv_textarea_set_text(wackelLog, "");
  if (rr.wackel) rr.wackel(wackelLaeuft);
}
void evNull(lv_event_t*) { if (rr.nullabgleich) rr.nullabgleich(); }
void evIso(lv_event_t* e) {
  if (rr.isolation) rr.isolation(lv_obj_has_state(lv_event_get_target(e), LV_STATE_CHECKED));
}
void evSerie(lv_event_t* e) {
  if (rr.serienModus) rr.serienModus(lv_obj_has_state(lv_event_get_target(e), LV_STATE_CHECKED));
}
void evDurchgang(lv_event_t*) {
  static const float werte[] = {1.0f, 2.0f, 5.0f, 10.0f, 50.0f, 100.0f};
  if (rr.durchgang) rr.durchgang(werte[lv_dropdown_get_selected(durchgangDd)]);
}
void evTastatur(lv_event_t* e) {
  lv_obj_t* kb = (lv_obj_t*)lv_event_get_user_data(e);
  lv_keyboard_set_textarea(kb, lv_event_get_target(e));
}

// --- Seiten ------------------------------------------------------------------
void seitePruefen(lv_obj_t* tab) {
  lv_obj_set_flex_flow(tab, LV_FLEX_FLOW_ROW);
  lv_obj_set_style_pad_all(tab, 8, 0);

  lv_obj_t* links = lv_obj_create(tab);
  lv_obj_set_size(links, 320, LV_PCT(100));
  lv_obj_set_flex_flow(links, LV_FLEX_FLOW_COLUMN);
  lv_obj_set_style_pad_row(links, 8, 0);
  lv_obj_clear_flag(links, LV_OBJ_FLAG_SCROLLABLE);

  profilDd = lv_dropdown_create(links);
  lv_obj_set_width(profilDd, LV_PCT(100));
  lv_dropdown_set_options(profilDd, "(kein Profil)");
  lv_obj_add_event_cb(profilDd, evProfil, LV_EVENT_VALUE_CHANGED, nullptr);

  statusBox = lv_obj_create(links);
  lv_obj_set_size(statusBox, LV_PCT(100), 130);
  lv_obj_set_style_bg_color(statusBox, lv_palette_darken(LV_PALETTE_GREY, 3), 0);
  lv_obj_clear_flag(statusBox, LV_OBJ_FLAG_SCROLLABLE);
  statusLabel = lv_label_create(statusBox);
  lv_obj_set_style_text_font(statusLabel, &lv_font_montserrat_48, 0);
  lv_label_set_text(statusLabel, "BEREIT");
  lv_obj_center(statusLabel);

  zaehlerLabel = lv_label_create(links);
  lv_label_set_text(zaehlerLabel, "Gut: 0   Fehler: 0");

  lv_obj_t* reihe = lv_obj_create(links);
  lv_obj_set_size(reihe, LV_PCT(100), 80);
  lv_obj_set_style_pad_all(reihe, 0, 0);
  lv_obj_set_style_border_width(reihe, 0, 0);
  lv_obj_set_style_bg_opa(reihe, LV_OPA_TRANSP, 0);
  lv_obj_set_flex_flow(reihe, LV_FLEX_FLOW_ROW);
  lv_obj_set_flex_align(reihe, LV_FLEX_ALIGN_SPACE_BETWEEN, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
  lv_obj_t* b = knopf(reihe, LV_SYMBOL_PLAY " PRUEFEN", evPruefen, lv_palette_main(LV_PALETTE_BLUE), 180, 70);
  lv_obj_set_style_text_font(lv_obj_get_child(b, 0), &lv_font_montserrat_28, 0);
  knopf(reihe, "Einlernen", evLernenOeffnen, lv_palette_darken(LV_PALETTE_GREY, 1), 110, 70);

  adapterLabel = lv_label_create(links);
  lv_obj_set_style_text_font(adapterLabel, &lv_font_montserrat_14, 0);
  lv_label_set_text(adapterLabel, "Adapter A: -   B: -");

  tabelle = lv_table_create(tab);
  lv_obj_set_size(tabelle, 440, LV_PCT(100));
  lv_table_set_col_cnt(tabelle, 3);
  lv_table_set_col_width(tabelle, 0, 170);
  lv_table_set_col_width(tabelle, 1, 120);
  lv_table_set_col_width(tabelle, 2, 130);
  lv_table_set_cell_value(tabelle, 0, 0, "Befund");
  lv_table_set_cell_value(tabelle, 0, 1, "Pins");
  lv_table_set_cell_value(tabelle, 0, 2, "Wert");
}

void seiteMessen(lv_obj_t* tab) {
  lv_obj_set_flex_flow(tab, LV_FLEX_FLOW_COLUMN);
  lv_obj_set_style_pad_row(tab, 12, 0);

  lv_obj_t* reihe = lv_obj_create(tab);
  lv_obj_set_size(reihe, LV_PCT(100), 80);
  lv_obj_set_flex_flow(reihe, LV_FLEX_FLOW_ROW);
  lv_obj_set_flex_align(reihe, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
  lv_obj_clear_flag(reihe, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_t* l = lv_label_create(reihe); lv_label_set_text(l, "Von");
  ddA = lv_dropdown_create(reihe); lv_dropdown_set_options(ddA, pinOptionen()); lv_obj_set_width(ddA, 110);
  l = lv_label_create(reihe); lv_label_set_text(l, "nach");
  ddB = lv_dropdown_create(reihe); lv_dropdown_set_options(ddB, pinOptionen()); lv_obj_set_width(ddB, 110);
  lv_dropdown_set_selected(ddB, (uint16_t)(kt::PINS_PRO_SEITE < pins ? kt::PINS_PRO_SEITE : 1));
  knopf(reihe, LV_SYMBOL_REFRESH " Messen", evMessen, lv_palette_main(LV_PALETTE_BLUE), 170, 56);

  wertLabel = lv_label_create(tab);
  lv_obj_set_style_text_font(wertLabel, &lv_font_montserrat_48, 0);
  lv_label_set_text(wertLabel, "- Ohm");
  detailLabel = lv_label_create(tab);
  lv_label_set_text(detailLabel, "4-Leiter-Messung mit Stromumkehr, automatische Bereichswahl");

  lv_obj_t* r2 = lv_obj_create(tab);
  lv_obj_set_size(r2, LV_PCT(100), 80);
  lv_obj_set_flex_flow(r2, LV_FLEX_FLOW_ROW);
  lv_obj_set_flex_align(r2, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
  lv_obj_clear_flag(r2, LV_OBJ_FLAG_SCROLLABLE);
  l = lv_label_create(r2); lv_label_set_text(l, "Querschnitt");
  querschnittDd = lv_dropdown_create(r2);
  lv_dropdown_set_options(querschnittDd,
      "0,14 mm2\n0,25 mm2\n0,5 mm2\n0,75 mm2\n1,0 mm2\n1,5 mm2\n2,5 mm2\n4 mm2\n6 mm2\nAWG 24\nAWG 26\nAWG 28");
  lv_dropdown_set_selected(querschnittDd, 5);
  lv_obj_add_event_cb(querschnittDd, evQuerschnitt, LV_EVENT_VALUE_CHANGED, nullptr);
  laengeLabel = lv_label_create(r2);
  lv_label_set_text(laengeLabel, "");
}

void seiteWackel(lv_obj_t* tab) {
  lv_obj_set_flex_flow(tab, LV_FLEX_FLOW_COLUMN);
  lv_obj_t* l = lv_label_create(tab);
  lv_label_set_long_mode(l, LV_LABEL_LONG_WRAP);
  lv_obj_set_width(l, LV_PCT(100));
  lv_label_set_text(l, "Erst PRUEFEN, dann Start. Kabel und Stecker bewegen: jede Unterbrechung "
                       "ab wenigen Mikrosekunden wird mit Dauer gemeldet und piept.");
  lv_obj_t* reihe = lv_obj_create(tab);
  lv_obj_set_size(reihe, LV_PCT(100), 80);
  lv_obj_set_flex_flow(reihe, LV_FLEX_FLOW_ROW);
  lv_obj_set_flex_align(reihe, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
  lv_obj_clear_flag(reihe, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_t* b = knopf(reihe, LV_SYMBOL_PLAY " Start", evWackel, lv_palette_main(LV_PALETTE_ORANGE), 170, 56);
  wackelBtnLabel = lv_obj_get_child(b, 0);
  wackelZahl = lv_label_create(reihe);
  lv_obj_set_style_text_font(wackelZahl, &lv_font_montserrat_28, 0);
  lv_label_set_text(wackelZahl, "0 Aussetzer");
  wackelLog = lv_textarea_create(tab);
  lv_obj_set_size(wackelLog, LV_PCT(100), 220);
  lv_textarea_set_text(wackelLog, "");
  lv_obj_clear_flag(wackelLog, LV_OBJ_FLAG_CLICK_FOCUSABLE);
}

void seiteSetup(lv_obj_t* tab) {
  lv_obj_set_flex_flow(tab, LV_FLEX_FLOW_COLUMN);
  lv_obj_set_style_pad_row(tab, 10, 0);
  auto zeile = [&](const char* text) {
    lv_obj_t* r = lv_obj_create(tab);
    lv_obj_set_size(r, LV_PCT(100), 64);
    lv_obj_set_flex_flow(r, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(r, LV_FLEX_ALIGN_SPACE_BETWEEN, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_clear_flag(r, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_t* l = lv_label_create(r); lv_label_set_text(l, text);
    return r;
  };
  lv_obj_t* sw = lv_switch_create(zeile("Isolationspruefung (5 V, langsamer)"));
  lv_obj_add_event_cb(sw, evIso, LV_EVENT_VALUE_CHANGED, nullptr);
  sw = lv_switch_create(zeile("Serienpruefung: automatisch bei eingestecktem Kabel"));
  lv_obj_add_event_cb(sw, evSerie, LV_EVENT_VALUE_CHANGED, nullptr);
  durchgangDd = lv_dropdown_create(zeile("Durchgangsgrenze"));
  lv_dropdown_set_options(durchgangDd, "1 Ohm\n2 Ohm\n5 Ohm\n10 Ohm\n50 Ohm\n100 Ohm");
  lv_dropdown_set_selected(durchgangDd, 3);
  lv_obj_add_event_cb(durchgangDd, evDurchgang, LV_EVENT_VALUE_CHANGED, nullptr);
  knopf(zeile("Nullabgleich (Kurzschlussadapter stecken)"), "Abgleich", evNull,
        lv_palette_main(LV_PALETTE_TEAL), 140, 48);
  infoLabel = lv_label_create(tab);
  lv_obj_set_style_text_font(infoLabel, &lv_font_montserrat_14, 0);
  lv_label_set_text(infoLabel, "Messkarte: warte ...");
}

void dialogEinlernen() {
  lernDialog = lv_obj_create(lv_layer_top());
  lv_obj_set_size(lernDialog, 800, 480);
  lv_obj_set_style_bg_color(lernDialog, lv_color_black(), 0);
  lv_obj_set_style_bg_opa(lernDialog, LV_OPA_90, 0);
  lv_obj_t* l = lv_label_create(lernDialog);
  lv_label_set_text(l, "Referenzkabel (Golden Sample) einstecken und Namen eingeben:");
  lv_obj_align(l, LV_ALIGN_TOP_LEFT, 10, 10);
  lernName = lv_textarea_create(lernDialog);
  lv_textarea_set_one_line(lernName, true);
  lv_textarea_set_max_length(lernName, 30);
  lv_obj_set_width(lernName, 480);
  lv_obj_align(lernName, LV_ALIGN_TOP_LEFT, 10, 50);
  knopf(lernDialog, "Einlernen", evLernenOk, lv_palette_main(LV_PALETTE_GREEN), 130, 48);
  lv_obj_align(lv_obj_get_child(lernDialog, -1), LV_ALIGN_TOP_RIGHT, -150, 45);
  knopf(lernDialog, "Abbruch", evLernenAbbruch, lv_palette_main(LV_PALETTE_RED), 120, 48);
  lv_obj_align(lv_obj_get_child(lernDialog, -1), LV_ALIGN_TOP_RIGHT, -10, 45);
  lv_obj_t* kb = lv_keyboard_create(lernDialog);
  lv_keyboard_set_textarea(kb, lernName);
  lv_obj_add_event_cb(lernName, evTastatur, LV_EVENT_FOCUSED, kb);
  lv_obj_add_flag(lernDialog, LV_OBJ_FLAG_HIDDEN);
}

}  // namespace

// --- öffentliche Funktionen --------------------------------------------------
void aufbauen(const Rueckrufe& r, int pinAnzahl) {
  Sperre s;
  rr = r;
  pins = pinAnzahl;
  lv_obj_t* tv = lv_tabview_create(lv_scr_act(), LV_DIR_TOP, 56);
  seitePruefen(lv_tabview_add_tab(tv, LV_SYMBOL_OK " Pruefen"));
  seiteMessen(lv_tabview_add_tab(tv, LV_SYMBOL_CHARGE " Messen"));
  seiteWackel(lv_tabview_add_tab(tv, LV_SYMBOL_SHUFFLE " Wackeltest"));
  seiteSetup(lv_tabview_add_tab(tv, LV_SYMBOL_SETTINGS " Setup"));
  dialogEinlernen();
}

void status(Zustand z, const char* text) {
  Sperre s;
  lv_color_t c;
  switch (z) {
    case Zustand::Gut:     c = lv_palette_main(LV_PALETTE_GREEN); break;
    case Zustand::Fehler:  c = lv_palette_main(LV_PALETTE_RED); break;
    case Zustand::Laeuft:  c = lv_palette_main(LV_PALETTE_BLUE); break;
    case Zustand::Warnung: c = lv_palette_main(LV_PALETTE_ORANGE); break;
    default:               c = lv_palette_darken(LV_PALETTE_GREY, 3); break;
  }
  lv_obj_set_style_bg_color(statusBox, c, 0);
  lv_label_set_text(statusLabel, text);
  lv_obj_set_style_text_font(statusLabel, strlen(text) > 9 ? &lv_font_montserrat_28 : &lv_font_montserrat_48, 0);
  lv_obj_center(statusLabel);
}

void ergebnis(const kt::Ergebnis& e, const kt::Messung* m, int n) {
  Sperre s;
  char pa[8], pb[8], paar[20], wert[24];
  int zeile = 1;
  // Zuerst die Fehler, danach alle gemessenen Verbindungen (grau) zur Übersicht
  lv_table_set_row_cnt(tabelle, (uint16_t)(1 + e.anzahl + n));
  for (int i = 0; i < e.anzahl; ++i, ++zeile) {
    const kt::Fehler& f = e.f[i];
    kt::pinName(f.a, pa, sizeof pa); kt::pinName(f.b, pb, sizeof pb);
    snprintf(paar, sizeof paar, "%s - %s", pa, pb);
    kt::ohmText(f.ohm, wert, sizeof wert);
    lv_table_set_cell_value_fmt(tabelle, (uint16_t)zeile, 0, LV_SYMBOL_WARNING " %s", kt::fehlerText(f.typ));
    lv_table_set_cell_value(tabelle, (uint16_t)zeile, 1, paar);
    lv_table_set_cell_value(tabelle, (uint16_t)zeile, 2, wert);
  }
  for (int i = 0; i < n; ++i, ++zeile) {
    kt::pinName(m[i].a, pa, sizeof pa); kt::pinName(m[i].b, pb, sizeof pb);
    snprintf(paar, sizeof paar, "%s - %s", pa, pb);
    kt::ohmText(m[i].ohm, wert, sizeof wert);
    lv_table_set_cell_value(tabelle, (uint16_t)zeile, 0, "Verbindung");
    lv_table_set_cell_value(tabelle, (uint16_t)zeile, 1, paar);
    lv_table_set_cell_value(tabelle, (uint16_t)zeile, 2, wert);
  }
  lv_obj_scroll_to_y(tabelle, 0, LV_ANIM_OFF);
}

void zaehler(uint32_t gut, uint32_t fehl) {
  Sperre s;
  uint32_t ges = gut + fehl;
  lv_label_set_text_fmt(zaehlerLabel, "Gut: %lu   Fehler: %lu   Ausbeute: %lu %%",
                        (unsigned long)gut, (unsigned long)fehl,
                        (unsigned long)(ges ? gut * 100 / ges : 0));
}

void messwert(const kt::Messung& m, int bereich, float tempC) {
  Sperre s;
  letzteMessung = m;
  if (!isnan(tempC)) letzteTemp = tempC;
  char t[24], t2[24];
  kt::ohmText(m.ohm, t, sizeof t);
  lv_label_set_text(wertLabel, t);
  static const char* strom[] = {"10 mA", "1 mA", "100 uA", "10 uA"};
  if (kt::istDiode(m)) {
    char an[8]; kt::pinName(m.a, an, sizeof an);
    lv_label_set_text_fmt(detailLabel, "Diode erkannt, Anode an %s (Rueckrichtung %s)", an,
                          isinf(m.ohmRueck) ? "sperrt" : (kt::ohmText(m.ohmRueck, t2, sizeof t2), t2));
  } else {
    kt::ohmText(m.ohmRueck, t2, sizeof t2);
    lv_label_set_text_fmt(detailLabel, "Messstrom %s, Rueckrichtung %s",
                          strom[bereich & 3], t2);
  }
  zeigeLaenge();
}

void wackelEreignis(const char* text, uint32_t anzahl) {
  Sperre s;
  lv_textarea_add_text(wackelLog, text);
  lv_textarea_add_text(wackelLog, "\n");
  lv_label_set_text_fmt(wackelZahl, "%lu Aussetzer", (unsigned long)anzahl);
}

void profile(const char* liste, const char* aktiv) {
  Sperre s;
  lv_dropdown_set_options(profilDd, liste && *liste ? liste : "(kein Profil)");
  if (aktiv) {
    int idx = lv_dropdown_get_option_index(profilDd, aktiv);
    if (idx >= 0) lv_dropdown_set_selected(profilDd, (uint16_t)idx);
  }
}

void info(const char* text) {
  Sperre s;
  lv_label_set_text(infoLabel, text);
}

void adapter(char seite, bool steckt, const char* name) {
  Sperre s;
  static char a[34] = "-", b[34] = "-";
  char* ziel = seite == 'A' ? a : b;
  snprintf(ziel, 34, "%s", steckt ? (name && *name ? name : "unbekannt") : "-");
  lv_label_set_text_fmt(adapterLabel, "Adapter A: %s   B: %s", a, b);
}

}  // namespace ui
