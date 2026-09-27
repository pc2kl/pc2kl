"""Génère un programme de test par built-in documenté dans le manuel KAREL.
Entrée : manual_builtins.json, produit localement par parse_manual.py depuis votre
exemplaire du manuel (non distribué)."""
import json, re, os
B = json.load(open('manual_builtins.json'))
TYMAP = [
 (r'^ARRAY( \[\*\])? OF REAL', 'ARRAY[10] OF REAL'), (r'^ARRAY( \[\*\])? OF INTEGER', 'ARRAY[10] OF INTEGER'),
 (r'^ARRAY( \[\*\])? OF STRING', 'ARRAY[10] OF STRING[40]'), (r'^ARRAY( \[\*\])? OF BOOLEAN', 'ARRAY[10] OF BOOLEAN'),
 (r'^ARRAY( \[\*\])? OF JOINTPOS', 'ARRAY[5] OF JOINTPOS'), (r'^ARRAY( \[\*\])? OF XYZWPR', 'ARRAY[5] OF XYZWPR'),
 (r'^ARRAY( \[\*\])? OF POSITION', 'ARRAY[5] OF POSITION'),
 (r'^INTEGER', 'INTEGER'), (r'^REAL', 'REAL'), (r'^BOOLEAN', 'BOOLEAN'), (r'^STRING', 'STRING[40]'),
 (r'^XYZWPREXT', 'XYZWPREXT'), (r'^XYZWPR', 'XYZWPR'), (r'^POSITION', 'POSITION'), (r'^JOINTPOS', 'JOINTPOS'),
 (r'^VECTOR', 'VECTOR'), (r'^FILE', 'FILE'), (r'^CONFIG', 'CONFIG'), (r'^PATH', 'PATH'),
]
def mapty(t):
    t = (t or '').upper().replace('  ', ' ')
    for rx, k in TYMAP:
        if re.match(rx, t): return k
    return None
os.makedirs('prog', exist_ok=True)
n = 0
for name, b in sorted(B.items()):
    order = b['args'] or list(b['params'])
    decl = []; args = []; ok = True
    for k, a in enumerate(order):
        io, ty = b['params'].get(a, ('in', None))
        kt = mapty(ty)
        if kt is None: ok = False; break
        v = 'v%d' % k
        decl.append(' %s : %s' % (v, kt)); args.append(v)
    if not ok: continue
    call = '%s(%s)' % (name, ', '.join(args)) if args else name
    body = call
    if b['ret']:
        rt = mapty(b['ret'])
        if rt is None: continue
        decl.append(' res : %s' % rt); body = 'res = ' + call
    src = 'PROGRAM T\n%%NOLOCKGROUP\nVAR\n%s\nBEGIN\n %s\nEND T\n' % ('\n'.join(decl), body)
    open('prog/%s.kl' % name, 'w').write(src); n += 1
print(n, 'programmes générés')
