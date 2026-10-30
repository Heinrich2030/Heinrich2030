"""Vergleicht die von KiCad exportierte Netzliste mit dem Modell."""
import subprocess, sys, os
from sexp import parse, find, findall


def kicad_netze(sch, tmp):
    subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '-o', tmp, sch], check=True, capture_output=True)
    root = parse(open(tmp).read())
    netze = {}
    for n in findall(find(root, 'nets'), 'net'):
        name = str(find(n, 'name')[1]).lstrip('/')
        knoten = frozenset((str(find(k, 'ref')[1]), str(find(k, 'pin')[1])) for k in findall(n, 'node'))
        netze[name] = knoten
    refs = [str(find(c, 'ref')[1]) for c in findall(find(root, 'components'), 'comp')]
    return netze, refs


def vergleiche(platine, sch, tmp):
    k, refs = kicad_netze(sch, tmp)
    soll = {n: frozenset(p) for n, p in platine.netze().items()}
    ist_nach_knoten = {v: n for n, v in k.items()}
    fehler = []
    for n, knoten in soll.items():
        if knoten not in ist_nach_knoten:
            # passendes KiCad-Netz suchen
            treffer = [kn for kn, v in k.items() if v & knoten]
            fehler.append(f'Netz {n}: Soll {sorted(knoten)[:6]} – KiCad {[(t, sorted(k[t])[:6]) for t in treffer[:3]]}')
    soll_refs = {t.ref for t in platine.teile}
    if set(refs) != soll_refs:
        fehler.append(f'Referenzen weichen ab: {sorted(set(refs) ^ soll_refs)[:10]}')
    # Netze in KiCad, die im Modell nicht vorkommen (nur Einzelpins von unbeschalteten Pins sind ok)
    soll_knoten = set(soll.values())
    extra = [n for n, v in k.items() if v not in soll_knoten and len(v) > 1]
    if extra:
        fehler.append(f'Zusätzliche KiCad-Netze: {extra[:5]}')
    return fehler
