"""Netzlisten-Modell: eine Quelle für Schaltplan und Platine."""
import os
import re
import uuid
from collections import defaultdict
from sexp import parse, find, findall, Sym

KICAD_SYM = '/usr/share/kicad/symbols'
HIER = os.path.dirname(os.path.abspath(__file__))
EIGENE_SYM = os.path.join(HIER, '..', 'bibliothek', 'kabeltester.kicad_sym')

_libs = {}


def _lib(name):
    if name not in _libs:
        pfad = EIGENE_SYM if name == 'kabeltester' else os.path.join(KICAD_SYM, f'{name}.kicad_sym')
        root = parse(open(pfad).read())
        _libs[name] = {s[1]: s for s in findall(root, 'symbol')}
    return _libs[name]


def symbol_flach(lib_id):
    """Symbol aus der Bibliothek, 'extends' aufgelöst, als Kopie mit Namen 'Lib:Name'."""
    lib, name = lib_id.split(':')
    syms = _lib(lib)
    s = syms[name]
    ext = find(s, 'extends')
    if ext:
        basis = syms[ext[1]]
        eigene_props = {p[1]: p for p in findall(s, 'property')}
        neu = [Sym('symbol'), lib_id]
        for e in basis[2:]:
            if isinstance(e, list) and e[0] == 'property':
                neu.append(eigene_props.pop(e[1], e))
            elif isinstance(e, list) and e[0] == 'symbol':
                unter = list(e)
                unter[1] = unter[1].replace(ext[1], name, 1)
                neu.append(unter)
            else:
                neu.append(e)
        for p in eigene_props.values():
            neu.insert(2, p)
        return neu
    neu = list(s)
    neu[1] = lib_id
    return neu


def symbol_pins(lib_id):
    """{einheit: [(nummer, name, x, y, winkel, versteckt)]}; Einheit 0 = gemeinsame Pins."""
    s = symbol_flach(lib_id)
    name = lib_id.split(':')[1]
    einheiten = defaultdict(list)
    for u in findall(s, 'symbol'):
        m = re.match(r'.*_(\d+)_(\d+)$', u[1])
        einheit, stil = int(m.group(1)), int(m.group(2))
        if stil > 1:
            continue
        for p in findall(u, 'pin'):
            at = find(p, 'at')
            versteckt = Sym('hide') in p
            einheiten[einheit].append((str(find(p, 'number')[1]), str(find(p, 'name')[1]),
                                       float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0, versteckt))
    return dict(einheiten)


def symbol_rahmen(lib_id, einheit):
    """Begrenzung (xmin, ymin, xmax, ymax) in Bibliothekskoordinaten (y nach oben)."""
    s = symbol_flach(lib_id)
    xs, ys = [], []
    for u in findall(s, 'symbol'):
        m = re.match(r'.*_(\d+)_(\d+)$', u[1])
        if int(m.group(1)) not in (0, einheit) or int(m.group(2)) > 1:
            continue
        for e in u[2:]:
            if not isinstance(e, list):
                continue
            for k in ('start', 'end', 'center', 'at'):
                for sub in findall(e, k):
                    xs.append(float(sub[1])); ys.append(float(sub[2]))
            pts = find(e, 'pts')
            if pts:
                for xy in findall(pts, 'xy'):
                    xs.append(float(xy[1])); ys.append(float(xy[2]))
    if not xs:
        return (-2.54, -2.54, 2.54, 2.54)
    return (min(xs), min(ys), max(xs), max(ys))


class Bauteil:
    def __init__(self, ref, lib_id, wert, footprint, pins, blatt, felder):
        self.ref = ref
        self.lib_id = lib_id
        self.wert = wert
        self.footprint = footprint
        self.pins = pins            # {pinnummer: netz}
        self.blatt = blatt
        self.felder = felder        # z. B. {'MPN': ..., 'LCSC': ...}
        self.uuid = str(uuid.uuid4())
        self.pcb = {}               # Platzierung: x, y, rot, seite


class Platine:
    def __init__(self, name, titel):
        self.name = name
        self.titel = titel
        self.teile = []
        self.blaetter = ['Hauptblatt']
        self.blatt = 'Hauptblatt'
        self._zaehler = defaultdict(int)

    def neues_blatt(self, name):
        if name not in self.blaetter:
            self.blaetter.append(name)
        self.blatt = name

    def teil(self, praefix, lib_id, wert, footprint, pins, **felder):
        self._zaehler[praefix] += 1
        ref = f'{praefix}{self._zaehler[praefix]}'
        alle = {nr for einheit in symbol_pins(lib_id).values() for nr, *_ in einheit}
        unbekannt = set(map(str, pins)) - alle
        if unbekannt:
            raise ValueError(f'{ref} ({lib_id}): unbekannte Pins {sorted(unbekannt)}')
        b = Bauteil(ref, lib_id, wert, footprint, {str(k): v for k, v in pins.items() if v}, self.blatt, felder)
        self.teile.append(b)
        return b

    # Kurzformen für Standardbauteile
    def R(self, wert, a, b, fp='Resistor_SMD:R_0603_1608Metric', **f):
        return self.teil('R', 'Device:R', wert, fp, {1: a, 2: b}, **f)

    def C(self, wert, a, b, fp='Capacitor_SMD:C_0603_1608Metric', **f):
        return self.teil('C', 'Device:C', wert, fp, {1: a, 2: b}, **f)

    def entkoppeln(self, netz, gnd='GND', n=1, wert='100n'):
        for _ in range(n):
            self.C(wert, netz, gnd, LCSC='C14663' if wert == '100n' else '')

    def netze(self):
        n = defaultdict(list)
        for t in self.teile:
            for pin, netz in t.pins.items():
                n[netz].append((t.ref, pin))
        return dict(n)

    def pruefe(self):
        """Netze mit nur einem Anschluss sind fast immer Tippfehler."""
        fehler = [f'{netz}: nur {p}' for netz, p in self.netze().items() if len(p) < 2 and not netz.startswith('NC_')]
        return fehler
