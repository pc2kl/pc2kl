"""Déduit la longueur de chaque opcode du p-code UNIQUEMENT par observation de .pc compilés.

Contraintes utilisées (toutes observables dans les .pc et les sources) :
 - les offsets des routines (table des routines) et des labels (table des labels) sont des débuts d'instruction ;
 - le décodage doit se terminer exactement à la fin du p-code (la dernière instruction peut être tronquée d'1 octet) ;
 - l'opcode 3E (marqueur de ligne) porte un n° de ligne et l'offset du début de cette ligne dans le source ;
 - 3F = chaîne littérale (octet de longueur), 2B = liste de types terminée par 0000 (règles observées).
"""
import sys, pickle, json, threading
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'pc2kl'))
from pcfile import PC
sys.setrecursionlimit(100000)
try:
    threading.stack_size(512 * 1024 * 1024)
except ValueError:                      # refusé par certains Python Windows
    threading.stack_size(64 * 1024 * 1024)

def line_starts(src):
    b = src.encode('latin-1'); st = {}; off = 0
    for i, l in enumerate(b.split(b'\n'), 1):
        st[i] = off; off += len(l) + 1
    return st

def special_len(code, pos):
    try:
        return _special_len(code, pos)
    except IndexError:
        return 10 ** 6

def _special_len(code, pos):
    op = code[pos]
    if op == 0x3f: return 2 + code[pos + 1]
    if op == 0x2b:
        j = pos + 1
        while True:
            t = (code[j] << 8) | code[j + 1]; j += 2
            if t == 0: return j - pos
            j += 2 * ((code[j - 2] >> 5) & 3)
            if t == 0x001f: j += 6
    return None

def solve(pc, src, table):
    code = pc.pcode[pc.pfx:]
    anchors = sorted({r['off'] for r in pc.routines if r['mod'] == 0 and r['off'] != 0xffff} | set(pc.labels))
    lines = line_starts(src) if src else None
    import bisect
    def ok_here(pos, n):
        k = bisect.bisect_right(anchors, pos)
        return not (k < len(anchors) and anchors[k] < pos + n)
    def rec(pos):
        if pos >= len(code):
            return pos <= len(code) + 1
        op = code[pos]
        n = special_len(code, pos)
        cands = [n] if n else ([table[op]] if op in table else list(range(1, 9)))
        for n in cands:
            if not ok_here(pos, n): continue
            if op == 0x3e and lines is not None:
                if n != 5: continue
                ln = (code[pos + 1] << 8) | code[pos + 2]; so = (code[pos + 3] << 8) | code[pos + 4]
                if lines.get(ln) != so: continue
            new = op not in table and special_len(code, pos) is None
            if new: table[op] = n
            if rec(pos + n): return True
            if new: del table[op]
        return False
    res = [False]
    t = threading.Thread(target=lambda: res.__setitem__(0, rec(0))); t.start(); t.join()
    return res[0]


def feasible(pc, src, cands):
    """Programmation dynamique : pour chaque opcode, longueurs compatibles avec AU MOINS un
    découpage complet du p-code respectant les ancres (routines, labels, fin, lignes 3E).
    Relâchement : un même opcode peut prendre des longueurs différentes d'une occurrence à
    l'autre ; les intersections entre programmes éliminent ensuite les candidats."""
    code = pc.pcode[pc.pfx:]; N = len(code)
    anchors = sorted({r['off'] for r in pc.routines if r['mod'] == 0 and r['off'] != 0xffff} | set(pc.labels))
    import bisect
    lines = line_starts(src) if src else None
    def lens(pos):
        op = code[pos]
        n = special_len(code, pos) if pos + 1 < N else None
        L = [n] if n else sorted(cands.get(op, range(1, 9)))
        out = []
        for n in L:
            k = bisect.bisect_right(anchors, pos)
            if k < len(anchors) and anchors[k] < pos + n: continue
            if pos + n > N + 1: continue
            if op == 0x3e:
                if n != 5 or pos + 5 > N: continue
                if lines is not None:
                    ln = (code[pos + 1] << 8) | code[pos + 2]; so = (code[pos + 3] << 8) | code[pos + 4]
                    if lines.get(ln) != so: continue
            out.append(n)
        return out
    ok = [False] * (N + 2); ok[N] = ok[N + 1] = True
    E = {}
    for pos in range(N - 1, -1, -1):
        E[pos] = [n for n in lens(pos) if ok[pos + n]]
        ok[pos] = bool(E[pos])
    if not ok[0]: return None
    reach = [False] * (N + 2); reach[0] = True; used = {}
    for pos in range(N):
        if not reach[pos]: continue
        for n in E[pos]:
            reach[pos + n] = True
            if special_len(code, pos) is None:
                used.setdefault(code[pos], set()).add(n)
    return used

def propagate(items, cands):
    """items : liste de (pc, src). Réduit cands jusqu'au point fixe ; renvoie les échecs."""
    changed = True; bad = set()
    while changed:
        changed = False
        for i, (pc, src) in enumerate(items):
            u = feasible(pc, src, cands)
            if u is None: bad.add(i); continue
            for op, ls in u.items():
                cur = cands.get(op, set(range(1, 9)))
                new = cur & ls
                if new != cur:
                    cands[op] = new; changed = True
    return bad


def solve_csp(items, log=print):
    """Recherche d'une affectation opcode -> longueur unique, cohérente avec TOUS les
    programmes (propagation + retour arrière). Renvoie (table, ambigus)."""
    # dédoublonnage : beaucoup de versions produisent le même p-code
    seen = {}; uniq = []
    for pc, src in items:
        key = (bytes(pc.pcode[pc.pfx:]), tuple(pc.labels),
               tuple(r['off'] for r in pc.routines if r['mod'] == 0), src)
        if key not in seen:
            seen[key] = 1; uniq.append((pc, src))
    log(len(uniq), 'p-codes distincts')
    cands = {}
    bad = propagate(uniq, cands)
    if bad: log(len(bad), 'programmes sans découpage possible (écartés)')
    uniq = [x for i, x in enumerate(uniq) if i not in bad]
    propagate(uniq, cands)
    def dfs(c):
        open_ = [op for op, v in c.items() if len(v) > 1]
        if not open_: return c
        op = min(open_, key=lambda o: (len(c[o]), o))
        for v in sorted(c[op]):
            c2 = {k: set(x) for k, x in c.items()}; c2[op] = {v}
            if propagate(uniq, c2): continue
            r = dfs(c2)
            if r: return r
        return None
    sol = dfs(cands)
    if sol is None: return None, None
    # ambiguïtés : une autre valeur de l'opcode admet-elle aussi une solution complète ?
    amb = {}
    for op in sorted(sol):
        alts = []
        for v in sorted(cands[op] - sol[op]):
            c2 = {k: set(x) for k, x in cands.items()}; c2[op] = {v}
            if not propagate(uniq, c2) and dfs(c2): alts.append(v)
        if alts: amb[op] = alts
    return {op: next(iter(v)) for op, v in sol.items()}, amb

if __name__ == '__main__':
    table = {}
    for f in sys.argv[1:]:
        corpus = pickle.load(open(f, 'rb'))
        for name, (src, d) in corpus.items():
            if d is None: continue
            pc = PC(d)
            snap = dict(table)
            if not solve(pc, src, table):
                print('ÉCHEC', name); table = snap
    print(len(table), 'opcodes déterminés')
    json.dump({'%02X' % k: v for k, v in sorted(table.items())}, open('oplen_observed.json', 'w'), indent=0)
