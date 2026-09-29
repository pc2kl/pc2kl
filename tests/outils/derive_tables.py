"""Construit karel_tables.json UNIQUEMENT à partir de programmes de test (écrits d'après
le manuel KAREL) compilés par ktrans sur un poste sous licence.

Entrée : un dossier contenant
    src/<langage|builtins>/*.kl          sources de test
    pc/<version>/<langage|builtins>/*.pc résultats de compilation
Sortie : karel_tables.json + rapport_derivation.txt

Aucune autre source d'information n'est utilisée : chaque entrée de table est déduite en
comparant un source de test et le .pc produit par le compilateur.
"""
import sys, os, re, json, glob, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'pc2kl'))
sys.path.insert(0, HERE)
from pcfile import PC, load
from derive_oplen import special_len

ROOT = sys.argv[1] if len(sys.argv) > 1 else '.'
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'karel_tables.json')
rapport = []
def log(*a):
    s = ' '.join(str(x) for x in a); rapport.append(s); print(s)

# ---------------------------------------------------------------- corpus
srcs = {}
for d in ('langage', 'builtins'):
    for f in glob.glob(os.path.join(ROOT, 'src', d, '*.kl')):
        srcs[(d, os.path.splitext(os.path.basename(f))[0].lower())] = open(f, encoding='latin-1', newline='').read()

corpus = []   # (version, dir, name, src, PC)
for f in sorted(glob.glob(os.path.join(ROOT, 'pc', '*', '*', '*.pc'))):
    ver = f.split(os.sep)[-3]; d = f.split(os.sep)[-2]
    name = os.path.splitext(os.path.basename(f))[0].lower()
    if (d, name) not in srcs: continue
    try:
        corpus.append((ver, d, name, srcs[(d, name)], PC(load(f))))
    except Exception as e:
        log('illisible', f, e)
log(len(corpus), 'programmes compilés,', len({c[0] for c in corpus}), 'versions')

# ---------------------------------------------------------------- 1. longueurs d'opcodes
# Établies par lecture comparée source / p-code (oplen_analyse.py) puis VÉRIFIÉES ici :
# chaque programme du corpus doit se découper exactement, en respectant les ancres
# observables (routines, labels, marqueurs de ligne 3E cohérents avec le source).
from oplen_analyse import OPLEN as _OA
from mdl_oplen import prep as _prep, parse as _parse
table = {k: v[0] for k, v in _OA.items()}
bad = []
for ver, d, name, src, pc in corpus:
    (code, a, l), = _prep([(pc, src)])
    if _parse(code, a, l, table) is None: bad.append('%s/%s/%s' % (ver, d, name))
log(len(table), "longueurs d'opcode ;", len(corpus) - len(bad), '/', len(corpus), 'programmes découpés exactement')
for x in bad: log('  NON DÉCOUPÉ :', x)

def ins(pc):
    code = pc.pcode[pc.pfx:]; i = 0; out = []
    while i < len(code):
        n = special_len(code, i) or table.get(code[i])
        if not n: break
        out.append((i, code[i], code[i:i + n])); i += n
    return out

def lines_of(pc):
    """instructions groupées par ligne source (marqueur 3E)"""
    cur = None; res = collections.OrderedDict()
    for off, op, b in ins(pc):
        if op == 0x3e:
            cur = (b[1] << 8) | b[2]; res.setdefault(cur, []); continue
        if cur is not None: res[cur].append((op, b))
    return res

def body_lines(src):
    L = [l.rstrip('\r') for l in src.split('\n')]; b = L.index('BEGIN') if 'BEGIN' in L else None
    return {i + 1: l.strip() for i, l in enumerate(L) if b is not None and i > b and l.strip() and not l.strip().startswith('END')}

def var_types(pc):
    return {n.upper(): ty for (_, n, _, ty) in pc.vars}

# ---------------------------------------------------------------- 2. ports d'E/S
ports = {}; int_ports = set(); conflicts = []
for ver, d, name, src, pc in corpus:
    if not name.startswith('port_'): continue
    pn = name[5:].upper()
    for ln, L in lines_of(pc).items():
        for op, b in L:
            if op in (0x19, 0x1a):
                k = b[1]
                if ports.get(k, pn) != pn: conflicts.append(('port', k, ports[k], pn, ver))
                ports[k] = pn
    if re.search(r'x\s*:\s*INTEGER', src, re.I): int_ports.add(pn)
log(len(ports), "ports d'E/S :", ', '.join('%02X=%s' % kv for kv in sorted(ports.items())))

