"""Schreibt ein KiCad-7-Schaltplanprojekt (Hauptblatt + Unterblätter) aus dem Netzlisten-Modell.

Jeder Pin bekommt ein Netzlabel direkt am Pinende (lokal, oder global wenn das Netz mehrere
Blätter berührt). Unbenutzte Pins erhalten ein No-Connect-Kreuz.
"""
import os
import uuid
from sexp import Sym, dump
from modell import symbol_flach, symbol_pins, symbol_rahmen

R = 2.54
SCHRIFT = [Sym('effects'), [Sym('font'), [Sym('size'), 1.27, 1.27]]]
PAPIER = {'A4': (297, 210), 'A3': (420, 297), 'A2': (594, 420), 'A1': (841, 594)}


def U():
    return str(uuid.uuid4())


def raster(v):
    return round(v / R) * R


def _eff(justify=None, hide=False):
    e = [Sym('effects'), [Sym('font'), [Sym('size'), 1.27, 1.27]]]
    if justify:
        e.append([Sym('justify')] + [Sym(j) for j in justify])
    if hide:
        e.append(Sym('hide'))
    return e


def _prop(name, wert, x, y, hide=False, justify=None):
    return [Sym('property'), name, wert, [Sym('at'), x, y, 0], _eff(justify, hide)]


def _label(netz, x, y, winkel, global_):
    just = {0: ['left'], 180: ['right'], 90: ['left'], 270: ['right']}[int(winkel) % 360]
    if global_:
        return [Sym('global_label'), netz, [Sym('shape'), Sym('bidirectional')], [Sym('at'), x, y, winkel],
                [Sym('fields_autoplaced')], _eff(just), [Sym('uuid'), U()],
                [Sym('property'), 'Intersheetrefs', '${INTERSHEET_REFS}', [Sym('at'), x, y, 0], _eff(None, True)]]
    return [Sym('label'), netz, [Sym('at'), x, y, winkel], [Sym('fields_autoplaced')],
            _eff(just + ['bottom'] if winkel in (0, 180) else just), [Sym('uuid'), U()]]


def _einheiten(teil):
    pins = symbol_pins(teil.lib_id)
    return sorted(e for e in pins if e > 0) or [1]


def _textbreite(s):
    return len(s) * 1.27 * 0.85 + 2.5


class Blattbau:
    """Setzt Symbole zeilenweise auf ein Blatt."""

    def __init__(self, papier):
        self.papier = papier
        self.b, self.h = PAPIER[papier]
        self.x = 25.4
        self.y = 30.48
        self.zeilenhoehe = 0
        self.elemente = []

    def platz(self, breite, hoehe):
        if self.x + breite > self.b - 20 and self.x > 25.4:
            self.x = 25.4
            self.y += self.zeilenhoehe + 7.62
            self.zeilenhoehe = 0
        pos = (self.x, self.y)
        self.x += breite + 5.08
        self.zeilenhoehe = max(self.zeilenhoehe, hoehe)
        return pos

    def voll(self):
        return self.y > self.h - 30


