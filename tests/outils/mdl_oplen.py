"""Longueurs d'opcodes par principe de description minimale (MDL), à partir des seuls .pc
compilés et de leurs sources de test.

Un découpage du p-code est valide s'il respecte les ancres observables (offsets des
routines et des labels = débuts d'instruction, fin du p-code, marqueurs de ligne 3E
cohérents avec les débuts de ligne du source, règles 3F/2B). Parmi les tables valides,
on retient celle qui utilise le MOINS de valeurs d'opcode distinctes : une longueur trop
courte fait lire des octets d'opérande comme des opcodes, ce qui multiplie les valeurs
distinctes ; une longueur trop longue avale des instructions et viole les ancres.
"""
import bisect
from derive_oplen import special_len, line_starts

def prep(items):
    P = []
    for pc, src in items:
        code = bytes(pc.pcode[pc.pfx:])
        anchors = sorted({r['off'] for r in pc.routines if r['mod'] == 0 and r['off'] != 0xffff} | set(pc.labels))
        P.append((code, anchors, line_starts(src) if src else None))
    return P

def parse(code, anchors, lines, table):
    N = len(code); pos = 0; ops = []; ai = 0
    while pos < N:
        op = code[pos]
        n = special_len(code, pos)
        if n is None:
            n = table.get(op)
            if not n: return None
        while ai < len(anchors) and anchors[ai] <= pos:
            if anchors[ai] < pos: return None     # ancre au milieu d'une instruction
            ai += 1
        if ai < len(anchors) and anchors[ai] < pos + n: return None
        if op == 0x3e:
            if n != 5 or pos + 5 > N: return None
            if lines is not None:
                ln = (code[pos + 1] << 8) | code[pos + 2]; so = (code[pos + 3] << 8) | code[pos + 4]
                if lines.get(ln) != so: return None
        ops.append(op); pos += n
    if pos > N + 1: return None
    return ops

def score(P, table):
    fail = 0; used = set()
    for code, a, l in P:
        r = parse(code, a, l, table)
        if r is None: fail += 1
        else: used.update(r)
    return fail, len(used)

def descend(P, table=None, maxlen=8, log=print):
    table = dict(table or {op: 1 for op in range(256)})
    table[0x3e] = 5
    best = score(P, table)
    improved = True
    while improved:
        improved = False
        for op in range(256):
            if op in (0x3e, 0x3f, 0x2b): continue
            cur = table[op]
            for n in range(1, maxlen + 1):
                if n == cur: continue
                table[op] = n
                s = score(P, table)
                if s < best:
                    best = s; cur = n; improved = True
                    log('  %02X -> %d  (échecs %d, opcodes distincts %d)' % (op, n, s[0], s[1]))
            table[op] = cur
    return table, best


import math
from collections import Counter, defaultdict

def _H(cnt):
    n = sum(cnt.values())
    return -sum(c * math.log2(c / n) for c in cnt.values()) if n else 0.0

def mdl_cost(P, table, fail_cost=1e6):
    """Longueur de description (bits) du corpus : flux d'opcodes + colonnes d'opérandes
    (entropie empirique par (opcode, position)) + coût du modèle (8 bits par valeur
    distincte observée dans chaque colonne)."""
    ops = Counter(); cols = defaultdict(Counter); fails = 0
    for code, a, l in P:
        N = len(code); pos = 0; ok = True; ai = 0; seq = []
        while pos < N:
            op = code[pos]; n = special_len(code, pos)
            spec = n is not None
            if n is None: n = table.get(op, 1)
            while ai < len(a) and a[ai] <= pos:
                if a[ai] < pos: ok = False
                ai += 1
            if not ok or (ai < len(a) and a[ai] < pos + n) or pos + n > N + 1: ok = False; break
            if op == 0x3e:
                ln = (code[pos + 1] << 8) | code[pos + 2] if pos + 2 < N else -1
                so = (code[pos + 3] << 8) | code[pos + 4] if pos + 4 < N else -1
                if n != 5 or (l is not None and l.get(ln) != so): ok = False; break
            seq.append((op, pos, n, spec)); pos += n
        if not ok: fails += 1; continue
        for op, p0, n, spec in seq:
            ops[op] += 1
            if spec or op == 0x3e: continue
            for k in range(1, n):
                if p0 + k < N: cols[(op, k)][code[p0 + k]] += 1
    bits = _H(ops) + 8 * len(ops)
    for c in cols.values():
        bits += _H(c) + 8 * len(c)
    return fails * fail_cost + bits

