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
a.add_argument('--runden', type=int, default=3,
               help='kurze Freerouting-Läufe nacheinander; nach jeder Runde wird gespeichert (übersteht Abbrüche)')
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
ok = True
# Runden: jeder Lauf übernimmt das gespeicherte Ergebnis des vorigen und routet weiter.
# Nach jeder Runde wird die Platine gespeichert – ein Abbruch kostet höchstens eine Runde.
ohne_fortschritt = 0
for runde in range(0 if arg.nur_nachbearbeiten else arg.runden):
    offen = lp.offene_verbindungen()
    if offen == 0 or time.time() - t0 > arg.zeitlimit:
        break
    r0 = time.time()
    erfolg = lp.routen(arg.durchgaenge, arg.threads, arg.zeitlimit)
    lp.speichern()
    neu = lp.offene_verbindungen()
    print(f'  Runde {runde + 1}: {offen} -> {neu} offen ({(time.time() - r0) / 60:.0f} min)', flush=True)
    ok = ok and erfolg
    ohne_fortschritt = ohne_fortschritt + 1 if neu >= offen else 0
    if not erfolg or ohne_fortschritt >= 2:
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
