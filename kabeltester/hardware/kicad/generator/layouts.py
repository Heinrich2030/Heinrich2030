"""Platzierung der Bauteile je Platine. Maße in mm, KiCad-Koordinaten (y nach unten).

Mechanische Bezüge (Gehäuse gehaeuse.scad, x = Breite, y = Tiefe ab Vorderkante):
  Kanalkarte A: Platinenecke links hinten bei Gehäuse (4, 194), Karte B um +124 mm in x versetzt.
                KiCad-y wächst nach vorne. DIN-Federleiste mittig unter dem Adapterschacht.
  Messkarte:    Platinenecke links hinten bei Gehäuse (3, 102), USB-C an der linken Kante.
  Adapter:      steht senkrecht, KiCad-oben = oben, Bauteilseite nach vorne.
"""
import re

MECH = {
    'kanalkarte': {'breite': 118.0, 'hoehe': 74.0, 'lagen': 4},
    'messkarte': {'breite': 120.0, 'hoehe': 90.0, 'lagen': 4},
    'adapter_rj45': {'breite': 100.0, 'hoehe': 60.0, 'lagen': 2},
}


def _nr(ref):
    return int(re.sub(r'\D', '', ref))


def _refs(lp, praefix):
    return sorted([r for r in lp.fps if re.fullmatch(praefix + r'\d+', r)], key=_nr)


def _netz_von(lp, ref, pin):
    for pad in lp.fps[ref].Pads():
        if str(pad.GetNumber()) == str(pin):
            return pad.GetNetname()
    return ''


def adapter(lp):
    import pcbnew
    b, h = lp.b, lp.h
    # Messerleiste: um 180° gedreht, Steckseite ragt unten 3,7 mm über die Kante
    lp.setze('J1', b / 2, h - 9.0 - 2.54, 180, mitte='pads')
    # RJ45 oben, Öffnung nach oben (Rotation so wählen, dass das Gehäuse nach oben übersteht)
    for i, ref in enumerate(('J2', 'J3')):
        besten = None
        for rot in (0, 90, 180, 270):
            lp.setze(ref, 0, 0, rot)
            x0, y0, x1, y1 = lp.rahmen(ref)
            pads = [pcbnew.ToMM(p.GetPosition().y) for p in lp.fps[ref].Pads()]
            ueberstand = min(pads) - y0          # Gehäuse oberhalb der Pads
            if x1 - x0 < 25 and (besten is None or ueberstand > besten[1]):
                besten = (rot, ueberstand)
        lp.setze(ref, 25 + i * 50, 0, besten[0])
        x0, y0, x1, y1 = lp.rahmen(ref)
        lp.setze(ref, 25 + i * 50 - (x0 + x1) / 2, -y0, besten[0])
    lp.setze('U1', b / 2, 33, 0, mitte='rahmen')
    lp.setze('C1', b / 2 + 5, 33, 90, mitte='rahmen')
    lp.setze('H1', 4, 30)
    lp.setze('H2', b - 4, 30)
    lp.text('KABELTESTER ADAPTER  2x RJ45', b / 2, 26, 1.8)
    lp.text('Port 1 = TP1-8 · Port 2 = TP9-16', b / 2, 40, 1.2)
    lp.flaeche('GND', pcbnew.B_Cu)
    lp.flaeche('GND', pcbnew.F_Cu)


