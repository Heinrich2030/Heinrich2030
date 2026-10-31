"""Erzeugt die projekteigene Symbol- und Footprint-Bibliothek (kabeltester.kicad_sym / kabeltester.pretty).

Nur für Bauteile, die in den KiCad-7-Standardbibliotheken fehlen. Pinbelegungen nach Datenblatt;
Einträge mit PRUEFEN=True sind vor der Fertigung gegen das Original-Datenblatt zu prüfen.
"""
import os
import itertools
import uuid

_ZAEHLER = itertools.count()


def _id():
    """Deterministische IDs: gleiche Bibliothek bei jedem Lauf."""
    return uuid.uuid5(uuid.NAMESPACE_URL, f'kabeltester/{next(_ZAEHLER)}')
from sexp import Sym, dump

PIN_LEN = 2.54
RASTER = 2.54


def _pin(nummer, name, x, y, winkel, typ='passive'):
    return [Sym('pin'), Sym(typ), Sym('line'), [Sym('at'), x, y, winkel], [Sym('length'), PIN_LEN],
            [Sym('name'), name, [Sym('effects'), [Sym('font'), [Sym('size'), 1.27, 1.27]]]],
            [Sym('number'), str(nummer), [Sym('effects'), [Sym('font'), [Sym('size'), 1.27, 1.27]]]]]


def _prop(name, wert, x, y, versteckt=False):
    eff = [Sym('effects'), [Sym('font'), [Sym('size'), 1.27, 1.27]]]
    if versteckt:
        eff.append(Sym('hide'))
    return [Sym('property'), name, wert, [Sym('at'), x, y, 0], eff]


def kasten(name, ref, wert, footprint, links, rechts, beschreibung='', breite=15.24, datenblatt=''):
    """Kastensymbol. links/rechts: Listen von (nummer, name, typ) oder None für eine Lücke."""
    n = max(len(links), len(rechts))
    hoehe = (n + 1) * RASTER
    oben = hoehe / 2
    oben = round(oben / RASTER) * RASTER
    pins = []
    for i, p in enumerate(links):
        if p:
            pins.append(_pin(p[0], p[1], -breite / 2 - PIN_LEN, oben - (i + 1) * RASTER, 0, p[2] if len(p) > 2 else 'passive'))
    for i, p in enumerate(rechts):
        if p:
            pins.append(_pin(p[0], p[1], breite / 2 + PIN_LEN, oben - (i + 1) * RASTER, 180, p[2] if len(p) > 2 else 'passive'))
    unten = oben - (n + 1) * RASTER
    rect = [Sym('rectangle'), [Sym('start'), -breite / 2, oben], [Sym('end'), breite / 2, unten],
            [Sym('stroke'), [Sym('width'), 0.254], [Sym('type'), Sym('default')]],
            [Sym('fill'), [Sym('type'), Sym('background')]]]
    sym = [Sym('symbol'), name, [Sym('in_bom'), Sym('yes')], [Sym('on_board'), Sym('yes')],
           _prop('Reference', ref, -breite / 2, oben + 1.27),
           _prop('Value', wert, -breite / 2, unten - 1.27),
           _prop('Footprint', footprint, 0, unten - 3.81, True),
           _prop('Datasheet', datenblatt, 0, unten - 6.35, True),
           _prop('ki_description', beschreibung, 0, 0, True),
           [Sym('symbol'), f'{name}_0_1', rect],
           [Sym('symbol'), f'{name}_1_1'] + pins]
    return sym


