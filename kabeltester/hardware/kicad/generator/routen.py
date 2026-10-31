"""Routet eine vorhandene Platine mit Freerouting und erzeugt danach DRC und Fertigungsdaten neu.

  FREEROUTING_JAR=... python3.12 routen.py kanalkarte --durchgaenge 12 --threads 0 --zeitlimit 10800
"""
import argparse, os, sys, time
HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import bauen, platinen, layouts, leiterplatte
import pcbnew

a = argparse.ArgumentParser()
a.add_argument('name')
a.add_argument('--durchgaenge', type=int, default=30)
a.add_argument('--threads', type=int, default=1)
a.add_argument('--zeitlimit', type=int, default=5400)
a.add_argument('--nur-nachbearbeiten', action='store_true', help='nicht routen, nur Masse anbinden + Fertigung')
arg = a.parse_args()

p = {'kanalkarte': platinen.kanalkarte, 'messkarte': platinen.messkarte, 'adapter_rj45': platinen.adapter}[arg.name]()
m = layouts.MECH[p.name]
ordner = os.path.join(bauen.ZIEL, p.name)
lp = leiterplatte.Leiterplatte.aus_datei(p, ordner, m['breite'], m['hoehe'], m['lagen'])
lp.lagen_typen()
# Masseflächen auf beiden Außenlagen (verbinden viele GND-Pads direkt)
vorhanden = {(z.GetNetname(), z.GetLayerSet().Seq()[0]) for z in lp.board.Zones()}
for lage in (pcbnew.F_Cu, pcbnew.B_Cu):
    if ('GND', lage) not in vorhanden:
        lp.flaeche('GND', lage)
for z in list(lp.board.Zones()):
    if z.GetNetname() == '5VA':
        # 5VA wird Leiterbahn, In2 Signallage; die Fläche wird zur GND-Fläche auf In1
        # (Board.Remove beschädigt KiCads Python-Bindung)
        z.SetNet(lp.board.FindNet('GND'))
        z.SetLayer(pcbnew.In1_Cu)
    lp.flaeche_einstellen(z)
vorher = lp.offene_verbindungen()
t0 = time.time()
ok = True if arg.nur_nachbearbeiten else lp.routen(arg.durchgaenge, arg.threads, arg.zeitlimit)
# Nachrouten: Freerouting übernimmt das vorhandene Ergebnis und versucht die Reste
for runde in range(2):
    offen = lp.offene_verbindungen()
    print(f'  nach Runde {runde + 1}: {offen} offen', flush=True)
    if arg.nur_nachbearbeiten or not ok or offen == 0 or time.time() - t0 > arg.zeitlimit:
        break
    ok = lp.routen(max(5, arg.durchgaenge // 2), arg.threads, arg.zeitlimit) or ok
    if lp.offene_verbindungen() >= offen:
        break
vias = lp.naehen()
vias += lp.inseln_naehen()
vias += lp.inseln_naehen()
fanout = lp.masse_anbinden(nur=lp.unverbundene_pads() | lp._insel_pads)
vias += lp.inseln_naehen()
fanout += lp.masse_anbinden(nur=lp.unverbundene_pads() | lp._insel_pads)
lp.fuellen()
print(f'  Masse-Fanout: {fanout} Pads angebunden', flush=True)
lp.speichern()
lp.neu_laden_und_fuellen()
nachher = lp.offene_verbindungen()
lp.drc()
lp.fertigung()
print(f'{p.name}: Routing {"importiert" if ok else "OHNE Ergebnis (Zeitlimit)"} nach {(time.time() - t0) / 60:.0f} min, '
      f'offene Verbindungen {vorher} -> {nachher}, {vias} Masse-Vias')
