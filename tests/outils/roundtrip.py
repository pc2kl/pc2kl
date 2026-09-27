"""Bilan de l'aller-retour : original .pc -> pc2kl -> .kl -> ktrans -> .pc recompilé.
Usage : roundtrip.py <dossier pc originaux> <dossier pc recompilés> <dossier journaux> <rapport>"""
import sys, os, glob, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from compare_pc import compare
ORIG, RT, LOG, OUT = sys.argv[1:5]
def index(root):
    d = {}
    for f in glob.glob(os.path.join(root, '*', '*', '*')):
        v, dd = f.split(os.sep)[-3:-1]
        n = os.path.splitext(os.path.basename(f))[0].lower()
        if n.endswith('_v2'): n = n[:-3]          # sources corrigés recompilés sous un autre nom
        d[(v, dd, n)] = f
    return d
O = {k: v for k, v in index(ORIG).items() if v.lower().endswith('.pc')}
R = {k: v for k, v in index(RT).items() if v.lower().endswith('.pc')}
L = index(LOG)
res = collections.Counter(); lines = []; perver = collections.defaultdict(collections.Counter)
for k in sorted(O):
    if k not in R:
        st = 'NON RECOMPILÉ'
        lg = L.get(k)
        err = ''
        if lg:
            t = open(lg, encoding='latin-1').read().replace('\r', '')
            err = ' | '.join(x.strip() for x in t.split('\n') if 'ERROR' in x or 'expected' in x.lower())[:200]
        lines.append('%s/%s/%s : %s %s' % (k + (st, err)))
    else:
        d = compare(O[k], R[k])
        st = 'IDENTIQUE' if not d else 'DIFFÉRENT'
        if d: lines.append('%s/%s/%s : %s %s' % (k + (st, '; '.join(d))))
    res[st] += 1; perver[k[0]][st] += 1
with open(OUT, 'w') as f:
    f.write('Aller-retour pc -> kl -> pc : %d programmes\n' % len(O))
    for s, n in res.most_common(): f.write('  %-14s %d\n' % (s, n))
    f.write('\nPar version :\n')
    for v in sorted(perver): f.write('  %-10s %s\n' % (v, dict(perver[v])))
    f.write('\nDétail des écarts :\n' + '\n'.join(lines) + '\n')
print(open(OUT).read()[:3000])
