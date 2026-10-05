"""Comparateur strict (proposition) : original .pc / .pc recompilé après décompilation.

Différences avec compare_pc.py :
  * les références aux variables GLOBALES (portée 01) sont résolues par nom via la
    table usedvars -> vars (plus de renommage) ; seules les locales/paramètres (portée ff),
    dont le nom n'est pas stocké, restent renommées par ordre de première apparition ;
  * les appels de routines sont résolus par nom (les noms de routines sont dans le .pc) ;
  * la table des routines est comparée : nom, module, type de retour, types des paramètres
    et instruction de début du corps (offset converti en indice d'instruction) ;
  * les déclarations sont comparées en entier et dans l'ordre : nom, module FROM, stockage
    (CMOS/SHADOW), type ;
  * les types utilisateur (noms et ordre des champs), le nom du programme, %COMMENT et
    les attributs de configuration (%STACKSIZE, %NOPAUSE, %LOCKGROUP...) sont comparés.
Le module *ID* (identifiant du programme) et la fin du fichier sont signalés à part
(INFO), car ils peuvent légitimement dépendre de la compilation."""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(HERE, '..', '..', 'pc2kl'), os.path.join(HERE, '..', '..', 'depot', 'pc2kl')):
    if os.path.isdir(p): sys.path.insert(0, p)
sys.path.insert(0, HERE)
from pcfile import PC, load
from compare_pc import instrs, VARREF, LABREF, ROUTREF

def gname(pc, idx):
    if 0 <= idx < len(pc.usedvars) and pc.usedvars[idx] < len(pc.vars):
        return pc.vars[pc.usedvars[idx]][1]
    return '?%d' % idx

def symbolize(pc):
    I = instrs(pc); off2idx = {}; k = 0
    for off, b in I:
        off2idx[off] = k
        if b[0] != 0x3e: k += 1
    off2idx.setdefault(len(pc.pcode) - pc.pfx, k)
    ren = {}
    def r(key): return ren.setdefault(key, 'l%d' % len(ren))
    out = []
    for off, b in I:
        op = b[0]
        if op == 0x3e: continue
        if op in VARREF and len(b) >= 6 and b[1] in (0x01, 0xff):
            if b[1] == 0x01: ref = 'G:' + gname(pc, int.from_bytes(b[2:6], 'big', signed=True))
            else: ref = r(b[1:6])
            out.append((op, ref, b[6:].hex())); continue
        if op in LABREF and len(b) >= 5:
            li = int.from_bytes(b[1:5], 'big')
            tgt = pc.labels[li] if li < len(pc.labels) else None
            out.append((op, 'L%s' % off2idx.get(tgt, tgt))); continue
        if op in ROUTREF and len(b) >= 3:
            ri = int.from_bytes(b[1:3], 'big')
            out.append((op, 'R:' + (pc.routines[ri]['name'] if ri < len(pc.routines) else str(ri)))); continue
        out.append((op, b[1:].hex()))
    return out, off2idx

def mod(pc, a): return pc.modules[a - 1] if 0 < a <= len(pc.modules) else ('' if a == 0 else '?%d' % a)

def tables(pc, off2idx):
    T = {}
    T['nom du programme'] = pc.name
    T['%COMMENT'] = pc.comment
    T['attributs (config)'] = bytes(pc.attr).hex()
    T['modules FROM'] = [m for m in pc.modules if not m.startswith('*ID*')]
    T['déclarations'] = [(n, mod(pc, a), fl, t) for (a, n, fl, t) in pc.vars]
    T['types utilisateur'] = [(t['name'], t['fields'], t['alias']) for t in pc.tdefs if not t['system']]
    T['routines'] = [(r['name'], r['mod'], r['ret'], r['params'],
                      off2idx.get(r['off'], r['off']) if r['off'] != 0xffff else None) for r in pc.routines]
    return T

def compare(a, b, info=False):
    A, B = PC(load(a)), PC(load(b))
    diffs = []
    sa, ia = symbolize(A); sb, ib = symbolize(B)
    ta, tb = tables(A, ia), tables(B, ib)
    for k in ta:
        if ta[k] != tb[k]: diffs.append('%s différent(e)s' % k)
    if sa != sb:
        for k, (x, y) in enumerate(zip(sa, sb)):
            if x != y: diffs.append('instruction %d : %s != %s' % (k, x, y)); break
        else: diffs.append('longueurs %d != %d' % (len(sa), len(sb)))
    if info:
        ida = [m for m in A.modules if m.startswith('*ID*')]; idb = [m for m in B.modules if m.startswith('*ID*')]
        if ida != idb: diffs.append('INFO *ID* %s != %s' % (ida, idb))
        if A.tail != B.tail: diffs.append('INFO fin de fichier %s != %s' % (A.tail.hex(), B.tail.hex()))
    return diffs

if __name__ == '__main__':
    d = compare(sys.argv[1], sys.argv[2], info=True); print('IDENTIQUE' if not d else '\n'.join(d))
