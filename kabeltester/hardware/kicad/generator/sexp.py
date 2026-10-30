"""Minimaler S-Ausdruck-Parser/Schreiber für KiCad-Dateien."""
import re

_TOKEN = re.compile(r'\s*(?:(\()|(\))|("(?:[^"\\]|\\.)*")|([^\s()"]+))', re.S)


class Sym(str):
    """Unquotiertes Atom (Schlüsselwort/Zahl)."""


def parse(text):
    stack, cur = [], []
    for m in _TOKEN.finditer(text):
        lp, rp, s, a = m.groups()
        if lp:
            stack.append(cur)
            cur = []
        elif rp:
            done = cur
            cur = stack.pop()
            cur.append(done)
        elif s is not None:
            cur.append(s[1:-1].replace('\\"', '"').replace('\\\\', '\\'))
        elif a is not None:
            cur.append(Sym(a))
    return cur[0] if len(cur) == 1 else cur


def q(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'


def dump(x, ind=0):
    """Schreibt einen S-Ausdruck; Reihenfolge der Elemente bleibt erhalten."""
    if isinstance(x, list):
        if not x:
            return '()'
        if all(not isinstance(e, list) for e in x):
            return '(' + ' '.join(dump(e) for e in x) + ')'
        out = '('
        for i, e in enumerate(x):
            if isinstance(e, list):
                out += '\n' + '  ' * (ind + 1) + dump(e, ind + 1)
            else:
                out += ('' if i == 0 else ' ') + dump(e)
        return out + ')'
    if isinstance(x, Sym):
        return str(x)
    if isinstance(x, bool):
        return 'yes' if x else 'no'
    if isinstance(x, (int, float)):
        v = round(float(x), 4)
        return str(int(v)) if v == int(v) else repr(v)
    return q(x)


def find(node, key):
    for e in node:
        if isinstance(e, list) and e and e[0] == key:
            return e
    return None


def findall(node, key):
    return [e for e in node if isinstance(e, list) and e and e[0] == key]
