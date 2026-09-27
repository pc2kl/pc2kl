"""Tests complémentaires écrits à la main d'après la syntaxe du manuel (paramètres
optionnels, types que le générateur automatique ne sait pas déduire)."""
import os
SPEC = {  # nom: (type de retour ou None, [types des paramètres])
 'CURPOS': ('XYZWPREXT', ['INTEGER', 'INTEGER', 'INTEGER']),
 'CURJPOS': ('JOINTPOS', ['INTEGER', 'INTEGER', 'INTEGER']),
 'POS': ('XYZWPR', ['REAL'] * 6 + ['CONFIG']),
 'UNPOS': (None, ['XYZWPR'] + ['REAL'] * 6 + ['CONFIG']),
 'FRAME': ('POSITION', ['POSITION', 'POSITION', 'POSITION', 'POSITION']),
 'MIRROR': ('XYZWPREXT', ['POSITION', 'POSITION', 'BOOLEAN']),
 'GET_POS_REG': ('XYZWPREXT', ['INTEGER', 'INTEGER', 'INTEGER']),
 'GET_JPOS_REG': ('JOINTPOS', ['INTEGER', 'INTEGER', 'INTEGER']),
 'SET_POS_REG': (None, ['INTEGER', 'XYZWPR', 'INTEGER', 'INTEGER']),
 'SET_JPOS_REG': (None, ['INTEGER', 'JOINTPOS', 'INTEGER', 'INTEGER']),
 'SET_EPOS_REG': (None, ['INTEGER', 'XYZWPREXT', 'INTEGER', 'INTEGER']),
 'GET_POS_TPE': ('XYZWPREXT', ['INTEGER', 'INTEGER', 'INTEGER', 'INTEGER']),
 'GET_JPOS_TPE': ('JOINTPOS', ['INTEGER', 'INTEGER', 'INTEGER', 'INTEGER']),
 'SET_POS_TPE': (None, ['INTEGER', 'INTEGER', 'XYZWPR', 'INTEGER', 'INTEGER']),
 'SET_JPOS_TPE': (None, ['INTEGER', 'INTEGER', 'JOINTPOS', 'INTEGER', 'INTEGER']),
 'SET_EPOS_TPE': (None, ['INTEGER', 'INTEGER', 'XYZWPREXT', 'INTEGER', 'INTEGER']),
 'CHECK_EPOS': (None, ['XYZWPREXT', 'POSITION', 'POSITION', 'INTEGER', 'INTEGER']),
 'CNV_JPOS_REL': (None, ['JOINTPOS', 'ARRAY[9] OF REAL', 'INTEGER']),
 'CNV_REL_JPOS': (None, ['ARRAY[9] OF REAL', 'JOINTPOS', 'INTEGER']),
 'CNV_CNF_STRG': (None, ['CONFIG', 'STRING[40]', 'INTEGER', 'INTEGER']),
 'JOINT2POS': (None, ['JOINTPOS', 'POSITION', 'POSITION', 'INTEGER', 'POSITION', 'CONFIG', 'ARRAY[6] OF REAL', 'INTEGER']),
 'POST_SEMA': (None, ['INTEGER']),
 'ARRAY_LEN': ('INTEGER', ['ARRAY[5] OF INTEGER']),
 'UNINIT': ('BOOLEAN', ['REAL']),
 'SET_FILE_ATR': (None, ['FILE', 'INTEGER', 'INTEGER']),
 'READ_KB': (None, ['FILE', 'STRING[40]', 'INTEGER', 'INTEGER', 'INTEGER', 'INTEGER', 'STRING[40]', 'INTEGER', 'INTEGER', 'INTEGER']),
 'PROG_LIST': (None, ['STRING[40]', 'INTEGER', 'INTEGER', 'INTEGER', 'ARRAY[10] OF STRING[40]', 'INTEGER', 'INTEGER', 'INTEGER']),
 'VAR_INFO': (None, ['STRING[40]', 'STRING[40]', 'BOOLEAN', 'STRING[40]', 'INTEGER', 'ARRAY[3] OF INTEGER', 'INTEGER', 'INTEGER']),
 'CREATE_VAR': (None, ['STRING[40]'] * 4 + ['INTEGER'] * 5),
 'ADD_INTPC': (None, ['ARRAY[20] OF BYTE', 'INTEGER', 'INTEGER', 'INTEGER']),
 'ADD_REALPC': (None, ['ARRAY[20] OF BYTE', 'INTEGER', 'REAL', 'INTEGER']),
 'ADD_STRINGPC': (None, ['ARRAY[20] OF BYTE', 'INTEGER', 'STRING[40]', 'INTEGER']),
 'ADD_BYNAMEPC': (None, ['ARRAY[20] OF BYTE', 'INTEGER', 'STRING[40]', 'STRING[40]', 'INTEGER']),
 'SEND_DATAPC': (None, ['INTEGER', 'ARRAY[20] OF BYTE', 'INTEGER']),
 'SET_PERCH': (None, ['JOINTPOS', 'ARRAY[6] OF REAL', 'INTEGER']),
 'APPEND_NODE': (None, ['PATH', 'INTEGER']),
 'INIT_QUEUE': (None, ['QUEUE_TYPE']),
 'APPEND_QUEUE': (None, ['INTEGER', 'QUEUE_TYPE', 'ARRAY[10] OF INTEGER', 'INTEGER', 'INTEGER']),
 'GET_QUEUE': (None, ['QUEUE_TYPE', 'ARRAY[10] OF INTEGER', 'INTEGER', 'INTEGER', 'INTEGER']),
 'MSG_PING': (None, ['STRING[40]', 'INTEGER']),
 'XML_REMTAG': (None, ['FILE', 'STRING[40]', 'INTEGER', 'INTEGER']),
}
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'builtins')
for name, (rt, ps) in SPEC.items():
    decl = [' v%d : %s' % (k, t) for k, t in enumerate(ps)]
    args = ', '.join('v%d' % k for k in range(len(ps)))
    body = '%s(%s)' % (name, args)
    if rt: decl.append(' res : %s' % rt); body = 'res = ' + body
    open(os.path.join(out, name + '.kl'), 'w').write(
        'PROGRAM T\n%%NOLOCKGROUP\nVAR\n%s\nBEGIN\n %s\nEND T\n' % ('\n'.join(decl), body))
print(len(SPEC), 'tests écrits')