# ---------------------------------------------------------------- 3. fichiers prédéfinis
files = {}
for ver, d, name, src, pc in corpus:
    if not name.startswith('file_'): continue
    fn = name[5:].upper(); I = ins(pc)
    for k in range(len(I) - 1):
        if I[k][1] == 0xad and I[k + 1][1] == 0x32:
            off = (I[k + 1][2][1] << 8) | I[k + 1][2][2]
            files.setdefault(off, set()).add(fn)
# plusieurs noms peuvent désigner le même fichier (synonymes) : on garde un nom canonique
file_alias = {k: sorted(v) for k, v in files.items() if len(v) > 1}
files = {k: sorted(v, key=lambda n: (n in ('INPUT',) or n.startswith('CRT'), n))[0] for k, v in files.items()}
log('synonymes :', file_alias)
log(len(files), 'fichiers prédéfinis :', ', '.join('%d=%s' % kv for kv in sorted(files.items())))

# ---------------------------------------------------------------- 4. intrinsèques (opcode 76)
intr = {}
for ver, d, name, src, pc in corpus:
    if d != 'builtins': continue
    nm = name.upper()
    I = ins(pc)
    pos76 = [k for k, (_, op, b) in enumerate(I) if op == 0x76]
    if len(pos76) != 1: continue
    ks = [I[pos76[0]][2][1]]
    # nombre d'arguments réellement empilés : un marqueur 27 par argument (tests à plat)
    nstack = sum(1 for _, op, b in I[:pos76[0]] if op == 0x27)
    vt = var_types(pc)
    ps = []
    for i in range(64):                     # paramètres v0, v1, ... du programme de test
        t = vt.get('V%d' % i)
        if t is None: break
        ps.append(['', [t[0], []]])
    rt = [vt['RES'][0], []] if 'RES' in vt else [0, []]
    hidden = nstack - len(ps)
    for _ in range(max(0, hidden)): ps.append(['', [0x10, []]])
    e = [nm, rt, ps, max(0, hidden)]
    if ks[0] in intr and intr[ks[0]][0] != nm: conflicts.append(('76', ks[0], intr[ks[0]][0], nm, ver))
    intr[ks[0]] = e
log(len(intr), 'intrinsèques (76 NN) identifiés')

# ---------------------------------------------------------------- 5. types position / VECTOR
POSF = [('x', 0x11), ('y', 0x11), ('z', 0x11), ('w', 0x11), ('p', 0x11), ('r', 0x11), ('config_data', 0x1c),
        ('ext1', 0x11), ('ext2', 0x11), ('ext3', 0x11),
        ('normal', 0x13), ('orient', 0x13), ('approach', 0x13), ('location', 0x13)]
POSF = dict(POSF)
KIND = {'X': 0x02, 'XE': 0x06, 'P': 0x01}
pos = {}; vector = {}
for ver, d, name, src, pc in corpus:
    if name != 't_posfields': continue
    h = '8' if pc.fmt >= 0x29 else '4'
    P = pos.setdefault(h, {})
    bl = body_lines(src); LL = lines_of(pc)
    soff = {}
    for ln, txt in bl.items():
        m = re.match(r'\w+\s*=\s*(\w+)\.(\w+)', txt)
        if not m: continue
        base, fld = m.group(1).upper(), m.group(2).lower()
        offs = [(b[1] << 8) | b[2] for op, b in LL.get(ln, []) if op == 0x32]
        off = offs[0] if offs else 0
        if base == 'S': soff[fld] = off
        elif base == 'V': vector[str(off)] = [fld, POSF[fld]]
        else:
            P.setdefault(str(KIND[base]), {'fields': {}})['fields'][str(off)] = [fld, POSF[fld]]
    # tailles : écart entre champs entiers consécutifs de la structure (a=0)
    seq = [('a', None), ('b', 0x02), ('c', 0x06), ('d', 0x01), ('e', 0x19), ('f', 0x29), ('g', 0x69), ('h', 0x99), ('k', 'V')]
    soff['a'] = 0
    jsz = {}
    for (f0, _), (f1, kind) in zip(seq, seq[1:]):
        sz = soff[f1] - soff[f0] - 4
        if kind == 'V': continue
        if kind in (0x02, 0x06, 0x01):
            P.setdefault(str(kind), {'fields': {}})['size'] = sz
        else:
            jsz[kind >> 4] = sz
    # JOINTPOSn : taille = base + per_axis * n (vérifié sur 1, 2, 6, 9 axes)
    per = (jsz[2] - jsz[1]); base = jsz[1] - per
    okj = all(base + per * n == s for n, s in jsz.items())
    if not okj: conflicts.append(('jointpos', h, jsz, None, ver))
    P['9'] = {'base': base, 'per_axis': per, 'fields': {}}
    for k in list(P):
        prev = P[k]