def symbole():
    s = []
    # Raspberry Pi Pico 2 (RP2350) als Modul, Pinbelegung identisch zum Pico 1
    gp_links = [(1, 'GP0'), (2, 'GP1'), (3, 'GND', 'power_in'), (4, 'GP2'), (5, 'GP3'), (6, 'GP4'), (7, 'GP5'),
                (8, 'GND', 'power_in'), (9, 'GP6'), (10, 'GP7'), (11, 'GP8'), (12, 'GP9'), (13, 'GND', 'power_in'),
                (14, 'GP10'), (15, 'GP11'), (16, 'GP12'), (17, 'GP13'), (18, 'GND', 'power_in'), (19, 'GP14'), (20, 'GP15')]
    gp_rechts = [(40, 'VBUS', 'power_out'), (39, 'VSYS', 'power_in'), (38, 'GND', 'power_in'), (37, '3V3_EN'),
                 (36, '3V3', 'power_out'), (35, 'ADC_VREF'), (34, 'GP28'), (33, 'AGND', 'power_in'), (32, 'GP27'),
                 (31, 'GP26'), (30, 'RUN'), (29, 'GP22'), (28, 'GND', 'power_in'), (27, 'GP21'), (26, 'GP20'),
                 (25, 'GP19'), (24, 'GP18'), (23, 'GND', 'power_in'), (22, 'GP17'), (21, 'GP16')]
    gp_links = [t if len(t) == 3 else t + ('bidirectional',) for t in gp_links]
    gp_rechts = [t if len(t) == 3 else t + ('bidirectional',) for t in gp_rechts]
    s.append(kasten('RaspberryPi_Pico2', 'U', 'Raspberry Pi Pico 2', 'kabeltester:RaspberryPi_Pico2_THT',
                    gp_links, gp_rechts, 'Raspberry Pi Pico 2 Modul (RP2350), Pinbelegung wie Pico', 20.32,
                    'https://datasheets.raspberrypi.com/pico/pico-2-datasheet.pdf'))
    # ADG1606: 16:1-Multiplexer, Ron 4,5 Ohm, TSSOP-28 (Pinbelegung wie ADG406/ADG1206) – PRUEFEN
    links = [(1, 'VDD', 'power_in'), (27, 'VSS', 'power_in'), (12, 'GND', 'power_in'), None,
             (17, 'A0', 'input'), (16, 'A1', 'input'), (15, 'A2', 'input'), (14, 'A3', 'input'), (18, 'EN', 'input'),
             None, (28, 'D'), None, (2, 'NC', 'no_connect'), (3, 'NC', 'no_connect'), (13, 'NC', 'no_connect')]
    rechts = [(19, 'S1'), (20, 'S2'), (21, 'S3'), (22, 'S4'), (23, 'S5'), (24, 'S6'), (25, 'S7'), (26, 'S8'),
              (11, 'S9'), (10, 'S10'), (9, 'S11'), (8, 'S12'), (7, 'S13'), (6, 'S14'), (5, 'S15'), (4, 'S16')]
    s.append(kasten('ADG1606', 'U', 'ADG1606BRUZ', 'Package_SO:TSSOP-28_4.4x9.7mm_P0.65mm', links, rechts,
                    '16:1 Analog-Multiplexer 4,5 Ohm (Pinbelegung vor Fertigung pruefen)', 12.7,
                    'https://www.analog.com/media/en/technical-documentation/data-sheets/ADG1606_1607.pdf'))
    # BAV199: zwei Low-Leakage-Dioden in Serie, SOT-23: 1 = Anode D1, 2 = Kathode D2, 3 = Kathode D1/Anode D2
    s.append(kasten('BAV199', 'D', 'BAV199', 'Package_TO_SOT_SMD:SOT-23',
                    [(3, 'K1/A2')], [(2, 'K2'), (1, 'A1')], 'Doppeldiode in Serie, Leckstrom pA (Klemmung)', 7.62,
                    'https://assets.nexperia.com/documents/data-sheet/BAV199.pdf'))
    # PESD2CAN: bidirektionale ESD-Schutzdiode 2-fach, SOT-23: 1/2 = Leitungen, 3 = gemeinsam (GND)
    s.append(kasten('PESD2CAN', 'D', 'PESD2CAN', 'Package_TO_SOT_SMD:SOT-23',
                    [(1, 'L1'), (2, 'L2')], [(3, 'COM')], 'ESD-Schutz 24 V bidirektional, 2 Leitungen', 7.62,
                    'https://assets.nexperia.com/documents/data-sheet/PESD2CAN.pdf'))
    # DIN 41612 Bauform C, 96-polig (Reihen a, b, c)
    for name, fp in (('DIN41612_C96_Female', 'Connector_DIN:DIN41612_C_3x32_Female_Vertical_THT'),
                     ('DIN41612_C96_Male', 'Connector_DIN:DIN41612_C_3x32_Male_Horizontal_THT')):
        links = [(f'a{i}', f'a{i}') for i in range(1, 33)] + [None] + [(f'b{i}', f'b{i}') for i in range(1, 33)]
        rechts = [(f'c{i}', f'c{i}') for i in range(1, 33)]
        s.append(kasten(name, 'J', name.replace('_', ' '), fp, links, rechts, 'DIN 41612 Bauform C, 96-polig', 12.7))
    return s


