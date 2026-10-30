"""Baut eine KiCad-7-Leiterplatte aus dem Netzlisten-Modell (benötigt python3.12 mit pcbnew).

Ablauf: Footprints laden -> Netze zuweisen -> platzieren -> Kontur/Löcher/Flächen -> Freerouting
-> Flächen füllen -> DRC -> Fertigungsdaten (Gerber, Bohrdaten, Bestückung, Stückliste, STEP).
"""
import csv
import os
import subprocess
import zipfile
import pcbnew

FP_ROOT = '/usr/share/kicad/footprints'
HIER = os.path.dirname(os.path.abspath(__file__))
EIGENE_FP = os.path.join(HIER, '..', 'bibliothek', 'kabeltester.pretty')
FREEROUTING = os.environ.get('FREEROUTING_JAR', '')

mm = pcbnew.FromMM


def V(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


LEISTUNG = {'GND', '5VA', '+5V', '3V3', 'VBUS_IN', 'VSYS', '3V3_ADP'}


class Leiterplatte:
    def __init__(self, platine, root_uuid, blatt_uuid, breite, hoehe, lagen=4, ordner=None):
        self.p = platine
        self.b, self.h = breite, hoehe
        self.ordner = ordner
        self.pfad = os.path.join(ordner, f'{platine.name}.kicad_pcb')
        self.board = pcbnew.NewBoard(self.pfad)
        self.board.SetCopperLayerCount(lagen)
        self.lagen = lagen
        self.fps = {}
        self.netze = {}
        self._regeln()
        self._laden(root_uuid, blatt_uuid)
        self._kontur()

    # ------------------------------------------------------------------
    def _regeln(self):
        ds = self.board.GetDesignSettings()
        ds.m_TrackMinWidth = mm(0.127)
        ds.m_MinClearance = mm(0.127)
        ds.m_ViasMinSize = mm(0.45)
        ds.m_MinThroughDrill = mm(0.25)
        ds.m_HoleClearance = mm(0.25)
        ds.m_CopperEdgeClearance = mm(0.3)
        nc = ds.m_NetSettings.m_DefaultNetClass
        nc.SetClearance(mm(0.15))
        nc.SetTrackWidth(mm(0.2))
        nc.SetViaDiameter(mm(0.6))
        nc.SetViaDrill(mm(0.3))
        leistung = pcbnew.NETCLASS('Leistung')
        leistung.SetClearance(mm(0.2))
        leistung.SetTrackWidth(mm(0.4))
        leistung.SetViaDiameter(mm(0.7))
        leistung.SetViaDrill(mm(0.35))
        ds.m_NetSettings.m_NetClasses['Leistung'] = leistung
        self._leistung = leistung

    def _laden(self, root_uuid, blatt_uuid):
        for netz in sorted(self.p.netze()):
            ni = pcbnew.NETINFO_ITEM(self.board, netz)
            self.board.Add(ni)
            self.netze[netz] = ni
        for t in self.p.teile:
            lib, name = t.footprint.split(':')
            lib_pfad = EIGENE_FP if lib == 'kabeltester' else os.path.join(FP_ROOT, f'{lib}.pretty')
            fp = pcbnew.FootprintLoad(lib_pfad, name)
            if fp is None:
                raise RuntimeError(f'Footprint fehlt: {t.footprint}')
            fp.SetFPID(pcbnew.LIB_ID(lib, name))
            fp.SetReference(t.ref)
            fp.SetValue(t.wert)
            blatt = '' if t.blatt == self.p.blaetter[0] else f'/{blatt_uuid[t.blatt]}'
            fp.SetPath(pcbnew.KIID_PATH(f'{blatt}/{t.uuid}'))
            for k, v in t.felder.items():
                if v:
                    fp.SetProperty(k, str(v))
            for pad in fp.Pads():
                netz = t.pins.get(str(pad.GetNumber()))
                if netz:
                    pad.SetNet(self.netze[netz])
            fp.SetPosition(V(-50, -50))
            self.board.Add(fp)
            self.fps[t.ref] = fp
        # Leistungsnetze breiter
        for n in LEISTUNG:
            if n in self.netze:
                self.netze[n].SetNetClass(self._leistung)

    def _linie(self, x1, y1, x2, y2, lage=pcbnew.Edge_Cuts, breite=0.1):
        s = pcbnew.PCB_SHAPE(self.board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(V(x1, y1))
        s.SetEnd(V(x2, y2))
        s.SetLayer(lage)
        s.SetWidth(mm(breite))
        self.board.Add(s)

    def _kontur(self):
        b, h = self.b, self.h
        for a in ((0, 0, b, 0), (b, 0, b, h), (b, h, 0, h), (0, h, 0, 0)):
            self._linie(*a)

    def text(self, s, x, y, groesse=1.5, unten=False):
        t = pcbnew.PCB_TEXT(self.board)
        t.SetText(s)
        t.SetPosition(V(x, y))
        t.SetLayer(pcbnew.B_SilkS if unten else pcbnew.F_SilkS)
        t.SetTextSize(V(groesse, groesse))
        t.SetTextThickness(mm(groesse * 0.15))
        if unten:
            t.SetMirrored(True)
        self.board.Add(t)

    # ------------------------------------------------------------------
    def rahmen(self, ref):
        """Begrenzung (Courtyard bzw. Pads) relativ zur aktuellen Position, in mm."""
        fp = self.fps[ref]
        fp.BuildCourtyardCaches() if hasattr(fp, 'BuildCourtyardCaches') else None
        lage = pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd
        poly = fp.GetCourtyard(lage)
        if poly.OutlineCount():
            bb = poly.BBox()
        else:
            bb = fp.GetBoundingBox(False, False)
        p = fp.GetPosition()
        return (pcbnew.ToMM(bb.GetLeft() - p.x), pcbnew.ToMM(bb.GetTop() - p.y),
                pcbnew.ToMM(bb.GetRight() - p.x), pcbnew.ToMM(bb.GetBottom() - p.y))

    def setze(self, ref, x, y, rot=0, unten=False, mitte='ursprung'):
        """Platziert ein Bauteil. mitte='rahmen' zentriert den Courtyard auf (x, y)."""
        fp = self.fps[ref]
        if unten and not fp.IsFlipped():
            fp.Flip(fp.GetPosition(), False)
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(V(x, y))
        if mitte == 'rahmen':
            x0, y0, x1, y1 = self.rahmen(ref)
            fp.SetPosition(V(x - (x0 + x1) / 2, y - (y0 + y1) / 2))
        elif mitte == 'pads':
            bb = fp.GetFpPadsLocalBbox() if hasattr(fp, 'GetFpPadsLocalBbox') else None
            xs = [pcbnew.ToMM(pd.GetPosition().x) for pd in fp.Pads()]
            ys = [pcbnew.ToMM(pd.GetPosition().y) for pd in fp.Pads()]
            fp.SetPosition(V(2 * x - (min(xs) + max(xs)) / 2, 2 * y - (min(ys) + max(ys)) / 2))

    def packe(self, refs, region, rot=0, unten=False, abstand=0.35, hindernisse=()):
        """Regalpackung in region=(x0, y0, x1, y1), Sperrflächen werden übersprungen.
        Gibt die nicht platzierten Referenzen zurück."""
        x0, y0, x1, y1 = region
        x, y, zeile = x0, y0, 0.0
        rest = []
        for ref in refs:
            self.setze(ref, 0, 0, rot, unten)
            a, b, c, d = self.rahmen(ref)
            w, h = c - a, d - b
            while True:
                if x + w > x1 + 1e-6:
                    x, y, zeile = x0, y + max(zeile, 0.5) + abstand, 0.0
                if y + h > y1 + 1e-6:
                    break
                stoss = [hx1 for (hx0, hy0, hx1, hy1) in hindernisse
                         if x < hx1 and hx0 < x + w and y < hy1 and hy0 < y + h]
                if not stoss:
                    break
                x = max(stoss) + abstand
            if y + h > y1 + 1e-6:
                rest.append(ref)
                continue
            self.setze(ref, x - a, y - b, rot, unten)
            x += w + abstand
            zeile = max(zeile, h)
        return rest

    def flaeche_von(self, ref, rand=0.3):
        """Absolute Courtyard-Fläche eines Bauteils (für Sperrflächen)."""
        p = self.fps[ref].GetPosition()
        a, b, c, d = self.rahmen(ref)
        px, py = pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)
        return (px + a - rand, py + b - rand, px + c + rand, py + d + rand)

    def ecken_loecher(self, refs, rand=4.0):
        pos = [(rand, rand), (self.b - rand, rand), (rand, self.h - rand), (self.b - rand, self.h - rand)]
        for ref, (x, y) in zip(refs, pos):
            self.setze(ref, x, y)
        return pos[:len(refs)]

    # ------------------------------------------------------------------
    def flaeche(self, netz, lage, rand=0.4, prio=0):
        z = pcbnew.ZONE(self.board)
        z.SetLayer(lage)
        z.SetNet(self.netze[netz])
        z.SetAssignedPriority(prio) if hasattr(z, 'SetAssignedPriority') else z.SetPriority(prio)
        z.SetMinThickness(mm(0.2))
        z.SetLocalClearance(mm(0.25))
        z.SetThermalReliefGap(mm(0.3))
        z.SetThermalReliefSpokeWidth(mm(0.35))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        o = z.Outline()
        o.NewOutline()
        for x, y in ((rand, rand), (self.b - rand, rand), (self.b - rand, self.h - rand), (rand, self.h - rand)):
            o.Append(mm(x), mm(y))
        self.board.Add(z)
        return z

    def fuellen(self):
        self.board.BuildConnectivity()
        pcbnew.ZONE_FILLER(self.board).Fill(self.board.Zones())

    def referenzen_ausblenden(self, praefixe=('R', 'C', 'D', 'F', 'Q', 'FB')):
        """Bezeichner kleiner Bauteile ausblenden (Lage steht in der Bestückungsliste)."""
        import re
        for ref, fp in self.fps.items():
            if re.sub(r'\d', '', ref) in praefixe:
                fp.Reference().SetVisible(False)

    def pruefe_platzierung(self):
        """Bauteile außerhalb der Kontur oder mit überlappendem Courtyard."""
        probleme = []
        boxen = []
        for ref, fp in self.fps.items():
            p = fp.GetPosition()
            a, b, c, d = self.rahmen(ref)
            x0, y0 = pcbnew.ToMM(p.x) + a, pcbnew.ToMM(p.y) + b
            x1, y1 = pcbnew.ToMM(p.x) + c, pcbnew.ToMM(p.y) + d
            if x0 < -0.01 or y0 < -0.01 or x1 > self.b + 0.01 or y1 > self.h + 0.01:
                if not ref.startswith('J') and not ref.startswith('BZ'):
                    probleme.append(f'{ref} außerhalb ({x0:.1f},{y0:.1f})-({x1:.1f},{y1:.1f})')
            boxen.append((ref, fp.IsFlipped(), fp.HasThroughHolePads() if hasattr(fp, 'HasThroughHolePads') else False,
                          x0, y0, x1, y1))
        for i in range(len(boxen)):
            r1, u1, t1, a0, b0, a1, b1 = boxen[i]
            for j in range(i + 1, len(boxen)):
                r2, u2, t2, c0, d0, c1, d1 = boxen[j]
                if u1 != u2 and not (t1 or t2):
                    continue
                if a0 < c1 - 0.05 and c0 < a1 - 0.05 and b0 < d1 - 0.05 and d0 < b1 - 0.05:
                    probleme.append(f'Überlappung {r1} / {r2}')
        return probleme

    # ------------------------------------------------------------------
    def speichern(self):
        pcbnew.SaveBoard(self.pfad, self.board)

    def neu_laden_und_fuellen(self):
        """Gespeicherte Platine neu laden und Flächen füllen (vermeidet veraltete Füllungen)."""
        self.board = pcbnew.LoadBoard(self.pfad)
        self.fuellen()
        pcbnew.SaveBoard(self.pfad, self.board)

    def routen(self, durchgaenge=40, threads=4, zeitlimit=3600):
        dsn = self.pfad.replace('.kicad_pcb', '.dsn')
        ses = self.pfad.replace('.kicad_pcb', '.ses')
        self.fuellen()
        if not pcbnew.ExportSpecctraDSN(self.board, dsn):
            raise RuntimeError('DSN-Export fehlgeschlagen')
        cmd = ['java', '-Djava.awt.headless=true', '-jar', FREEROUTING, '-de', dsn, '-do', ses,
               '-mp', str(durchgaenge), '-mt', str(threads)]
        log = open(self.pfad.replace('.kicad_pcb', '.freerouting.log'), 'w')
        subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, timeout=zeitlimit)
        if not os.path.exists(ses):
            raise RuntimeError('Freerouting lieferte keine SES-Datei')
        pcbnew.ImportSpecctraSES(self.board, ses)
        for f in (dsn, ses):
            os.remove(f)
        self.fuellen()

    def offene_verbindungen(self):
        self.board.BuildConnectivity()
        return self.board.GetConnectivity().GetUnconnectedCount(False)

    def drc(self):
        bericht = self.pfad.replace('.kicad_pcb', '-drc.rpt')
        pcbnew.WriteDRCReport(self.board, bericht, pcbnew.EDA_UNITS_MILLIMETRES, True)
        return bericht

    def fertigung(self):
        """Gerber + Bohrdaten (ZIP), Bestückungsliste und Stückliste im JLCPCB-Format, STEP."""
        fo = os.path.join(self.ordner, 'fertigung')
        gerb = os.path.join(fo, 'gerber')
        os.makedirs(gerb, exist_ok=True)
        lagen = 'F.Cu,In1.Cu,In2.Cu,B.Cu' if self.lagen == 4 else 'F.Cu,B.Cu'
        lagen += ',F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts'
        subprocess.run(['kicad-cli', 'pcb', 'export', 'gerbers', '--layers', lagen, '--subtract-soldermask',
                        '-o', gerb + '/', self.pfad], check=True, capture_output=True)
        subprocess.run(['kicad-cli', 'pcb', 'export', 'drill', '--format', 'excellon', '--excellon-separate-th',
                        '--generate-map', '--map-format', 'gerberx2', '-o', gerb + '/', self.pfad],
                       check=True, capture_output=True)
        zipname = os.path.join(fo, f'{self.p.name}-gerber.zip')
        with zipfile.ZipFile(zipname, 'w', zipfile.ZIP_DEFLATED) as z:
            for f in sorted(os.listdir(gerb)):
                z.write(os.path.join(gerb, f), f)
        # Bestückungsliste (CPL) im JLCPCB-Format
        pos = os.path.join(fo, f'{self.p.name}-pos.csv')
        subprocess.run(['kicad-cli', 'pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm', '--side', 'both',
                        '-o', pos, self.pfad], check=True, capture_output=True)
        zeilen = list(csv.DictReader(open(pos)))
        with open(os.path.join(fo, f'{self.p.name}-cpl-jlcpcb.csv'), 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
            for z in zeilen:
                w.writerow([z['Ref'], z['PosX'] + 'mm', z['PosY'] + 'mm',
                            'Top' if z['Side'] == 'top' else 'Bottom', z['Rot']])
        os.remove(pos)
        # Stückliste: gruppiert nach Wert + Footprint
        gruppen = {}
        for t in self.p.teile:
            if t.ref.startswith('H'):
                continue
            key = (t.wert, t.footprint, t.felder.get('MPN', ''), t.felder.get('LCSC', ''))
            gruppen.setdefault(key, []).append(t.ref)
        with open(os.path.join(fo, f'{self.p.name}-bom-jlcpcb.csv'), 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['Comment', 'Designator', 'Footprint', 'Menge', 'Hersteller-Nr.', 'LCSC Part #'])
            for (wert, fp, mpn, lcsc), refs in sorted(gruppen.items(), key=lambda g: (g[0][1], g[0][0])):
                w.writerow([wert, ','.join(sorted(refs, key=lambda r: (r.rstrip('0123456789'), int(r.lstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ') or 0)))),
                            fp.split(':')[1], len(refs), mpn, lcsc])
        # 3D-Modell
        step = os.path.join(fo, f'{self.p.name}.step')
        subprocess.run(['kicad-cli', 'pcb', 'export', 'step', '--subst-models', '--force',
                        '-o', step, self.pfad], check=True, capture_output=True)
        # STEP gezippt ablegen (Repository-Größe), Gerber nur als ZIP behalten
        with zipfile.ZipFile(step + '.zip', 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            z.write(step, os.path.basename(step))
        if not os.environ.get('STEP_BEHALTEN'):
            os.remove(step)
        import shutil
        shutil.rmtree(gerb)
        return fo