log('positions :', json.dumps(pos))
log('vector :', json.dumps(vector))

# ---------------------------------------------------------------- 6. clauses WITH, types énumérés
# Le type des variables système de mouvement est lu dans la table des types du .pc
# (structure UPR_T de $GROUP) : aucun nom ni valeur n'est inventé.
def upr_fields(pc):
    for t in pc.tdefs:
        if t['name'] == 'UPR_T':
            return {fn.upper(): ft for (fn, fl, ft) in t['fields']}
    return {}

def field_kind(pc, ft):
    code = ft[0]; hi, lo = code >> 8, code & 0xff
    if hi == 0x11 and lo < len(pc.tdefs): return pc.tdefs[lo]['name']
    if 1 <= hi <= 8: return 'pos'
    return {0x10: 'int', 0x11: 'real', 0x12: 'bool', 0x17: 'int', 0x18: 'int'}.get(code, 'int')

def const_of(b):
    return {0x9c: 0, 0x9d: 1}.get(b[0], int.from_bytes(b[1:5], 'big') if b[0] == 0x2e else None)

with_ids = {}; enums = {}
RE_W = re.compile(r'(?:\$GROUP\[\s*\d+\s*\]\.)?(\$\w+)\s*=\s*([^,]+?)\s*(?=,|\bMOVE\b)', re.I)
for ver, d, name, src, pc in corpus:
    uf = upr_fields(pc)
    if not uf: continue
    bl = body_lines(src); LL = lines_of(pc)
    for ln, txt in bl.items():
        L = LL.get(ln, [])
        m = re.match(r'WITH\s+(.*)\bMOVE\b', txt, re.I)
        if m:
            cl = RE_W.findall(m.group(1) + ' MOVE')
            ids = [b[1] for op, b in L if op == 0x02]
            if len(cl) != len(ids): continue
            for (sv, val), k in zip(cl, ids):
                sv = sv.upper()
                kd = field_kind(pc, uf[sv]) if sv in uf else None
                if with_ids.get(k, [sv])[0] != sv: conflicts.append(('WITH', k, with_ids[k][0], sv, ver))
                with_ids[k] = [sv, kd]
            continue
        m = re.match(r'\$GROUP\[\s*\d+\s*\]\.(\$\w+)\s*=\s*([A-Z_]\w*)$', txt, re.I)
        if m and m.group(2).upper() not in ('TRUE', 'FALSE') and m.group(1).upper() in uf:
            tn = field_kind(pc, uf[m.group(1).upper()])
            if tn in ('int', 'real', 'bool', 'pos') or m.group(2).upper() in var_types(pc): continue
            cs = [const_of(b) for op, b in L if op in (0x2e, 0x9c, 0x9d)]
            if not cs or cs[0] is None: continue
            E = enums.setdefault(tn, {})
            if E.get(cs[0], m.group(2).upper()) != m.group(2).upper(): conflicts.append(('enum', tn, cs[0], m.group(2), ver))
            E[cs[0]] = m.group(2).upper()
log(len(with_ids), 'clauses WITH :', ', '.join('%d=%s' % (k, v[0]) for k, v in sorted(with_ids.items())))
for tn, E in sorted(enums.items()):
    log('énuméré %s :' % tn, ', '.join('%d=%s' % kv for kv in sorted(E.items())))

for c in conflicts: log('CONFLIT', c)
json.dump({
    'source': 'Tables déduites par observation de programmes de test compilés (voir tests/)',
    'oplen': {'%02X' % k: v for k, v in sorted(table.items())},
    'intrinsics': {str(k): v for k, v in sorted(intr.items())},
    'ports': {str(k): v for k, v in sorted(ports.items())},
    'int_ports': sorted(int_ports),
    'predef_files': {str(k): v for k, v in sorted(files.items())},
    'pos': pos, 'vector': vector,
    'with_ids': {str(k): v for k, v in sorted(with_ids.items())},
    'enums': {tn: {str(k): v for k, v in sorted(E.items())} for tn, E in sorted(enums.items())},
}, open(OUT, 'w'), indent=1, ensure_ascii=False)
open(os.path.join(ROOT, 'rapport_derivation.txt'), 'w').write('\n'.join(rapport) + '\n')
