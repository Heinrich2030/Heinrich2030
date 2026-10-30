"""Gehäuse und Gesamtbaugruppe als STEP (für SolidWorks, Fusion 360, FreeCAD, Onshape …).

Aufruf (CadQuery):  python gehaeuse_step.py
Ergebnis:  step/gehaeuse_oberschale.step, step/gehaeuse_boden.step, step/kabeltester_baugruppe.step

Koordinaten wie gehaeuse.scad: x = Breite (links -> rechts), y = Tiefe ab Vorderkante, z = Höhe.
Die Platinenpositionen passen zu kabeltester/hardware/kicad/generator/layouts.py.
"""
import math
import os
import cadquery as cq

HIER = os.path.dirname(os.path.abspath(__file__))
KICAD = os.path.join(HIER, '..', 'hardware', 'kicad')
AUS = os.path.join(HIER, 'step')

# --- Hauptmaße (identisch zu gehaeuse.scad) ---------------------------------
B, T, HV, HH, YK, WD = 250.0, 200.0, 32.0, 88.0, 135.0, 2.4
WINKEL = math.degrees(math.atan((HH - HV) / YK))
L = math.hypot(HH - HV, YK)

# Display Waveshare ESP32-S3-Touch-LCD-7 (am realen Modul nachmessen)
DISP_SICHT = (156.0, 88.0)
DISP_MODUL = (194.0, 112.0)
DISP_X, DISP_Y = 12.0, 10.0

# Platinen (Ecke links hinten im Gehäuse, Unterseite der Platine)
MESSKARTE = dict(x=3.0, y=102.0, z=8.0, b=120.0, h=90.0,
                 loecher=[(4, 30), (114, 60), (4, 86), (116, 86)])
KANAL_Z = 85.6 - 1.0 - 13.3          # Federleiste endet 1 mm unter dem Deck
KANALKARTEN = [dict(x=4.0, y=194.0, z=KANAL_Z), dict(x=128.0, y=194.0, z=KANAL_Z)]
KANAL_LOECHER = [(4, 4), (114, 4), (4, 70), (114, 70)]
SCHACHT = dict(l=104.0, b=14.0, y=YK + (T - YK - 14.0) / 2, x=[13.0, 133.0])
ADAPTER_Z_OBEN = 139.6               # Oberkante der Adapterplatine (gesteckt)

# Gehäusedurchbrüche in der linken Seitenwand
USB_STROM = dict(y=MESSKARTE['y'] - 62.0, z=MESSKARTE['z'] + 1.6 + 1.6, b=10.0, h=4.6)
USB_PICO = dict(y=MESSKARTE['y'] - 14.5, z=MESSKARTE['z'] + 1.6 + 2.6, b=10.0, h=5.0)


def keil():
    """Gehäuseprofil (y, z) in x extrudiert."""
    pts = [(0, 0), (T, 0), (T, HH), (YK, HH), (0, HV)]
    return cq.Workplane('YZ').polyline(pts).close().extrude(B)


def oberschale():
    aussen = keil()
    # Innenraum: Profil um die Wandstärke nach innen versetzt, unten offen
    t, c = math.tan(math.radians(WINKEL)), math.cos(math.radians(WINKEL))
    y_knick = (HH - WD - HV + WD / c) / t
    innen_pts = [(WD, -1), (T - WD, -1), (T - WD, HH - WD), (y_knick, HH - WD), (WD, HV + WD * t - WD / c)]
    innen = cq.Workplane('YZ').workplane(offset=WD).polyline(innen_pts).close().extrude(B - 2 * WD)
    schale = aussen.cut(innen)

    # Arbeitsebene auf der Schrägfläche: Ursprung Vorderkante oben links
    def schraeg():
        return cq.Workplane(cq.Plane(origin=(0, 0, HV), xDir=(1, 0, 0),
                                     normal=(0, -math.sin(math.radians(WINKEL)), math.cos(math.radians(WINKEL)))))
    # Sichtfenster, Einlegetasche, Taster, LED-Schlitz
    fx = DISP_X + (DISP_MODUL[0] - DISP_SICHT[0]) / 2
    fy = DISP_Y + (DISP_MODUL[1] - DISP_SICHT[1]) / 2
    fenster = schraeg().center(fx + DISP_SICHT[0] / 2, fy + DISP_SICHT[1] / 2).rect(*DISP_SICHT).extrude(10, both=True)
    tasche = (schraeg().workplane(offset=-1.0).center(DISP_X + DISP_MODUL[0] / 2, DISP_Y + DISP_MODUL[1] / 2)
              .rect(DISP_MODUL[0] + 0.6, DISP_MODUL[1] + 0.6).extrude(-10))
    tx = B - (B - DISP_X - DISP_MODUL[0]) / 2
    taster = schraeg().center(tx, DISP_Y + DISP_MODUL[1] * 0.7).circle(11.0).extrude(10, both=True)
    led = schraeg().center(tx, DISP_Y + 20).rect(8, 30).extrude(10, both=True)
    schale = schale.cut(fenster).cut(tasche).cut(taster).cut(led)
    # Adapterschächte
    for x in SCHACHT['x']:
        schale = schale.cut(cq.Workplane('XY').box(SCHACHT['l'], SCHACHT['b'], 20, centered=False)
                            .translate((x, SCHACHT['y'], HH - 10)))
    # USB-C (Versorgung) und Pico-USB (Firmware) in der linken Wand
    for u in (USB_STROM, USB_PICO):
        schale = schale.cut(cq.Workplane('XY').box(10, u['b'], u['h']).translate((0, u['y'], u['z'])))
    # Klinkenbuchse Fußschalter vorne rechts
    schale = schale.cut(cq.Workplane('XZ').center(B - 25, HV / 2).circle(3.25).extrude(-10).translate((0, -1, 0)))
    # Lüftungsschlitze
    for k in range(6):
        for x in (-1, B - WD - 1):
            schale = schale.cut(cq.Workplane('XY').box(WD + 2, 4, 30, centered=False).translate((x, 120 + k * 10, 15)))
    # Schachtbeschriftung A / B
    for x, t in ((SCHACHT['x'][0] + SCHACHT['l'] / 2, 'A'), (SCHACHT['x'][1] + SCHACHT['l'] / 2, 'B')):
        try:
            schale = schale.union(cq.Workplane('XY').workplane(offset=HH).center(x, YK + 6).text(t, 7, 0.6))
        except Exception:
            pass   # ohne Systemschrift keine Beschriftung
    return schale


