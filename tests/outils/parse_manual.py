"""Extrait du manuel KAREL (texte) la syntaxe de chaque built-in : nom, paramètres, types, retour.
Usage : parse_manual.py <manuel_converti_en_texte.txt> > manual_builtins.json
Le manuel et le fichier produit restent locaux : ils ne sont pas distribués avec ce dépôt."""
import re, json, sys
txt = open(sys.argv[1], errors='replace').read().split('\n')
out = {}
i = 0
while i < len(txt):
    m = re.match(r'\s*Syntax\s*:\s*([A-Z_][A-Z0-9_]*)\s*(\((.*))?$', txt[i])
    if m and i > 3000:
        name = m.group(1)
        sig = (m.group(3) or '')
        j = i + 1
        while sig and ')' not in sig and j < i + 6:
            sig += ' ' + txt[j].strip(); j += 1
        sig = sig.split(')')[0]
        args = [a.strip() for a in sig.split(',') if a.strip()] if m.group(2) else []
        ret = None; params = {}; env = None
        for k in range(i + 1, min(i + 60, len(txt))):
            l = txt[k].strip()
            if l.startswith('Details') or l.startswith('Syntax'):
                break
            r = re.match(r'Function Return Type\s*:\s*(.+)', l)
            if r: ret = r.group(1).strip()
            p = re.match(r'\[(in|out|in,out|in, out)\]\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+)', l)
            if p: params[p.group(2).upper()] = (p.group(1), p.group(3).strip())
            e = re.match(r'%ENVIRONMENT Group\s*:\s*(\S+)', l)
            if e: env = e.group(1)
        if name not in out:
            out[name] = dict(args=[a.upper().strip('[] ') for a in args], ret=ret, params=params, env=env)
        i = j
    i += 1
json.dump(out, sys.stdout, indent=1)