def descend_mdl(P, table=None, maxlen=8, log=print, rounds=10):
    table = dict(table or {op: 1 for op in range(256)}); table[0x3e] = 5
    best = mdl_cost(P, table)
    for _ in range(rounds):
        improved = False
        for op in range(256):
            if op in (0x3e, 0x3f, 0x2b): continue
            cur = table[op]
            for n in range(1, maxlen + 1):
                if n == cur: continue
                table[op] = n
                c = mdl_cost(P, table)
                if c < best - 1e-9:
                    best = c; cur = n; improved = True
            table[op] = cur
        log('  tour : %.0f bits' % best)
        if not improved: break
    return table, best


def _file_stats(code, a, l, table):
    N = len(code); pos = 0; ai = 0; ops = Counter(); cols = Counter()
    while pos < N:
        op = code[pos]; n = special_len(code, pos)
        spec = n is not None
        if n is None: n = table.get(op, 1)
        while ai < len(a) and a[ai] <= pos:
            if a[ai] < pos: return None
            ai += 1
        if (ai < len(a) and a[ai] < pos + n) or pos + n > N + 1: return None
        if op == 0x3e:
            if n != 5 or pos + 4 >= N: return None
            ln = (code[pos + 1] << 8) | code[pos + 2]; so = (code[pos + 3] << 8) | code[pos + 4]
            if l is not None and l.get(ln) != so: return None
        ops[op] += 1
        if not spec and op != 0x3e:
            for k in range(1, n):
                if pos + k < N: cols[(op, k, code[pos + k])] += 1
        pos += n
    return ops, cols

class MDL:
    """Évaluation incrémentale de la longueur de description (voir mdl_cost)."""
    def __init__(self, P, table, fail_cost=1e6):
        self.P = P; self.table = table; self.fc = fail_cost
        self.byop = defaultdict(list)
        for i, (code, a, l) in enumerate(P):
            for b in set(code): self.byop[b].append(i)
        self.st = [None] * len(P); self.ops = Counter(); self.cols = Counter(); self.fails = 0
        for i in range(len(P)): self._add(i, _file_stats(*P[i], table))
    def _add(self, i, s, sign=1):
        if sign == 1: self.st[i] = s
        if s is None: self.fails += sign; return
        for k, v in s[0].items(): self.ops[k] += sign * v
        for k, v in s[1].items(): self.cols[k] += sign * v
    def cost(self):
        ops = {k: v for k, v in self.ops.items() if v > 0}
        bits = _H(ops) + 8 * len(ops)
        per = defaultdict(Counter)
        for (op, k, b), v in self.cols.items():
            if v > 0: per[(op, k)][b] = v
        for c in per.values(): bits += _H(c) + 8 * len(c)
        return self.fails * self.fc + bits
    def set(self, op, n):
        self.table[op] = n
        for i in self.byop.get(op, []):
            self._add(i, self.st[i], -1)
            self._add(i, _file_stats(*self.P[i], self.table))

def descend_fast(P, table=None, maxlen=8, log=print, rounds=10):
    table = dict(table or {op: 1 for op in range(256)}); table[0x3e] = 5
    M = MDL(P, table); best = M.cost()
    for _ in range(rounds):
        improved = False
        for op in range(256):
            if op in (0x3e, 0x3f, 0x2b) or op not in M.byop: continue
            cur = table[op]
            for n in range(1, maxlen + 1):
                if n == cur: continue
                M.set(op, n); c = M.cost()
                if c < best - 1e-9: best = c; cur = n; improved = True
            M.set(op, cur)
        log('  tour : %.0f bits, %d échecs' % (best, M.fails))
        if not improved: break
    return table, best, M
