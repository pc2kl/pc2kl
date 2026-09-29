"""Types KAREL : décodage des codes de type u16 et calcul des tailles/offsets."""
import json, os
_T = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'karel_tables.json')))
# 'pos' : pour chaque famille d'en-tête ('8' = format >= 0x29, '4' = avant),
#   taille des types position et offsets de leurs champs, établis par observation.
POSL = {h: {int(k): v for k, v in d.items()} for h, d in _T['pos'].items()}

SIMPLE = {
    0x10: 'INTEGER', 0x11: 'REAL', 0x12: 'BOOLEAN', 0x13: 'VECTOR',
    0x14: 'VIS_PROCESS', 0x15: 'MODEL', 0x16: 'CAM_SETUP',
    0x17: 'SHORT', 0x18: 'BYTE', 0x1c: 'CONFIG', 0x1d: 'FILE',
    0x1f: 'PATH', 0x00: '',
}
POSKIND = {0x01: 'POSITION', 0x02: 'XYZWPR', 0x06: 'XYZWPREXT'}

# tailles en octets (mémoire KAREL) utilisées pour calculer les offsets de champs
SIZE_SIMPLE = {0x10: 4, 0x11: 4, 0x12: 4, 0x13: 12, 0x17: 2, 0x18: 1, 0x1c: 4, 0x1d: 4}


def jpos_axes(lo):
    return lo >> 4


