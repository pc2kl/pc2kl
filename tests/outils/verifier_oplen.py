"""Vérifie la table d'analyse sur tout le corpus compilé et liste les opcodes inconnus en contexte."""
import sys, os, glob, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', '..', 'pc2kl'))
from pcfile import PC, load
from mdl_oplen import prep, parse
from oplen_analyse import OPLEN
ROOT = sys.argv[1]
S = {}
for d in ('langage', 'builtins'):
    for s in glob.glob(os.path.join(ROOT, 'src', d, '*.kl')):
        S[(d, os.path.basename(s)[:-3].lower())] = open(s, encoding='latin-1').read()
T = {k: v[0] for k, v in OPLEN.items()}
bad = collections.defaultdict(list); ok = 0; tot = 0
for f in sorted(glob.glob(os.path.join(ROOT, 'pc', '*', '*', '*.pc'))):
    v, d = f.split(os.sep)[-3:-1]; n = os.path.basename(f)[:-3].lower()
    pc = PC(load(f)); (code, a, l), = prep([(pc, S[(d, n)])]); tot += 1
    if parse(code, a, l, T) is not None: ok += 1; continue
    # premier point de blocage
    pos = 0
    from derive_oplen import special_len
    while pos < len(code):
        m = special_len(code, pos) or T.get(code[pos])
        if not m: break
        pos += m
    bad[code[pos] if pos < len(code) else -1].append((v, d, n, code[max(0, pos - 12):pos + 12].hex(' ')))
print(ok, '/', tot, 'programmes découpés sans erreur')
for op, L in sorted(bad.items(), key=lambda x: -len(x[1])):
    print('opcode %s : %d programmes' % ('%02X' % op if op >= 0 else 'fin', len(L)))
    for x in L[:3]: print('   ', *x)