def schreibe_symbole(pfad):
    inhalt = [Sym('kicad_symbol_lib'), [Sym('version'), 20220914], [Sym('generator'), Sym('kabeltester_generator')]] + symbole()
    with open(pfad, 'w') as f:
        f.write(dump(inhalt) + '\n')


def pico_footprint():
    global _ZAEHLER
    _ZAEHLER = itertools.count()
    """Pico-2-Modul, durchkontaktiert (2 x 20, Raster 2,54, Reihenabstand 17,78 mm), Pin 1 oben links."""
    pads = []
    for i in range(20):
        y = -24.13 + i * 2.54
        for nummer, x in ((i + 1, -8.89), (40 - i, 8.89)):
            form = 'rect' if nummer == 1 else 'oval'
            pads.append(f'  (pad "{nummer}" thru_hole {form} (at {x} {y}) (size 1.7 1.7) (drill 1.02) '
                        f'(layers "*.Cu" "*.Mask") (tstamp "{_id()}"))')
    linien = []
    for (x1, y1, x2, y2) in ((-10.5, -25.5, 10.5, -25.5), (10.5, -25.5, 10.5, 25.5), (10.5, 25.5, -10.5, 25.5), (-10.5, 25.5, -10.5, -25.5)):
        linien.append(f'  (fp_line (start {x1} {y1}) (end {x2} {y2}) (stroke (width 0.12) (type solid)) (layer "F.SilkS") (tstamp "{_id()}"))')
        linien.append(f'  (fp_line (start {x1 * 1.03:.3f} {y1 * 1.02:.3f}) (end {x2 * 1.03:.3f} {y2 * 1.02:.3f}) (stroke (width 0.05) (type solid)) (layer "F.CrtYd") (tstamp "{_id()}"))')
        linien.append(f'  (fp_line (start {x1} {y1}) (end {x2} {y2}) (stroke (width 0.1) (type solid)) (layer "F.Fab") (tstamp "{_id()}"))')
    # USB-Buchse des Pico markieren
    linien.append(f'  (fp_rect (start -4 -26.5) (end 4 -21.5) (stroke (width 0.12) (type solid)) (fill none) (layer "F.SilkS") (tstamp "{_id()}"))')
    return ('(footprint "RaspberryPi_Pico2_THT" (version 20221018) (generator kabeltester_generator)\n'
            '  (layer "F.Cu")\n  (descr "Raspberry Pi Pico 2, Modul auf Stiftleisten 2x20, 2,54 mm")\n'
            '  (attr through_hole)\n'
            f'  (fp_text reference "REF**" (at 0 -27.5) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))) (tstamp "{_id()}"))\n'
            f'  (fp_text value "Pico2" (at 0 27.5) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))) (tstamp "{_id()}"))\n'
            + '\n'.join(linien) + '\n' + '\n'.join(pads) + '\n)\n')


def schreibe_footprints(ordner):
    os.makedirs(ordner, exist_ok=True)
    with open(os.path.join(ordner, 'RaspberryPi_Pico2_THT.kicad_mod'), 'w') as f:
        f.write(pico_footprint())


if __name__ == '__main__':
    import sys
    ziel = sys.argv[1]
    schreibe_symbole(os.path.join(ziel, 'kabeltester.kicad_sym'))
    schreibe_footprints(os.path.join(ziel, 'kabeltester.pretty'))
