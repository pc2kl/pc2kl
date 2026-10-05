"""Test du comparateur par mutations : on altère un .pc original de façon qui change le
programme, puis on vérifie que le comparateur signale une différence.
Usage : test_comparateur.py <dossier de .pc> [compare_pc | compare_pc_strict]

Mutations (une seule par fichier et par type, quand elle est applicable) :
  M1  deux variables globales de même type échangent leurs références (table usedvars)
  M2  une variable globale passe IN CMOS
  M3  configuration : %STACKSIZE, %NOPAUSE, %LOCKGROUP
  M4  nom du programme
  M5  type du premier paramètre d'une routine
  M6  deux routines locales de même signature échangent leur corps
  T0  (témoin) les cibles de deux labels sont échangées : doit être détecté par les deux comparateurs"""
import sys, os, glob, struct, collections, importlib, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', '..', 'pc2kl'))
from pcfile import PC, load, R, read_type

def layout(d):
    p = PC(d); r = R(d); L = {}
    r.u16(); r.u16(); L['name'] = r.p; r.cstr(); r.cstr(); L['attr'] = r.p
    r.p = p.vars_off; nv = r.u16(); L['vars'] = []
    for _ in range(nv):
        r.u8(); r.cstr(); fl = r.p; r.u8(); read_type(r); L['vars'].append(fl)
    nu = r.u16(); L['used'] = []
    for _ in range(nu): L['used'].append(r.p); r.u16()
    nr = r.u16(); L['rout'] = []
    for _ in range(nr):
        r.cstr(); r.u8(); off = r.p; r.u16(); read_type(r, False); np_ = r.u8(); ps = []
        for _ in range(np_): ps.append(r.p); read_type(r, False)
        L['rout'].append(dict(off=off, params=ps))
    return p, L

def swap(d, i, j, n):
    b = bytearray(d); b[i:i + n], b[j:j + n] = d[j:j + n], d[i:i + n]; return bytes(b)
def setb(d, i, v):
    b = bytearray(d); b[i:i + len(v)] = v; return bytes(b)

def mutants(d):
    p, L = layout(d); M = []
    g = collections.defaultdict(list)
    for k, vi in enumerate(p.usedvars):
        if vi < len(p.vars):
            a, n, fl, t = p.vars[vi]
            if a == 0 and not n.startswith('$'): g[(fl, repr(t))].append(k)
    for ks in g.values():
        if len(ks) >= 2: M.append(('M1 globales permutées', swap(d, L['used'][ks[0]], L['used'][ks[1]], 2))); break
    for k, (a, n, fl, t) in enumerate(p.vars):
        if a == 0 and fl != 0xfd and not n.startswith('$'): M.append(('M2 variable IN CMOS', setb(d, L['vars'][k], b'\xfd'))); break
    if not p.old:
        A = L['attr']
        M.append(('M3a %STACKSIZE', setb(d, A + 9, b'\x01\x2c')))
        M.append(('M3b %NOPAUSE', setb(d, A + 5, bytes([d[A + 5] ^ 2]))))
        M.append(('M3c %LOCKGROUP', setb(d, A + 17, b'\x00' if d[A + 17] else b'\x01')))
    M.append(('M4 nom du programme', setb(d, L['name'], b'Q' if d[L['name']] != ord('Q') else b'Z')))
    loc = [k for k, r in enumerate(p.routines) if r['mod'] == 0 and r['off'] != 0xffff]
    for k in loc:
        if L['rout'][k]['params']:
            q = L['rout'][k]['params'][0]; t = struct.unpack_from('>H', d, q)[0]
            M.append(('M5 type de paramètre', setb(d, q, struct.pack('>H', 0x0011 if t != 0x0011 else 0x0012)))); break
    sig = collections.defaultdict(list)
    for k in loc: sig[(repr(p.routines[k]['ret']), repr(p.routines[k]['params']))].append(k)
    for ks in sig.values():
        if len(ks) >= 2: M.append(('M6 corps de routines permutés', swap(d, L['rout'][ks[0]]['off'], L['rout'][ks[1]]['off'], 2))); break
    if len(p.labels) >= 2 and p.labels[0] != p.labels[1]:
        pos = p.post_off
        while d[pos] != 0xff: pos += 1
        M.append(('T0 témoin : labels permutés', swap(d, pos + 3, pos + 7, 4)))
    return [(t, m) for t, m in M if m != d]

if __name__ == '__main__':
    C = importlib.import_module(sys.argv[2] if len(sys.argv) > 2 else 'compare_pc')
    tot = collections.Counter(); ok = collections.Counter(); tmp = tempfile.mkdtemp()
    for f in sorted(glob.glob(os.path.join(sys.argv[1], '**', '*.pc'), recursive=True)):
        for tag, m in mutants(load(f)):
            g = os.path.join(tmp, 'mutant.pc'); open(g, 'wb').write(m)
            tot[tag] += 1; ok[tag] += bool([x for x in C.compare(f, g) if not x.startswith('INFO')])
    print('Comparateur : %s' % C.__name__)
    print('%-32s %9s %9s' % ('mutation', 'appliquée', 'détectée'))
    for t in sorted(tot): print('%-32s %9d %9d' % (t, tot[t], ok[t]))
