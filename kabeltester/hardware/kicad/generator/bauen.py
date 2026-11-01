"""Erzeugt alle KiCad-Projekte (Schaltplan, Leiterplatte, Fertigungsdaten):  python3.12 bauen.py

Optional mit Autorouting:  FREEROUTING_JAR=/pfad/freerouting-1.9.0.jar python3.12 bauen.py --routen
"""
import os, sys, json, shutil
HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import eigene_bibliothek, platinen, schaltplan, netzvergleich

ZIEL = os.path.abspath(os.path.join(HIER, '..'))
for _var, _pfad in (('KICAD7_FOOTPRINT_DIR', 'footprints'), ('KICAD7_SYMBOL_DIR', 'symbols'),
                    ('KICAD7_3DMODEL_DIR', '3dmodels')):
    os.environ.setdefault(_var, f'/usr/share/kicad/{_pfad}')


def projektdateien(ordner, name):
    vorlage = json.load(open('/usr/share/kicad/template/kicad.kicad_pro'))
    vorlage['meta']['filename'] = f'{name}.kicad_pro'
    json.dump(vorlage, open(os.path.join(ordner, f'{name}.kicad_pro'), 'w'), indent=2)
    with open(os.path.join(ordner, 'sym-lib-table'), 'w') as f:
        f.write('(sym_lib_table\n  (lib (name "kabeltester")(type "KiCad")(uri "${KIPRJMOD}/../bibliothek/kabeltester.kicad_sym")(options "")(descr "Kabeltester"))\n)\n')
    with open(os.path.join(ordner, 'fp-lib-table'), 'w') as f:
        f.write('(fp_lib_table\n  (lib (name "kabeltester")(type "KiCad")(uri "${KIPRJMOD}/../bibliothek/kabeltester.pretty")(options "")(descr "Kabeltester"))\n)\n')


def main(nur_schaltplan=False):
    eigene_bibliothek.schreibe_symbole(os.path.join(ZIEL, 'bibliothek', 'kabeltester.kicad_sym'))
    eigene_bibliothek.schreibe_footprints(os.path.join(ZIEL, 'bibliothek', 'kabeltester.pretty'))
    ergebnis = {}
    nur = sys.argv[sys.argv.index('--nur') + 1] if '--nur' in sys.argv else None
    for bau in (platinen.kanalkarte, platinen.messkarte, platinen.adapter):
        p = bau()
        if nur and p.name != nur:
            continue
        offen = p.pruefe()
        if offen:
            raise SystemExit(f'{p.name}: Netze mit nur einem Anschluss: {offen}')
        ordner = os.path.join(ZIEL, p.name)
        os.makedirs(ordner, exist_ok=True)
        projektdateien(ordner, p.name)
        root, blaetter = schaltplan.schreibe(p, ordner)
        tmp = os.path.join(ordner, '.netzliste.tmp')
        fehler = netzvergleich.vergleiche(p, os.path.join(ordner, f'{p.name}.kicad_sch'), tmp)
        os.remove(tmp)
        print(f'{p.name}: {len(p.teile)} Bauteile, {len(p.netze())} Netze, Schaltplan-Netzvergleich: '
              + ('OK' if not fehler else 'FEHLER\n  ' + '\n  '.join(fehler)))
        ergebnis[p.name] = (p, root, blaetter)
        if not nur_schaltplan:
            leiterplatte_bauen(p, root, blaetter, ordner)
    return ergebnis


def leiterplatte_bauen(p, root, blaetter, ordner):
    import leiterplatte, layouts
    m = layouts.MECH[p.name]
    lp = leiterplatte.Leiterplatte(p, root, blaetter, m['breite'], m['hoehe'], m['lagen'], ordner)
    getattr(layouts, p.name.split('_')[0])(lp)
    if p.name != 'adapter_rj45':
        lp.referenzen_ausblenden()
    probleme = lp.pruefe_platzierung()
    if probleme:
        raise SystemExit(f'{p.name}: Platzierungsfehler: {probleme[:10]}')
    if '--routen' in sys.argv:
        lp.routen()
    lp.speichern()
    lp.neu_laden_und_fuellen()
    offen = lp.offene_verbindungen()
    lp.drc()
    lp.fertigung()
    netzklassen(ordner, p.name)
    print(f'  Leiterplatte {m["breite"]:.0f} x {m["hoehe"]:.0f} mm, {m["lagen"]} Lagen, '
          f'noch zu routende Verbindungen: {offen}')


def netzklassen(ordner, name):
    """Netzklasse 'Leistung' (0,4 mm) dauerhaft im Projekt hinterlegen."""
    import leiterplatte
    pfad = os.path.join(ordner, f'{name}.kicad_pro')
    pro = json.load(open(pfad))
    ns = pro.setdefault('net_settings', {})
    klassen = ns.setdefault('classes', [])
    if not any(k.get('name') == 'Leistung' for k in klassen):
        basis = dict(klassen[0]) if klassen else {}
        basis.update({'name': 'Leistung', 'track_width': 0.4, 'clearance': 0.2, 'via_diameter': 0.7, 'via_drill': 0.35})
        klassen.append(basis)
    # Standardklasse wie in der Platine (Freerouting routet mit diesen Werten; JLCPCB kann 0,1 mm)
    for k in klassen:
        if k.get('name') == 'Default':
            k.update({'clearance': 0.15, 'track_width': 0.2, 'via_diameter': 0.6, 'via_drill': 0.3})
    ns['netclass_patterns'] = [{'netclass': 'Leistung', 'pattern': n} for n in sorted(leiterplatte.LEISTUNG)]
    json.dump(pro, open(pfad, 'w'), indent=2)


if __name__ == '__main__':
    main(nur_schaltplan='--nur-schaltplan' in sys.argv)