def boden():
    platte = cq.Workplane('XY').box(B - 2 * WD - 0.6, T - 2 * WD - 0.6, 2, centered=False).translate((WD + 0.3, WD + 0.3, -2))
    dome = []
    for lx, ly in MESSKARTE['loecher']:
        dome.append((MESSKARTE['x'] + lx, MESSKARTE['y'] - ly, MESSKARTE['z']))
    for k in KANALKARTEN:
        for lx, ly in KANAL_LOECHER:
            dome.append((k['x'] + lx, k['y'] - ly, k['z']))
    for x, y, h in dome:
        d = 7.0 if h < 20 else 9.0
        saeule = cq.Workplane('XY').circle(d / 2).circle(1.3).extrude(h).translate((x, y, 0))
        platte = platte.union(saeule)
    return platte


def platine(name):
    """STEP der Platine (von KiCad erzeugt, liegt gezippt in hardware/kicad/<name>/fertigung)."""
    pfad = os.path.join(KICAD, name, 'fertigung', f'{name}.step')
    if not os.path.exists(pfad):
        import tempfile
        import zipfile
        tmp = tempfile.mkdtemp()
        with zipfile.ZipFile(pfad + '.zip') as z:
            z.extractall(tmp)
        pfad = os.path.join(tmp, f'{name}.step')
    return cq.importers.importStep(pfad)


def display():
    """Platzhalter für das Waveshare-Modul (Glas + Rahmen + Elektronik)."""
    w = (cq.Workplane('XY').box(DISP_MODUL[0], DISP_MODUL[1], 1.2, centered=False).translate((DISP_X, DISP_Y, -3.6))
         .union(cq.Workplane('XY').box(DISP_MODUL[0] - 2, DISP_MODUL[1] - 2, 11, centered=False)
                .translate((DISP_X + 1, DISP_Y + 1, -14.6))))
    return w.rotate((0, 0, 0), (1, 0, 0), WINKEL).translate((0, 0, HV))


def baugruppe():
    a = cq.Assembly(name='Kabeltester')
    a.add(boden(), name='Bodenplatte', color=cq.Color(0.29, 0.32, 0.31))
    a.add(oberschale(), name='Gehaeuse_Oberschale', color=cq.Color(0.80, 0.82, 0.80, 0.6))
    a.add(display(), name='Display_7Zoll', color=cq.Color(0.08, 0.09, 0.10))
    m = MESSKARTE
    a.add(platine('messkarte'), name='Messkarte', loc=cq.Location(cq.Vector(m['x'], m['y'], m['z'])))
    for i, k in enumerate(KANALKARTEN):
        a.add(platine('kanalkarte'), name=f'Kanalkarte_{"AB"[i]}', loc=cq.Location(cq.Vector(k['x'], k['y'], k['z'])))
    # Adapter: senkrecht, Bauteilseite nach vorne; Steckmitte der Messerleiste über der Federleiste
    for i, x in enumerate((SCHACHT['x'][0] + SCHACHT['l'] / 2 - 50, SCHACHT['x'][1] + SCHACHT['l'] / 2 - 50)):
        loc = cq.Location(cq.Vector(x, T - 29.3, ADAPTER_Z_OBEN), cq.Vector(1, 0, 0), 90)
        a.add(platine('adapter_rj45'), name=f'Adapter_{"AB"[i]}', loc=loc)
    return a


def main():
    os.makedirs(AUS, exist_ok=True)
    cq.exporters.export(oberschale(), os.path.join(AUS, 'gehaeuse_oberschale.step'))
    cq.exporters.export(boden(), os.path.join(AUS, 'gehaeuse_boden.step'))
    cq.exporters.export(oberschale(), os.path.join(AUS, 'gehaeuse_oberschale.stl'))
    cq.exporters.export(boden(), os.path.join(AUS, 'gehaeuse_boden.stl'))
    ziel = os.path.join(AUS, 'kabeltester_baugruppe.step')
    baugruppe().save(ziel)
    import zipfile
    with zipfile.ZipFile(ziel + '.zip', 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.write(ziel, os.path.basename(ziel))
    os.remove(ziel)   # 290 MB ungepackt – gezippt ca. 40 MB
    print('geschrieben:', sorted(os.listdir(AUS)))


if __name__ == '__main__':
    main()
