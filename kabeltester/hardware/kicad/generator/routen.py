"""Routet eine vorhandene Platine mit Freerouting und erzeugt danach DRC und Fertigungsdaten neu.

  FREEROUTING_JAR=... python3.12 routen.py kanalkarte --durchgaenge 12 --threads 0 --zeitlimit 10800
"""
import argparse, os, sys, time
HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import bauen, platinen, layouts, leiterplatte

a = argparse.ArgumentParser()
a.add_argument('name')
a.add_argument('--durchgaenge', type=int, default=30)
a.add_argument('--threads', type=int, default=1)
a.add_argument('--zeitlimit', type=int, default=5400)
arg = a.parse_args()

p = {'kanalkarte': platinen.kanalkarte, 'messkarte': platinen.messkarte, 'adapter_rj45': platinen.adapter}[arg.name]()
m = layouts.MECH[p.name]
ordner = os.path.join(bauen.ZIEL, p.name)
lp = leiterplatte.Leiterplatte.aus_datei(p, ordner, m['breite'], m['hoehe'], m['lagen'])
for z in lp.board.Zones():
    lp.flaeche_einstellen(z)
vorher = lp.offene_verbindungen()
t0 = time.time()
ok = lp.routen(arg.durchgaenge, arg.threads, arg.zeitlimit)
vias = lp.naehen()
lp.speichern()
lp.neu_laden_und_fuellen()
nachher = lp.offene_verbindungen()
lp.drc()
lp.fertigung()
print(f'{p.name}: Routing {"importiert" if ok else "OHNE Ergebnis (Zeitlimit)"} nach {(time.time() - t0) / 60:.0f} min, '
      f'offene Verbindungen {vorher} -> {nachher}, {vias} Masse-Vias')
