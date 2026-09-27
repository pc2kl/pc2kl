"""Décompile tous les .pc de test : pc/<version>/<dossier>/*.pc -> roundtrip/kl/<version>/<dossier>/*.kl
Usage : decompiler_tout.py [dossier tests]   (par défaut : le dossier parent de outils/)"""
import sys, os, glob, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..')
PC2KL = os.path.join(HERE, '..', '..', 'pc2kl', 'pc2kl.py')
ok = err = 0
for f in sorted(glob.glob(os.path.join(ROOT, 'pc', '*', '*', '*.pc'))):
    v, d = f.split(os.sep)[-3:-1]
    out = os.path.join(ROOT, 'roundtrip', 'kl', v, d, os.path.splitext(os.path.basename(f))[0] + '.kl')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    r = subprocess.run([sys.executable, PC2KL, f, '-o', out], capture_output=True, text=True)
    if r.returncode == 0: ok += 1
    else: err += 1; print('ÉCHEC', f, r.stderr.strip()[-200:])
print('%d décompilés, %d échecs' % (ok, err))
