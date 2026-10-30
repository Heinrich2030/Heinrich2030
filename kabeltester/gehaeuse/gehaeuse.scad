// Kabeltester – Pultgehäuse für den 3D-Druck (PETG), parametrisch
//
//   teil = "gehaeuse"  -> Oberschale (Display schräg, Adapterschächte hinten)
//   teil = "boden"     -> Bodenplatte mit Schraubdomen für die Leiterplatten
//   teil = "ansicht"   -> beides zusammen zur Kontrolle
//
// Maße in mm. Display-Maße vor dem Druck am realen Modul nachmessen!
teil = "ansicht";

// --- Hauptmaße -----------------------------------------------------------------
B = 250;            // Breite
T = 200;            // Tiefe
H_vorne = 32;       // Höhe Vorderkante
H_hinten = 88;      // Höhe Rückseite (Adapterdeck)
Y_knick = 135;      // Ende der Schrägfläche (Display), dahinter waagerechtes Deck
wand = 2.4;

// --- Display: Waveshare ESP32-S3-Touch-LCD-7 -------------------------------------
disp_sicht_b = 156;     // sichtbarer Bereich inkl. Rand
disp_sicht_h = 88;
disp_modul_b = 194;     // Glas/Modul außen
disp_modul_h = 112;
disp_x = 12;            // Abstand linker Rand -> Modul
disp_y = 10;            // Abstand Vorderkante (auf der Schräge) -> Modul

// --- Bedienelemente ------------------------------------------------------------
taster_d = 22;          // beleuchteter Start-Taster
led_schlitz = [8, 60];  // Lichtleiter für Gut/Fehler-LED-Streifen

// --- Adapterschächte (DIN 41612 C96, Adapterplatine 1,6 mm + Bauteile) -----------
schacht_l = 104;
schacht_b = 14;
schacht_abstand = 16;
kanal_dom_h = 71.3;   // Kanalkarten-Unterseite: DIN-Federleiste (11,7 mm) endet 1 mm unter dem Deck
mess_dom_h = 8;

// Schraubdome = Befestigungslöcher der KiCad-Platinen (hardware/kicad/generator/layouts.py)
mess_dome = [[7, 72], [117, 42], [7, 16], [119, 16]];
kanal_dome = [for (x0 = [4, 128], p = [[4, 4], [114, 4], [4, 70], [114, 70]]) [x0 + p[0], 194 - p[1]]];
// USB-Öffnungen in der linken Wand: [y, z] Mitte
usb_strom = [40, 11.2];   // USB-C Versorgung (Messkarte)
usb_pico = [87.5, 12.2];  // USB des Pico 2 (Firmware-Update)

$fn = 48;

winkel = atan((H_hinten - H_vorne) / Y_knick);
schraeg_l = sqrt(pow(H_hinten - H_vorne, 2) + pow(Y_knick, 2));

module profil(d = 0) {
  offset(delta = -d)
    polygon([[0, 0], [T, 0], [T, H_hinten], [Y_knick, H_hinten], [0, H_vorne]]);
}

module keil(d = 0, x0 = 0, xl = B) {
  translate([x0, 0, 0]) rotate([90, 0, 90]) linear_extrude(xl) profil(d);
}

// Koordinatensystem auf der Schrägfläche: x nach rechts, y die Schräge hinauf
module auf_schraege() {
  translate([0, 0, H_vorne]) rotate([winkel, 0, 0]) children();
}

module gehaeuse() {
  difference() {
    keil();
    // Innenraum, unten offen
    translate([0, 0, -1]) keil(wand, wand, B - 2 * wand);
    translate([wand, wand, -1]) cube([B - 2 * wand, T - 2 * wand, wand + 1]);

    auf_schraege() {
      // Sichtfenster
      translate([disp_x + (disp_modul_b - disp_sicht_b) / 2,
                 disp_y + (disp_modul_h - disp_sicht_h) / 2, -10])
        cube([disp_sicht_b, disp_sicht_h, 20]);
      // Einlegetasche für das Glas (von innen, 1 mm Restwand am Rand)
      translate([disp_x - 0.3, disp_y - 0.3, -10])
        cube([disp_modul_b + 0.6, disp_modul_h + 0.6, 10 + wand - 1]);
      // Start-Taster rechts neben dem Display
      translate([B - (B - disp_x - disp_modul_b) / 2, disp_y + disp_modul_h * 0.7, -10])
        cylinder(d = taster_d, h = 20);
      // LED-Lichtleiter (Gut/Fehler)
      translate([B - (B - disp_x - disp_modul_b) / 2 - led_schlitz[0] / 2,
                 disp_y + 5, -10])
        cube([led_schlitz[0], led_schlitz[1] * 0.5, 20]);
    }

    // Adapterschächte A (links) und B (rechts) im Deck
    for (i = [0, 1])
      translate([B / 2 + (i == 0 ? -schacht_abstand / 2 - schacht_l : schacht_abstand / 2),
                 Y_knick + (T - Y_knick - schacht_b) / 2, H_hinten - 10])
        cube([schacht_l, schacht_b, 20]);

    // Linke Wand: USB-C (Versorgung) und USB des Pico 2
    for (u = [usb_strom, usb_pico]) translate([-1, u[0] - 5, u[1] - 2.5]) cube([wand + 2, 10, 5]);
    // Vorderseite: 3,5-mm-Klinke für Fußschalter
    translate([B - 25, -1, H_vorne / 2]) rotate([-90, 0, 0]) cylinder(d = 6.5, h = 10);
    // Lüftungsschlitze seitlich
    for (s = [0, 1], k = [0 : 5])
      translate([s * (B - wand) - 1, 120 + k * 10, 15]) cube([wand + 2, 4, 30]);
  }
  // Beschriftung der Schächte
  for (i = [0, 1])
    translate([B / 2 + (i == 0 ? -schacht_abstand / 2 - schacht_l / 2 : schacht_abstand / 2 + schacht_l / 2),
               Y_knick + 4, H_hinten - 0.01])
      linear_extrude(0.6) text(i == 0 ? "A" : "B", size = 6, halign = "center");
}

module boden() {
  difference() {
    union() {
      translate([wand + 0.3, wand + 0.3, 0]) cube([B - 2 * wand - 0.6, T - 2 * wand - 0.6, 2]);
      // Schraubdome Messkarte und Kanalkarten (M2,5 selbstschneidend, Kernloch 2,6 mm)
      for (p = mess_dome) translate([p[0], p[1], 0]) cylinder(d = 7, h = mess_dom_h);
      for (p = kanal_dome) translate([p[0], p[1], 0]) cylinder(d = 9, h = kanal_dom_h);
    }
    for (p = mess_dome) translate([p[0], p[1], -1]) cylinder(d = 2.6, h = 20);
    for (p = kanal_dome) translate([p[0], p[1], -1]) cylinder(d = 2.6, h = kanal_dom_h + 2);
  }
  // Gummifüße-Markierungen
  for (x = [15, B - 15], y = [15, T - 15]) translate([x, y, -0.4]) cylinder(d = 12, h = 0.4);
}

if (teil == "gehaeuse") gehaeuse();
else if (teil == "boden") boden();
else { color("SteelBlue", 0.8) gehaeuse(); color("Gray") translate([0, 0, -2]) boden(); }