def kanalkarte(lp):
    import pcbnew
    b, h = lp.b, lp.h
    teil = {t.ref: t for t in lp.p.teile}
    folge = [t.ref for t in lp.p.teile]
    # DIN-Federleiste: Längsachse entlang x, Mitte im Gehäuse bei y = 167,5 -> KiCad-y 26,5
    lp.setze('J1', b / 2, 26.5, 90, mitte='pads')
    din = lp.flaeche_von('J1', 0.2)
    loecher = [(x - 3.6, y - 3.6, x + 3.6, y + 3.6) for x, y in lp.ecken_loecher(['H1', 'H2', 'H3', 'H4'])]
    # Flachbandstecker unten, vorne mittig (THT: Sperrfläche auf beiden Seiten)
    lp.setze('J2', b / 2, h - 5.5, 90, unten=True, mitte='pads')
    idc = lp.flaeche_von('J2', 0.3)
    sperre = loecher + [din, idc]

    def art(r):
        return teil[r].wert
    ics = [r for r in folge if r.startswith('U')]
    adg = [r for r in ics if art(r).startswith('ADG')]
    hct = [r for r in ics if art(r).startswith('CD74')]
    sr = [r for r in ics if art(r).startswith('SN74')]
    entk = {r: folge[i + 1] for i, r in enumerate(folge) if r in ics and folge[i + 1].startswith('C')}

    # Oberseite hinten: 8x ADG1606 (je Block HI, LO), Schieberegister an den Rändern
    spalte = (b - 20) / 8
    for i, r in enumerate(adg):
        x = 10 + spalte * (i + 0.5)
        lp.setze(r, x, 6.6, 0, mitte='rahmen')
        lp.setze(entk[r], x, 14.0, 0, mitte='rahmen')
    for r, x in ((sr[0], 4.6), (sr[1], b - 4.6)):
        lp.setze(r, x, 14.8, 0, mitte='rahmen')
        lp.setze(entk[r], x, 19.2, 0, mitte='rahmen')
    # Oberseite vorne: 8x CD74HCT4067
    y_hct = din[3] + 0.6
    for i, r in enumerate(hct):
        x = 1.0 + (b - 2.0) / 8 * (i + 0.5)
        lp.setze(r, x, y_hct + 8.6, 0, mitte='rahmen')
        lp.setze(entk[r], x, y_hct + 18.4, 0, mitte='rahmen')
    # Kanalbauteile sammeln
    def suche(bed):
        return [r for r in folge if bed(teil[r])]
    sense_r = [suche(lambda t, n=n: t.ref.startswith('R') and t.pins.get('2') == f'S{n}')[0] for n in range(1, 65)]
    sense_d = [suche(lambda t, n=n: t.wert == 'BAV199' and t.pins.get('3') == f'S{n}')[0] for n in range(1, 65)]
    force_d = [suche(lambda t, n=n: t.wert == 'BAV199' and t.pins.get('3') == f'F{n}')[0] for n in range(1, 65)]
    r33 = suche(lambda t: t.wert == '33')
    ptc = suche(lambda t: t.wert == '100mA')
    esd = suche(lambda t: t.wert == 'PESD2CAN')
    ruhe = suche(lambda t: t.ref.startswith('R') and t.wert == '10k')
    sonst = [r for r in folge if r.startswith('C') and r not in entk.values()] + ['F1']

    # Oberseite: Sense-Pfad (1k + BAV199) zwischen HCT-Reihe und Vorderkante
    oben_sense = []
    for n in range(64):
        oben_sense += [sense_r[n], sense_d[n]]
    rest = lp.packe(oben_sense, (0.6, y_hct + 20.2, b - 0.6, h - 0.6), rot=90, hindernisse=sperre)
    # Unterseite: Force-Pfad (33 R, PTC, BAV199) und ESD hinten, Rest vorne
    kette = []
    for n in range(64):
        kette += [r33[n], ptc[n], force_d[n]]
        if n % 2 == 0:
            kette.append(esd[n // 2])
    rest = lp.packe(kette + rest, (0.6, 0.6, b - 0.6, din[1] - 0.2), rot=90, unten=True, hindernisse=sperre)
    rest = lp.packe(rest + ruhe + sonst, (0.6, din[3] + 0.2, b - 0.6, h - 0.6), rot=90, unten=True, hindernisse=sperre)
    if rest:
        raise RuntimeError(f'Kanalkarte: kein Platz für {len(rest)} Bauteile: {rest[:8]}')
    lp.text('KABELTESTER KANALKARTE 64 TP v1.0', b / 2, idc[1] - 1.5, 1.0, unten=True)
    lp.flaeche('GND', pcbnew.In1_Cu)
    lp.flaeche('GND', pcbnew.B_Cu)
    lp.flaeche('GND', pcbnew.F_Cu)


def messkarte(lp):
    import pcbnew
    b, h = lp.b, lp.h
    teil = {t.ref: t for t in lp.p.teile}
    folge = [t.ref for t in lp.p.teile]
    blatt = {r: teil[r].blatt for r in folge}
    # Pico 2 hinten links, seine USB-Buchse zeigt zur linken Gehäusewand (Firmware-Update)
    pico = [r for r in folge if teil[r].wert == 'Raspberry Pi Pico 2'][0]
    lp.setze(pico, 26.0, 14.5, 90, mitte='rahmen')
    lp.setze(pico, 0, 0, 90)
    x0, y0, x1, y1 = lp.rahmen(pico)
    lp.setze(pico, -x0 + 0.6, 14.5 - (y0 + y1) / 2, 90)
    # USB-C (Versorgung) an der linken Kante
    usb = 'J1'
    lp.setze(usb, 0, 0, 270)
    x0, y0, x1, y1 = lp.rahmen(usb)
    lp.setze(usb, -x0 - 1.0, 62 - (y0 + y1) / 2, 270)
    # Flachbandstecker: Kanalkarte A hinten mittig, B an der rechten Kante
    lp.setze('J2', 79.0, 5.6, 90, mitte='pads')
    lp.setze('J3', b - 5.6, 28.0, 0, mitte='pads')
    loecher = [(4, 30), (114, 60), (4, 86), (116, 86)]
    for ref, (x, y) in zip(['H1', 'H2', 'H3', 'H4'], loecher):
        lp.setze(ref, x, y)
    sperre = [(x - 3.6, y - 3.6, x + 3.6, y + 3.6) for x, y in loecher]
    sperre += [lp.flaeche_von(r, 0.4) for r in (pico, usb, 'J2', 'J3')]
    # Bedienanschlüsse vorne
    vorne = [r for r in folge if r in ('J4', 'J5', 'J6', 'J7', 'J8', 'JP1') or r.startswith('BZ') or r.startswith('Q')
             and blatt[r] == lp.p.blaetter[0]]
    rest = lp.packe(vorne, (9.0, h - 14.0, b - 9.0, h - 0.6), hindernisse=sperre)
    for r in vorne:
        if r not in rest:
            sperre.append(lp.flaeche_von(r, 0.3))
    # Versorgung links neben USB-C
    versorgung = [r for r in folge if blatt[r] == lp.p.blaetter[0] and r not in vorne + [pico, usb, 'J2', 'J3']
                  and not r.startswith('H')]
    ics = [r for r in folge if r.startswith('U') and r != pico]
    steuerung = [r for r in folge if blatt[r] == 'Steuerung']
    frontend = [r for r in folge if blatt[r] == 'Messfrontend']
    frontend = [r for r in frontend if r in ics] + [r for r in frontend if r not in ics]
    rest = lp.packe(rest + steuerung, (55.0, 12.0, b - 12.0, 27.0), hindernisse=sperre)
    rest = lp.packe(rest + frontend, (38.0, 28.0, b - 0.6, h - 15.0), hindernisse=sperre)
    rest = lp.packe(rest + versorgung, (8.5, 27.0, 37.5, h - 15.0), hindernisse=sperre)
    rest = lp.packe(rest, (0.6, 0.6, b - 0.6, h - 0.6), unten=True, hindernisse=sperre)
    if rest:
        raise RuntimeError(f'Messkarte: kein Platz für {rest}')
    lp.text('KABELTESTER MESSKARTE v1.0', 75, h - 15.5, 1.2)
    lp.flaeche('GND', pcbnew.In1_Cu)
    lp.flaeche('GND', pcbnew.B_Cu)