class TypeCtx:
    """Contexte : table des types du .pc (pour 0x11NN)."""

    def __init__(self, types=None, fmt=0x29):
        self.types = types or []
        # en-tête des types position : 8 octets à partir de V9.x (fmt 0x29), 4 avant
        self.ph = 8 if fmt >= 0x29 else 4   # liste de dict(name, fields=[(name, flag, (code,dims))], system)

    def name(self, t, dims=None):
        code = t if isinstance(t, int) else t[0]
        if dims is None and not isinstance(t, int):
            dims = t[1]
        dims = dims or []
        hi, lo = code >> 8, code & 0xff
        nd = (hi >> 5) & 3
        base_hi = hi & 0x1f
        base = self._base(base_hi, lo)
        if code == 0x001f and len(dims) == 3:
            return self.path_name(dims)
        if nd:
            ds = ','.join(str(d) if d else '' for d in dims) if any(dims) else ''
            if ds:
                return 'ARRAY[%s] OF %s' % (ds, base)
            if nd > 1:
                return 'ARRAY[%s] OF %s' % (','.join(['*'] * nd), base)
            return 'ARRAY OF %s' % base
        return base

    def path_name(self, dims):
        """PATH : dims = [en-tête standard, type PATHHEADER (0 si absent), type NODEDATA] ;
        seuls les types utilisateur (non système) sont déclarés."""
        parts = []
        for kw, t in (('PATHHEADER', dims[1]), ('NODEDATA', dims[2])):
            hi, lo = t >> 8, t & 0xff
            if hi == 0x11 and lo < len(self.types) and not self.types[lo].get('system'):
                parts.append('%s = %s' % (kw, self.types[lo]['name']))
        return 'PATH' + (' ' + ', '.join(parts) if parts else '')

    def path_node(self, t):
        """type d'un noeud de PATH (pth[i])"""
        if isinstance(t, tuple) and t[0] == 0x001f and len(t[1]) == 3:
            return (t[1][2], [])
        return None

    def path_header(self, t):
        if isinstance(t, tuple) and t[0] == 0x001f and len(t[1]) == 3:
            return (t[1][1] or t[1][0], [])
        return None

    def _base(self, hi, lo):
        if hi == 0:
            return SIMPLE.get(lo, 'TYPE_%02X' % lo)
        if hi == 0x1f:
            return 'STRING[%d]' % lo if lo else 'STRING'
        if hi == 0x11:
            if lo < len(self.types):
                return self.types[lo]['name']
            return 'TYPEREF_%d' % lo
        if 1 <= hi <= 8:
            grp = '' if hi == 1 else ' IN GROUP[%d]' % hi
            if lo in POSKIND:
                return POSKIND[lo] + grp
            if lo & 0x0f == 9:
                n = lo >> 4
                return ('JOINTPOS%d' % n if n != 9 else 'JOINTPOS') + grp
            return 'POSTYPE_%02X%s' % (lo, grp)
        return 'TYPE_%04X' % ((hi << 8) | lo)

    def kind(self, t):
        """'int','real','bool','str','pos','struct','array','other'"""
        code = t if isinstance(t, int) else t[0]
        hi, lo = code >> 8, code & 0xff
        if (hi >> 5) & 3:
            return 'array'
        hi &= 0x1f
        if hi == 0:
            return {0x10: 'int', 0x11: 'real', 0x12: 'bool', 0x17: 'int', 0x18: 'int',
                    0x13: 'vec', 0x1d: 'file', 0x1c: 'config'}.get(lo, 'other')
        if hi == 0x1f:
            return 'str'
        if hi == 0x11:
            if lo < len(self.types):
                t2 = self.types[lo]
                if t2.get('alias') is not None:
                    return self.kind(t2['alias'])
            return 'struct'
        if 1 <= hi <= 8:
            return 'pos'
        return 'other'

    def elem(self, t):
        """type élément d'un tableau (code sans dimensions)"""
        code = t if isinstance(t, int) else t[0]
        hi, lo = code >> 8, code & 0xff
        hi &= 0x1f
        return ((hi << 8) | lo, [])

    def size(self, t):
        code = t if isinstance(t, int) else t[0]
        dims = [] if isinstance(t, int) else t[1]
        hi, lo = code >> 8, code & 0xff
        nd = (hi >> 5) & 3
        if nd:
            # tableaux imbriqués : ARRAY[d1,d2,...] = en-tête (4) + d1 x ARRAY[d2,...]
            # (observé sur les locales : [2,3] OF INTEGER = 36, [2,2,2] OF INTEGER = 60)
            n = self.size(self.elem(t))
            for d in reversed(dims or [0]):
                n = 4 + d * n
            return n
        if hi == 0:
            return SIZE_SIMPLE.get(lo, 4)
        if hi == 0x1f:
            return (lo + 3 + 1) & ~1
        if hi == 0x11:
            return self.struct_layout(lo)[1]
        if 1 <= hi <= 8:
            L = POSL[str(self.ph)]
            if lo in L:
                return L[lo]['size']
            if lo & 0x0f == 9:
                return L[0x09]['base'] + L[0x09]['per_axis'] * (lo >> 4)
        return 4

    def struct_layout(self, idx):
        t = self.types[idx]
        if 'layout' in t:
            return t['layout']
        off = 0
        fl = []
        for (fname, flag, ft) in t['fields']:
            sz = self.size(ft)
            if sz >= 2 and off & 1:
                off += 1
            fl.append((fname, off, ft))
            off += sz
        if off & 1:
            off += 1
        t['layout'] = (fl, off)
        return t['layout']

    def field_at(self, t, off):
        """nom du champ à l'offset off dans le type structuré t"""
        code = t if isinstance(t, int) else t[0]
        hi, lo = code >> 8, code & 0xff
        if hi == 0x11 and lo < len(self.types):
            fl, _ = self.struct_layout(lo)
            for (n, o, ft) in fl:
                if o == off and not n.startswith('$DUMMY'):
                    return n, ft
            return None, None
        if 1 <= hi <= 8:
            f = POSL[str(self.ph)].get(lo, {}).get('fields', {}).get(str(off))
            return (f[0], (f[1], [])) if f else (None, None)
        if hi == 0 and lo == 0x13:
            f = _T['vector'].get(str(off))
            return (f[0], (f[1], [])) if f else (None, None)
        return None, None
