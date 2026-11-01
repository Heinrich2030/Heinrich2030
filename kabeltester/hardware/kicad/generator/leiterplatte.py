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
        self.lagen_typen()
        self.fps = {}
        self.netze = {}
        self._regeln()
        self._laden(root_uuid, blatt_uuid)
        self._kontur()

    @classmethod
    def aus_datei(cls, platine, ordner, breite, hoehe, lagen):
        """Vorhandene .kicad_pcb laden (z. B. zum Routen), ohne neu zu platzieren."""
        lp = cls.__new__(cls)
        lp.p, lp.b, lp.h, lp.lagen, lp.ordner = platine, breite, hoehe, lagen, ordner
        lp.pfad = os.path.join(ordner, f'{platine.name}.kicad_pcb')
        lp.board = pcbnew.LoadBoard(lp.pfad)
        lp.fps = {fp.GetReference(): fp for fp in lp.board.GetFootprints()}
        lp.netze = {n: lp.board.FindNet(n) for n in platine.netze()}
        return lp

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
        self.flaeche_einstellen(z)
        o = z.Outline()
        o.NewOutline()
        for x, y in ((rand, rand), (self.b - rand, rand), (self.b - rand, self.h - rand), (rand, self.h - rand)):
            o.Append(mm(x), mm(y))
        self.board.Add(z)
        return z

    def lagen_typen(self):
        """In1 = Masselage (Power, Autorouter lässt sie frei), alle weiteren Innenlagen = Signallagen."""
        n = self.board.GetCopperLayerCount()
        if n >= 4:
            self.board.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)
            for i in range(2, n - 1):
                self.board.SetLayerType(getattr(pcbnew, f'In{i}_Cu'), pcbnew.LT_SIGNAL)

    @staticmethod
    def flaeche_einstellen(z):
        """Volle Anbindung: auch Pads zwischen dichten Steckerreihen bekommen Masse."""
        z.SetMinThickness(mm(0.2))
        z.SetLocalClearance(mm(0.2))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)

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

    def leiterbahnen_aus_datei_entfernen(self):
        """Speichert, entfernt segment/arc/via-Einträge im Dateitext und lädt neu."""
        from sexp import parse, dump
        pcbnew.SaveBoard(self.pfad, self.board)
        baum = parse(open(self.pfad).read())
        baum = [e for e in baum if not (isinstance(e, list) and e and e[0] in ('segment', 'arc', 'via'))]
        with open(self.pfad, 'w') as f:
            f.write(dump(baum) + '\n')
        self.board = pcbnew.LoadBoard(self.pfad)
        self.fps = {fp.GetReference(): fp for fp in self.board.GetFootprints()}

    def nullbahnen_entfernen(self):
        """Entfernt Leiterbahnstücke ohne Länge (Start = Ende) im Dateitext und lädt neu.
        Solche Reste aus dem SES-Import bringen Freerouting beim Laden zum Stehen."""
        from sexp import parse, dump, find
        pcbnew.SaveBoard(self.pfad, self.board)
        baum = parse(open(self.pfad).read())

        def null(e):
            if not (isinstance(e, list) and e and e[0] == 'segment'):
                return False
            a, b = find(e, 'start'), find(e, 'end')
            return abs(float(a[1]) - float(b[1])) < 1e-4 and abs(float(a[2]) - float(b[2])) < 1e-4
        neu = [e for e in baum if not null(e)]
        if len(neu) == len(baum):
            return 0
        with open(self.pfad, 'w') as f:
            f.write(dump(neu) + '\n')
        self.board = pcbnew.LoadBoard(self.pfad)
        self.fps = {fp.GetReference(): fp for fp in self.board.GetFootprints()}
        return len(baum) - len(neu)

    @staticmethod
    def _freerouting(cmd, dsn, zeitlimit, ruhezeit=300):
        """Startet Freerouting auf einem eigenen virtuellen Bildschirm (Xvfb).
        Freerouting zeigt beim Einlesen teilweise gerouteter Platinen Warnfenster ("normalization of
        net ... failed") und wartet auf OK – ohne Rechenzeit zu verbrauchen. Steht die Rechenzeit, wird
        deshalb Enter geschickt (xdotool). Gibt True zurück, wenn es trotzdem hängen blieb (dann beendet)."""
        import re
        import time

        def cpu():
            try:
                pid = subprocess.run(['pgrep', '-f', '^java -jar.*' + re.escape(dsn)], capture_output=True,
                                     text=True).stdout.split()[0]
                f = open(f'/proc/{pid}/stat').read().rsplit(')', 1)[1].split()
                return int(f[11]) + int(f[12])
            except (IndexError, OSError):
                return None
        nr = next(n for n in range(150, 250) if not os.path.exists(f'/tmp/.X11-unix/X{n}')
                  and not os.path.exists(f'/tmp/.X{n}-lock'))
        env = dict(os.environ, DISPLAY=f':{nr}')
        env.pop('XAUTHORITY', None)
        xvfb = subprocess.Popen(['Xvfb', f':{nr}', '-screen', '0', '1280x1024x24', '-nolisten', 'tcp'],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        log = open(dsn.replace('.dsn', '.freerouting.log'), 'w')
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env)
        t0 = letzte_aenderung = time.time()
        stand, haengt = None, False
        try:
            while proc.poll() is None:
                time.sleep(15)
                c = cpu()
                if c is not None and c != stand:
                    stand, letzte_aenderung = c, time.time()
                elif time.time() - letzte_aenderung > 30:
                    subprocess.run(['xdotool', 'key', 'Return'], env=env, capture_output=True)
                if time.time() - t0 > zeitlimit or time.time() - letzte_aenderung > ruhezeit:
                    haengt = time.time() - t0 <= zeitlimit
                    subprocess.run(['pkill', '-f', dsn])
                    proc.wait()
        finally:
            xvfb.terminate()
            xvfb.wait()
        return haengt

    def neu_laden_und_fuellen(self):
        """Gespeicherte Platine neu laden und Flächen füllen (vermeidet veraltete Füllungen)."""
        self.board = pcbnew.LoadBoard(self.pfad)
        self.fuellen()
        pcbnew.SaveBoard(self.pfad, self.board)

    def routen(self, durchgaenge=60, threads=1, zeitlimit=5400):
        """Autorouting mit Freerouting. Gibt True zurück, wenn ein Ergebnis importiert wurde."""
        dsn = self.pfad.replace('.kicad_pcb', '.dsn')
        ses = self.pfad.replace('.kicad_pcb', '.ses')
        self.nullbahnen_entfernen()
        self.fuellen()
        if not pcbnew.ExportSpecctraDSN(self.board, dsn):
            raise RuntimeError('DSN-Export fehlgeschlagen')
        # Freerouting 1.9 braucht eine grafische Oberfläche -> virtueller Bildschirm (siehe _freerouting).
        # Optimierung mit mehr als einem Thread erzeugt laut Freerouting Abstandsfehler; 0 = aus.
        cmd = ['java', '-jar', FREEROUTING, '-de', dsn, '-do', ses,
               '-mp', str(durchgaenge), '-mt', str(threads), '-dct', '0']
        for versuch in range(2):
            if not self._freerouting(cmd, dsn, zeitlimit):
                break
            # Freerouting blieb ohne Rechenzeit stehen (passiert gelegentlich beim Laden) -> neu starten
            print(f'  Freerouting hing, Versuch {versuch + 2}', flush=True)
        ok = os.path.exists(ses)
        if ok:
            # Freerouting liefert alle Leiterbahnen (auch bereits vorhandene) -> vorher entfernen
            # Alte Leiterbahnen in der Datei entfernen (Board.Remove beschädigt KiCads
            # Python-Bindung), neu laden und das vollständige Ergebnis importieren
            self.leiterbahnen_aus_datei_entfernen()
            self.ses_importieren(ses)
            os.remove(ses)
        os.remove(dsn)
        self.fuellen()
        return ok

    def ses_importieren(self, ses):
        """Liest Leiterbahnen und Vias aus einer Freerouting-SES-Datei (KiCad 7 kann das in
        Python nicht selbst). Koordinaten: Einheit laut (resolution), y gespiegelt."""
        import re
        from sexp import parse, find, findall
        root = parse(open(ses).read())
        routes = find(root, 'routes')
        res = find(routes, 'resolution')
        einheit = {'um': 0.001, 'mm': 1.0, 'mil': 0.0254, 'inch': 25.4}[str(res[1])] / float(res[2])
        lagen = {self.board.GetLayerName(l): l for l in range(pcbnew.PCB_LAYER_ID_COUNT)}

        def pt(x, y):
            return pcbnew.VECTOR2I(mm(float(x) * einheit), mm(-float(y) * einheit))
        bahnen = vias = 0
        for netz in findall(find(routes, 'network_out'), 'net'):
            ni = self.board.FindNet(str(netz[1]))
            for w in findall(netz, 'wire'):
                pfad = find(w, 'path')
                lage = lagen[str(pfad[1])]
                breite = mm(float(pfad[2]) * einheit)
                k = pfad[3:]
                for i in range(0, len(k) - 2, 2):
                    if k[i] == k[i + 2] and k[i + 1] == k[i + 3]:
                        continue  # Stück ohne Länge
                    t = pcbnew.PCB_TRACK(self.board)
                    t.SetStart(pt(k[i], k[i + 1]))
                    t.SetEnd(pt(k[i + 2], k[i + 3]))
                    t.SetWidth(breite)
                    t.SetLayer(lage)
                    t.SetNet(ni)
                    self.board.Add(t)
                    bahnen += 1
            for v in findall(netz, 'via'):
                m = re.search(r'_(\d+):(\d+)_um', str(v[1]))
                via = pcbnew.PCB_VIA(self.board)
                via.SetPosition(pt(v[2], v[3]))
                via.SetWidth(mm(int(m.group(1)) / 1000))
                via.SetDrill(mm(int(m.group(2)) / 1000))
                via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                via.SetViaType(pcbnew.VIATYPE_THROUGH)
                via.SetNet(ni)
                self.board.Add(via)
                vias += 1
        return bahnen, vias

    def naehen(self, netz='GND', raster=5.0, abstand=0.35, rand=1.2):
        """Masse-Durchkontaktierungen im Raster setzen, wo kein fremdes Kupfer in der Nähe ist.
        Verbindet die Masseflächen aller Lagen (auch Inseln zwischen Leiterbahnen)."""
        import math
        ni = self.board.FindNet(netz)
        via_r = 0.3            # Via 0,6 / 0,3 mm
        hindernisse = []       # (art, daten) in mm
        for t in self.board.GetTracks():
            if t.GetNetname() == netz and t.Type() != pcbnew.PCB_VIA_T:
                continue
            if t.Type() == pcbnew.PCB_VIA_T:
                p = t.GetPosition()
                hindernisse.append(('kreis', pcbnew.ToMM(p.x), pcbnew.ToMM(p.y), pcbnew.ToMM(t.GetWidth()) / 2))
            else:
                a, b = t.GetStart(), t.GetEnd()
                hindernisse.append(('linie', pcbnew.ToMM(a.x), pcbnew.ToMM(a.y), pcbnew.ToMM(b.x), pcbnew.ToMM(b.y),
                                    pcbnew.ToMM(t.GetWidth()) / 2))
        for fp in self.board.GetFootprints():
            for pad in fp.Pads():
                bb = pad.GetBoundingBox()
                bohrung = pad.GetDrillSize().x > 0
                if pad.GetNetname() == netz and not bohrung:
                    continue
                hindernisse.append(('box', pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()),
                                    pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())))
        def frei(x, y):
            m = via_r + abstand
            for h in hindernisse:
                if h[0] == 'kreis':
                    if math.hypot(x - h[1], y - h[2]) < h[3] + m:
                        return False
                elif h[0] == 'box':
                    if h[1] - m < x < h[3] + m and h[2] - m < y < h[4] + m:
                        return False
                else:
                    _, x1, y1, x2, y2, r = h
                    dx, dy = x2 - x1, y2 - y1
                    l2 = dx * dx + dy * dy
                    t = 0 if l2 == 0 else max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / l2))
                    if math.hypot(x - x1 - t * dx, y - y1 - t * dy) < r + m:
                        return False
            return True
        n = 0
        y = rand
        while y <= self.h - rand:
            x = rand + (raster / 2 if int(round(y / raster)) % 2 else 0)
            while x <= self.b - rand:
                if frei(x, y):
                    v = pcbnew.PCB_VIA(self.board)
                    v.SetPosition(V(x, y))
                    v.SetWidth(mm(0.6))
                    v.SetDrill(mm(0.3))
                    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                    v.SetViaType(pcbnew.VIATYPE_THROUGH)
                    v.SetNet(ni)
                    self.board.Add(v)
                    hindernisse.append(('kreis', x, y, raster / 2 - via_r - abstand))
                    n += 1
                x += raster
            y += raster
        return n

    def unverbundene_pads(self, netz='GND'):
        """(Referenz, Pad) aller Pads des Netzes, die der DRC als unverbunden meldet."""
        import re
        bericht = self.drc()
        treffer = set()
        for m in re.finditer(r'Pad (\S+) \[' + re.escape(netz) + r'\] of (\S+) on', open(bericht).read()):
            treffer.add((m.group(2), m.group(1)))
        return treffer

    def masse_anbinden(self, netz='GND', via_d=0.6, bohr=0.3, bahn=0.25, abstand=0.23, nur=None):
        """Fanout: jedes SMD-Pad am Massenetz bekommt eine kurze Leitung zu einem Via in die
        Masselage (Freerouting überlässt Flächennetze der Fläche und setzt diese Vias nicht)."""
        import math
        ni = self.board.FindNet(netz)
        hind = []
        for t in self.board.GetTracks():
            if t.GetNetname() == netz:
                continue
            if t.Type() == pcbnew.PCB_VIA_T:
                p = t.GetPosition()
                hind.append(('k', pcbnew.ToMM(p.x), pcbnew.ToMM(p.y), pcbnew.ToMM(t.GetWidth()) / 2, None))
            else:
                a, b = t.GetStart(), t.GetEnd()
                hind.append(('l', pcbnew.ToMM(a.x), pcbnew.ToMM(a.y), pcbnew.ToMM(b.x), pcbnew.ToMM(b.y),
                             pcbnew.ToMM(t.GetWidth()) / 2, t.GetLayer()))
        pads = []
        for fp in self.board.GetFootprints():
            for pad in fp.Pads():
                bb = pad.GetBoundingBox()
                box = (pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()))
                tht = pad.GetDrillSize().x > 0
                lage = None if tht else (pcbnew.B_Cu if pad.IsOnLayer(pcbnew.B_Cu) else pcbnew.F_Cu)
                if pad.GetNetname() == netz and not tht:
                    if nur is None or (fp.GetReference(), str(pad.GetNumber())) in nur:
                        pads.append((pad, box, lage))
                elif pad.GetNetname() != netz or tht:
                    hind.append(('b',) + box + (lage,))

        def seg_dist(px, py, x1, y1, x2, y2):
            dx, dy = x2 - x1, y2 - y1
            l2 = dx * dx + dy * dy
            t = 0 if l2 == 0 else max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / l2))
            return math.hypot(px - x1 - t * dx, py - y1 - t * dy)

        def frei(x, y, r, lage):
            """Kreis (x, y, r) frei von fremdem Kupfer; lage None = alle Lagen (Via)."""
            if not (0.8 < x < self.b - 0.8 and 0.8 < y < self.h - 0.8):
                return False
            for h in hind:
                if h[0] == 'k':
                    if math.hypot(x - h[1], y - h[2]) < h[3] + r + abstand:
                        return False
                elif h[0] == 'l':
                    if lage is not None and h[6] != lage:
                        continue
                    if seg_dist(x, y, h[1], h[2], h[3], h[4]) < h[5] + r + abstand:
                        return False
                else:
                    if lage is not None and h[5] is not None and h[5] != lage:
                        continue
                    if h[1] - r - abstand < x < h[3] + r + abstand and h[2] - r - abstand < y < h[4] + r + abstand:
                        return False
            return True

        masse_vias = [(pcbnew.ToMM(t.GetPosition().x), pcbnew.ToMM(t.GetPosition().y)) for t in self.board.GetTracks()
                      if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == netz]
        n = 0
        for pad, box, lage in pads:
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            halb = max(box[2] - box[0], box[3] - box[1]) / 2
            gesetzt = False
            # Kandidaten: vorhandene Masse-Vias (nur Leitung nötig), dann neue Via-Positionen
            kandidaten = sorted((math.hypot(vx - cx, vy - cy), vx, vy, False) for vx, vy in masse_vias
                                if math.hypot(vx - cx, vy - cy) < 4.0)
            for i in range(12):
                dist = halb + 0.5 + i * 0.25
                for w in range(0, 360, 15):
                    kandidaten.append((dist + 10, cx + dist * math.cos(math.radians(w)),
                                       cy + dist * math.sin(math.radians(w)), True))
            for _, vx, vy, neu in kandidaten:
                if True:
                    if neu and not frei(vx, vy, via_d / 2, None):
                        continue
                    # Leitung vom Padrand zum Via prüfen (Stützpunkte)
                    ok = True
                    for k in range(1, 8):
                        f = k / 8
                        if not frei(cx + (vx - cx) * f, cy + (vy - cy) * f, bahn / 2, lage):
                            # innerhalb des eigenen Pads ist erlaubt
                            px, py = cx + (vx - cx) * f, cy + (vy - cy) * f
                            if not (box[0] <= px <= box[2] and box[1] <= py <= box[3]):
                                ok = False
                                break
                    if not ok:
                        continue
                    if neu:
                        v = pcbnew.PCB_VIA(self.board)
                        v.SetPosition(V(vx, vy)); v.SetWidth(mm(via_d)); v.SetDrill(mm(bohr))
                        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetViaType(pcbnew.VIATYPE_THROUGH)
                        v.SetNet(ni)
                        self.board.Add(v)
                        masse_vias.append((vx, vy))
                    t = pcbnew.PCB_TRACK(self.board)
                    t.SetStart(V(cx, cy)); t.SetEnd(V(vx, vy)); t.SetWidth(mm(bahn)); t.SetLayer(lage); t.SetNet(ni)
                    self.board.Add(t)
                    hind.append(('l', cx, cy, vx, vy, bahn / 2, lage))
                    n += 1
                    gesetzt = True
                    break
        return n

    def inseln_naehen(self, netz='GND', via_d=0.6, abstand=0.23, raster=0.25):
        """Setzt in jede Insel der Außenlagen-Masseflächen ein Via (falls sie noch keins hat).
        Inseln ohne Platz merken sich ihre GND-Pads in self._insel_pads (für masse_anbinden)."""
        import math
        self._insel_pads = set()
        self.fuellen()
        ni = self.board.FindNet(netz)
        r = via_d / 2
        # fremdes Kupfer auf allen Lagen
        hind = []
        for t in self.board.GetTracks():
            if t.GetNetname() == netz:
                continue
            if t.Type() == pcbnew.PCB_VIA_T:
                p = t.GetPosition()
                hind.append(('k', pcbnew.ToMM(p.x), pcbnew.ToMM(p.y), pcbnew.ToMM(t.GetWidth()) / 2))
            else:
                a, b = t.GetStart(), t.GetEnd()
                hind.append(('l', pcbnew.ToMM(a.x), pcbnew.ToMM(a.y), pcbnew.ToMM(b.x), pcbnew.ToMM(b.y),
                             pcbnew.ToMM(t.GetWidth()) / 2))
        for fp in self.board.GetFootprints():
            for pad in fp.Pads():
                if pad.GetNetname() == netz and pad.GetDrillSize().x == 0:
                    continue
                bb = pad.GetBoundingBox()
                hind.append(('b', pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()),
                             pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())))

        def frei(x, y):
            m = r + abstand
            for h in hind:
                if h[0] == 'k':
                    if math.hypot(x - h[1], y - h[2]) < h[3] + m:
                        return False
                elif h[0] == 'b':
                    if h[1] - m < x < h[3] + m and h[2] - m < y < h[4] + m:
                        return False
                else:
                    _, x1, y1, x2, y2, w = h
                    dx, dy = x2 - x1, y2 - y1
                    l2 = dx * dx + dy * dy
                    t = 0 if l2 == 0 else max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / l2))
                    if math.hypot(x - x1 - t * dx, y - y1 - t * dy) < w + m:
                        return False
            return True
        vias = [(t.GetPosition().x, t.GetPosition().y) for t in self.board.GetTracks()
                if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == netz]
        n = 0
        for z in self.board.Zones():
            lage = z.GetLayerSet().Seq()[0]
            if z.GetNetname() != netz or lage not in (pcbnew.F_Cu, pcbnew.B_Cu):
                continue
            polys = z.GetFilledPolysList(lage)
            for i in range(polys.OutlineCount()):
                umriss = polys.Outline(i)
                einzel = pcbnew.SHAPE_POLY_SET()
                einzel.AddOutline(umriss)
                if any(einzel.Contains(pcbnew.VECTOR2I(x, y)) for x, y in vias):
                    continue
                bb = umriss.BBox()
                x0, y0 = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())
                x1, y1 = pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())
                gefunden = False
                y = y0
                while y <= y1 and not gefunden:
                    x = x0
                    while x <= x1:
                        # Via-Kreis muss ganz in der Insel liegen
                        if all(einzel.Contains(V(x + r * math.cos(a), y + r * math.sin(a)))
                               for a in [k * math.pi / 4 for k in range(8)]) and \
                                einzel.Contains(V(x, y)) and frei(x, y):
                            v = pcbnew.PCB_VIA(self.board)
                            v.SetPosition(V(x, y)); v.SetWidth(mm(via_d)); v.SetDrill(mm(0.3))
                            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetViaType(pcbnew.VIATYPE_THROUGH)
                            v.SetNet(ni)
                            self.board.Add(v)
                            vias.append((mm(x), mm(y)))
                            hind.append(('k', x, y, r))
                            n += 1
                            gefunden = True
                            break
                        x += raster
                    y += raster
                if not gefunden:
                    # Kein Platz für ein Via: GND-Pads in dieser Insel per Fanout anbinden
                    for fp in self.board.GetFootprints():
                        for pad in fp.Pads():
                            if pad.GetNetname() == netz and einzel.Contains(pad.GetPosition()):
                                self._insel_pads.add((fp.GetReference(), str(pad.GetNumber())))
        self.fuellen()
        return n

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
        lagen = ','.join(['F.Cu'] + [f'In{i}.Cu' for i in range(1, self.lagen - 1)] + ['B.Cu'])
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
