"""Régénère le tableau des longueurs d'opcode de depot/docs/FORMAT.md depuis oplen_analyse.py."""
import os, re
from oplen_analyse import OPLEN
HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, '..', '..', 'docs', 'FORMAT.md')
s = open(P).read()
rows = '\n'.join('| `%02X` | %d | %s |' % (k, v[0], v[1].replace('|', '\\|')) for k, v in sorted(OPLEN.items()))
head = '| `2B` | variable | local structured variables, list of type codes ended by `0000` |\n'
a = s.index(head) + len(head); b = s.index('\n\n', a)
open(P, 'w').write(s[:a] + rows + s[b:])
print(len(OPLEN), 'lignes')
