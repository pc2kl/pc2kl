"""Compare deux .pc (original / recompilé après décompilation) à renommage près.

Le p-code est découpé avec la table de longueurs, les marqueurs de ligne (3E) sont ignorés,
les références de variables, de routines et de labels sont renumérotées dans l'ordre de
première apparition (équivalence à renommage près), puis les suites d'instructions sont
comparées. Les déclarations (variables globales, types) sont comparées par nom et type."""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'pc2kl'))
from pcfile import PC, load
from derive_oplen import special_len
T = {int(k, 16): v for k, v in json.load(open(os.path.join(HERE, '..', '..', 'pc2kl', 'karel_tables.json')))['oplen'].items()}
VARREF = {0x17, 0x1C, 0x21, 0x22, 0x23, 0x2D, 0x2F, 0x49, 0x4A, 0x4B, 0x4C, 0x73, 0x74, 0x75, 0x9E, 0x9F, 0xA0, 0xA2}
LABREF = {0x79, 0x7A, 0x20, 0x45, 0x40}
ROUTREF = {0xAA, 0xAB, 0x31}

def instrs(pc):
    c = bytes(pc.pcode[pc.pfx:]); i = 0; out = []
    while i < len(c):
        n = special_len(c, i) or T.get(c[i])
        if not n: out.append((i, c[i:])); break
        out.append((i, c[i:i + n])); i += n
    return out

def symbolize(pc):
    I = instrs(pc); off2idx = {}
    k = 0
    for off, b in I:
        off2idx[off] = k                  # un label sur un marqueur de ligne vise l'instruction suivante
        if b[0] != 0x3e: k += 1
    off2idx.setdefault(len(pc.pcode) - pc.pfx, k)
    ren = {}
    def r(kind, key):
        return ren.setdefault((kind, key), '%s%d' % (kind, sum(1 for x in ren if x[0] == kind)))
    out = []
    for off, b in I:
        op = b[0]
        if op == 0x3e: continue
        if op in VARREF and len(b) >= 6 and b[1] in (0x01, 0xff):
            out.append((op, r('v', b[1:6]), b[6:].hex())); continue
        if op in LABREF and len(b) >= 5:
            li = int.from_bytes(b[1:5], 'big')
            tgt = pc.labels[li] if li < len(pc.labels) else None
            out.append((op, 'L%s' % off2idx.get(tgt, tgt))); continue
        if op in ROUTREF and len(b) >= 3:
            ri = int.from_bytes(b[1:3], 'big')
            nm = pc.routines[ri]['name'] if ri < len(pc.routines) else ri
            out.append((op, 'R:' + str(nm) if ri < len(pc.routines) and pc.routines[ri]['mod'] else r('r', nm))); continue
        out.append((op, b[1:].hex()))
    return out

def decls(pc):
    g = sorted((n, t) for (a, n, fl, t) in pc.vars)
    return g

def compare(a, b):
    A, B = PC(load(a)), PC(load(b))
    diffs = []
    if decls(A) != decls(B): diffs.append('déclarations différentes')
    sa, sb = symbolize(A), symbolize(B)
    if sa != sb:
        for k, (x, y) in enumerate(zip(sa, sb)):
            if x != y: diffs.append('instruction %d : %s != %s' % (k, x, y)); break
        else: diffs.append('longueurs %d != %d' % (len(sa), len(sb)))
    return diffs

if __name__ == '__main__':
    d = compare(sys.argv[1], sys.argv[2]); print('IDENTIQUE' if not d else '\n'.join(d))