def schreibe(platine, ordner, projekt_uuid=None):
    os.makedirs(ordner, exist_ok=True)
    netze = platine.netze()
    blaetter_je_netz = {}
    for t in platine.teile:
        for netz in t.pins.values():
            blaetter_je_netz.setdefault(netz, set()).add(t.blatt)

    root_uuid = projekt_uuid or U()
    blatt_uuid = {b: (root_uuid if i == 0 else U()) for i, b in enumerate(platine.blaetter)}
    lib_ids = sorted({t.lib_id for t in platine.teile})
    dateien = {}

    for nr, blatt in enumerate(platine.blaetter):
        teile = [t for t in platine.teile if t.blatt == blatt]
        # Papiergröße nach Fläche wählen
        flaeche = 0
        for t in teile:
            for e in _einheiten(t):
                x0, y0, x1, y1 = symbol_rahmen(t.lib_id, e)
                flaeche += (x1 - x0 + 30) * (y1 - y0 + 12)
        papier = 'A3' if flaeche < 50000 else ('A2' if flaeche < 110000 else 'A1')
        bau = Blattbau(papier)
        pfad = f'/{root_uuid}' if nr == 0 else f'/{root_uuid}/{blatt_uuid[blatt]}'
        inhalt = []
        for t in teile:
            pins = symbol_pins(t.lib_id)
            for i, einheit in enumerate(_einheiten(t)):
                x0, y0, x1, y1 = symbol_rahmen(t.lib_id, einheit)
                eigene = pins.get(einheit, []) + (pins.get(0, []) if i == 0 else [])
                links = max([_textbreite(t.pins.get(p[0], '')) for p in eigene if p[4] == 0] + [0])
                rechts = max([_textbreite(t.pins.get(p[0], '')) for p in eigene if p[4] == 180] + [0])
                oben = 6 if any(p[4] == 270 for p in eigene) else 0
                unten = 6 if any(p[4] == 90 for p in eigene) else 0
                breite = (x1 - x0) + links + rechts + 4
                hoehe = (y1 - y0) + oben + unten + 7
                px, py = bau.platz(breite, hoehe)
                sx = raster(px + links - x0)
                sy = raster(py + oben + y1 + 2.54)
                inhalt.append(_symbol(t, einheit, sx, sy, y0, y1, pfad, platine.name))
                for (num, name, lx, ly, winkel, versteckt) in eigene:
                    ex, ey = round(sx + lx, 3), round(sy - ly, 3)
                    netz = t.pins.get(num)
                    if netz:
                        inhalt.append(_label(netz, ex, ey, (winkel + 180) % 360, len(blaetter_je_netz[netz]) > 1))
                    elif not versteckt:
                        inhalt.append([Sym('no_connect'), [Sym('at'), ex, ey], [Sym('uuid'), U()]])

        kopf = [Sym('kicad_sch'), [Sym('version'), 20230121], [Sym('generator'), Sym('eeschema')],
                [Sym('uuid'), blatt_uuid[blatt]], [Sym('paper'), papier],
                [Sym('title_block'), [Sym('title'), f'{platine.titel} – {blatt}'], [Sym('date'), '2026-10-30'],
                 [Sym('rev'), '1.0'], [Sym('company'), 'Kabeltester'],
                 [Sym('comment'), 1, 'Automatisch erzeugt aus kabeltester/hardware/kicad/generator – nicht von Hand ändern'],
                 [Sym('comment'), 2, 'Netze sind über Labels verbunden (Label am Pinende)']],
                [Sym('lib_symbols')] + [symbol_flach(l) for l in lib_ids if any(t.lib_id == l for t in teile)]]
        datei = f'{platine.name}.kicad_sch' if nr == 0 else f'{platine.name}_{_dateiname(blatt)}.kicad_sch'
        dateien[blatt] = (datei, kopf, inhalt)

    # Unterblatt-Kästen im Hauptblatt
    haupt_datei, haupt_kopf, haupt_inhalt = dateien[platine.blaetter[0]]
    for i, blatt in enumerate(platine.blaetter[1:]):
        x, y = 25.4 + (i % 6) * 60.96, 12.7
        datei = dateien[blatt][0]
        haupt_inhalt.insert(0, [Sym('sheet'), [Sym('at'), x, y], [Sym('size'), 50.8, 10.16], [Sym('fields_autoplaced')],
                                [Sym('stroke'), [Sym('width'), 0.1524], [Sym('type'), Sym('solid')]],
                                [Sym('fill'), [Sym('color'), 0, 0, 0, 0.0]], [Sym('uuid'), blatt_uuid[blatt]],
                                _prop('Sheetname', blatt, x, y - 0.7, justify=['left', 'bottom']),
                                _prop('Sheetfile', datei, x, y + 10.76, justify=['left', 'top']),
                                [Sym('instances'), [Sym('project'), platine.name,
                                                    [Sym('path'), f'/{root_uuid}', [Sym('page'), str(i + 2)]]]]])
        # Hauptblatt-Inhalt weiter unten beginnen lassen
    for blatt, (datei, kopf, inhalt) in dateien.items():
        doc = kopf + inhalt
        if blatt == platine.blaetter[0]:
            doc.append([Sym('sheet_instances'), [Sym('path'), '/', [Sym('page'), '1']]])
        with open(os.path.join(ordner, datei), 'w') as f:
            f.write(dump(doc) + '\n')
    return root_uuid, blatt_uuid


def _dateiname(blatt):
    import re
    ersatz = {'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss', ' ': '_'}
    s = ''.join(ersatz.get(c, c) for c in blatt.lower())
    return re.sub(r'[^a-z0-9_-]', '', s).strip('_')


def _symbol(t, einheit, x, y, y0, y1, pfad, projekt):
    pins = symbol_pins(t.lib_id)
    alle = {nr for e in pins.values() for nr, *_ in e}
    felder = [_prop('Reference', t.ref, x, y - y1 - 1.6, justify=['left']),
              _prop('Value', t.wert, x, y - y0 + 1.6, justify=['left']),
              _prop('Footprint', t.footprint, x, y, hide=True),
              _prop('Datasheet', '', x, y, hide=True)]
    for k, v in t.felder.items():
        if v:
            felder.append(_prop(k, v, x, y, hide=True))
    return ([Sym('symbol'), [Sym('lib_id'), t.lib_id], [Sym('at'), x, y, 0], [Sym('unit'), einheit],
             [Sym('in_bom'), Sym('yes')], [Sym('on_board'), Sym('yes')], [Sym('dnp'), Sym('no')],
             [Sym('uuid'), t.uuid if einheit == _einheiten(t)[0] else U()]] + felder +
            [[Sym('pin'), nr, [Sym('uuid'), U()]] for nr in sorted(alle)] +
            [[Sym('instances'), [Sym('project'), projekt,
                                 [Sym('path'), pfad, [Sym('reference'), t.ref], [Sym('unit'), einheit]]]]])
