#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pc2kl - Décompilateur FANUC KAREL p-code (.pc) -> source (.kl)

Usage :  python pc2kl.py fichier.pc [-o sortie.kl] [--asm] [--no-lines]

Formats pris en charge : .pc produits par ktrans V6.40 à V10.13 (identifiants 0x22 à 0x2A).
Les noms des variables locales et des paramètres ne sont pas stockés dans le .pc :
ils sont régénérés (p1, p2..., l_3...). Les CONST sont remplacées par leur valeur,
les commentaires sont perdus.
"""
import sys, os, re, struct, json, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pcfile import PC, load, R, norm_type
from karel_types import TypeCtx

# Tables établies par observation de programmes compilés (voir tests/outils/derive_tables.py).
_T = json.load(open(os.path.join(HERE, 'karel_tables.json')))
OPLEN = {int(k, 16): v for k, v in _T['oplen'].items()}
INTRINSICS = {int(k): v for k, v in _T['intrinsics'].items()}
PORTS = {int(k): v for k, v in _T['ports'].items()}
PORT_KIND = {n: ('int' if n in _T['int_ports'] else 'bool') for n in PORTS.values()}
PREDEF_FILES = {int(k): v for k, v in _T['predef_files'].items()}
WITH_IDS = {int(k): tuple(v) for k, v in _T['with_ids'].items()}   # clauses WITH d'un MOVE
ENUMS = {k: {int(a): b for a, b in v.items()} for k, v in _T['enums'].items()}   # MOTYPE_E, TERMTYPE_E...
# Champs d'un CONFIG, stocké en un mot de 32 bits : (bit de départ, largeur) -> nom (opcodes A4/A5).
CFG_FIELDS = {(0, 8): 'cfg_turn_no1', (8, 8): 'cfg_turn_no2', (16, 8): 'cfg_turn_no3',
              (24, 1): 'cfg_flip', (25, 1): 'cfg_left', (26, 1): 'cfg_up', (27, 1): 'cfg_front'}

# ---------------------------------------------------------------- désassemblage

class Ins:
    __slots__ = ('off', 'op', 'b', 'idx')

    def __init__(self, off, op, b):
        self.off = off; self.op = op; self.b = b; self.idx = 0

    def u8(self, i=1): return self.b[i]
    def u16(self, i=1): return struct.unpack_from('>H', self.b, i)[0]
    def s16(self, i=1): return struct.unpack_from('>h', self.b, i)[0]
    def u32(self, i=1): return struct.unpack_from('>I', self.b, i)[0]
    def s32(self, i=1): return struct.unpack_from('>i', self.b, i)[0]

    def __repr__(self):
        if self.op == -1:
            return '%04x: %s   <-- ?? opcode %02X inconnu (octets non décodés)' % (self.off, self.b.hex(' '), self.b[0])
        return '%04x: %s' % (self.off, self.b.hex(' '))


def oplen(code, i):
    op = code[i]
    if op == 0x3f:
        return 2 + code[i + 1]
    if op == 0x2b:                       # déclaration des locales structurées
        j = i + 1
        while True:
            t = (code[j] << 8) | code[j + 1]
            if t == 0:
                return j + 2 - i
            j += 2
            nd = (code[j - 2] >> 5) & 3
            j += 2 * nd
            if t == 0x001f:
                j += 6
    return OPLEN.get(op, 0)


def _marker_ok(code, p, prev):
    """3E llll oooo plausible à la position p, après le marqueur précédent prev=(ligne, offset)."""
    if p + 5 > len(code) or code[p] != 0x3e:
        return None
    ln, so = struct.unpack_from('>HH', code, p + 1)
    if prev is not None:
        pl, po = prev
        dso = (so - po) % 0x10000
        if not (pl <= ln <= pl + 400) or not (dso < 20000) or (dso == 0 and ln != pl):
            return None                        # (un même marqueur peut être répété : IF, WHILE...)
    return ln, so


def _resync(code, i, base, bounds, prev):
    """Opcode inconnu à i : longueur inconnue. Cherche la prochaine frontière d'instruction sûre :
    une étiquette ou une entrée de routine (certaines), sinon un marqueur de ligne 3E plausible
    à partir duquel le décodage reprend proprement. Renvoie la position de reprise."""
    nb = min([b + base for b in bounds if b + base > i] or [len(code)])
    for p in range(i + 1, nb):
        m = _marker_ok(code, p, prev)
        if m is None:
            continue
        # vérification : décoder la suite jusqu'au marqueur suivant, une frontière ou un autre inconnu
        j = p + 5; ok = True; last = m
        for _ in range(200):
            if j >= nb:
                ok = (j == nb); break
            if code[j] == 0x3e:
                ok = _marker_ok(code, j, last) is not None; break
            n = oplen(code, j)
            if n == 0:
                break                              # autre opcode inconnu : on s'arrête là
            j += n
        if ok:
            return p
    return nb


def disasm(pcode, base=2, bounds=None, nlabels=0):
    """bounds : offsets certains de début d'instruction (étiquettes, routines). S'il est fourni,
    un opcode inconnu ne termine plus le désassemblage : ses octets sont regroupés dans une
    pseudo-instruction (op = -1) jusqu'à la prochaine frontière retrouvée."""
    out = []
    i = base
    prev = None
    while i < len(pcode):
        n = oplen(pcode, i)
        if n == 0:                         # opcode jamais observé
            if bounds is None:
                out.append(Ins(i - base, pcode[i], pcode[i:i + 1]))
                out[-1].op = -1
                break
            j = _resync(pcode, i, base, bounds, prev)
            # un saut (79/7A étiquette) en fin de zone est conservé : il porte la structure IF/WHILE
            k = j
            if j - i >= 6 and pcode[j - 5] in (0x79, 0x7a) and pcode[j - 4:j - 2] == b'\x00\x00' \
                    and struct.unpack_from('>I', pcode, j - 4)[0] < nlabels:
                k = j - 5
            out.append(Ins(i - base, pcode[i], pcode[i:k]))
            out[-1].op = -1
            if k < j:
                out.append(Ins(k - base, pcode[k], pcode[k:j]))
            i = j
            continue
        b = pcode[i:i + n]
        if len(b) < n:
            pad = bytes(n - len(b))
            if pcode[i] == 0x7f and len(b) == 3 and b[2] == 0xff:
                pad = b'\xfd'                  # fin de fonction tronquée
            b = b + pad
        if pcode[i] == 0x3e and len(b) == 5:
            prev = struct.unpack_from('>HH', b, 1)
        out.append(Ins(i - base, pcode[i], b))
        i += n
    for k, x in enumerate(out):
        x.idx = k
    return out


# ---------------------------------------------------------------- expressions

PREC_REL, PREC_ADD, PREC_MUL, PREC_POS, PREC_UN, PREC_ATOM = 1, 2, 3, 4, 5, 6
HINTS = {}
NEGCONST = {}      # constantes négatives pliées par le compilateur (ne peuvent venir que d'un CONST)


def negconst(v):
    if v not in NEGCONST:
        NEGCONST[v] = 'CST_M' + v[1:].replace('.', '_').replace('-', 'M').replace('+', '')
    return NEGCONST[v]


def fmt_real(v):
    b = struct.pack('>f', v)
    for p in range(1, 10):
        s = '%.*g' % (p, v)
        try:
            if struct.pack('>f', float(s)) == b:
                break
        except OverflowError:              # arrondi au-delà de FLT_MAX (ex. 3.403E38)
            continue
    if 'e' in s or 'E' in s:
        m, e = s.lower().split('e')
        if '.' not in m:
            m += '.0'
        return '%sE%d' % (m, int(e))
    if '.' not in s and 'inf' not in s and 'nan' not in s:
        s += '.0'
    return s


class E:
    """noeud d'expression"""
    def __init__(self, text=None, prec=PREC_ATOM, kind=None, ty=None, addr=False):
        self.text = text; self.prec = prec; self.kind = kind; self.ty = ty; self.addr = addr

    def render(self, hint=None):
        return self.text

    def __repr__(self):
        return '<E %s:%s>' % (self.render(), self.kind)


class Const(E):
    def __init__(self, raw):
        E.__init__(self, None, PREC_ATOM, None)
        self.raw = raw & 0xffffffff

    def render(self, hint=None):
        k = hint or self.kind
        if k == 'real':
            r = fmt_real(struct.unpack('>f', struct.pack('>I', self.raw))[0])
            if r.startswith('-') and NEGCONST is not None:
                return negconst(r)
            return r
        if k == 'bool' and self.raw in (0, 1):
            return 'TRUE' if self.raw else 'FALSE'
        v = struct.unpack('>i', struct.pack('>I', self.raw))[0]
        if v < 0 and NEGCONST is not None:
            return negconst(str(v))
        return str(v)

    @property
    def neg(self):
        return self.raw & 0x80000000 and self.kind != 'real'


class Marker(E):
    def __init__(self):
        E.__init__(self, '<27>')


class Motion(E):
    def __init__(self, grp):
        E.__init__(self, '<MOVE>')
        self.grp = grp; self.parts = []; self.nowait = False
        self.withs = []            # (nom système, groupe, valeur)


class CondN(E):
    def __init__(self, kind, num=None, with_=None):
        E.__init__(self, '<COND>')
        self.ckind = kind          # 'WAIT' ou 'COND'
        self.num = num; self.with_ = with_
        self.clauses = []          # [ [conds], [actions], or_flag ]
        self.pending_or = False
        self.done = False

    def clause(self):
        if not self.clauses:
            self.clauses.append([[], [], False])
        return self.clauses[-1]


class FileN(E):
    def __init__(self, text):
        E.__init__(self, text, PREC_ATOM, 'file')
        self.items = []
        self.mode = None


def txt(e, hint=None):
    if hint and isinstance(e, E) and getattr(e, 'lkey', None) is not None:
        HINTS.setdefault(e.lkey, set()).add(hint)
    if isinstance(e, E):
        return e.render(hint)
    return str(e)


def wrap(e, minprec, hint=None):
    s = txt(e, hint)
    p = e.prec if isinstance(e, E) else PREC_ATOM
    if isinstance(e, Const) and s.startswith('-'):
        p = PREC_ADD
    if p < minprec:
        return '(%s)' % s
    return s


def unify(a, b):
    ka = a.kind if isinstance(a, E) else None
    kb = b.kind if isinstance(b, E) else None
    return ka or kb


# ---------------------------------------------------------------- décompilateur

_HOLE = re.compile(r"'(?:[^']|'')*'|(?<![\w])\?(?![\w])")


def _has_hole(text):
    """Vrai si l'instruction contient l'opérande manquant '?' (hors chaînes)."""
    return any(m.group(0) == '?' for m in _HOLE.finditer(text))


class Stmt:
    def __init__(self, line, text, off=None, kids=None):
        if text and not text.lstrip().startswith('--') and _has_hole(text):
            text += '  -- ?? INSTRUCTION INCOMPLÈTE : opérande manquant (voir opcode inconnu au-dessus)'
        self.line = line; self.text = text; self.off = off; self.kids = kids


class Routine:
    pass


class Decompiler:
    def __init__(self, pc, fname=''):
        self.pc = pc
        self.fname = fname
        self.tc = TypeCtx(pc.tdefs, pc.fmt)
        bounds = set(pc.labels) | {r['off'] for r in pc.routines if r['mod'] == 0 and r['off'] != 0xffff}
        self.ins = disasm(pc.pcode, pc.pfx, bounds, len(pc.labels))
        self.unknown = [x for x in self.ins if x.op == -1]
        self.byoff = {x.off: x.idx for x in self.ins}
        self.labels = pc.labels
        self.warn = []
        self.goto_targets = set()
        self.used_labels = set()
        self.called31 = set()
        self.calledaa = set()

    # ------------------------------------------------------------ noms
    def varinfo(self, scope, idx):
        """-> (nom, type) pour var globale/système (scope 01), ou locale/param (ff)"""
        if scope == 0x01:
            if idx < len(self.pc.usedvars):
                v = self.pc.vars[self.pc.usedvars[idx]]
                return v[1], v[3]
            return 'var_%d' % idx, None
        if scope == 0xff:
            return self.cur.localname(idx)
        return 'v%02x_%d' % (scope, idx), None

    def lab(self, n):
        return 'lbl_%d' % n

    # ------------------------------------------------------------ routines
    def routine_ranges(self):
        rs = []
        for k, r in enumerate(self.pc.routines):
            if r['mod'] == 0 and r['off'] != 0xffff:
                rs.append((r['off'], k))
        rs.sort()
        out = []
        for j, (off, k) in enumerate(rs):
            end = rs[j + 1][0] if j + 1 < len(rs) else self.ins[-1].off + len(self.ins[-1].b)
            i0 = self.byoff.get(off)
            # l'instruction 7b (début) peut précéder l'offset déclaré ; on prend tout jusqu'au suivant
            i1 = self.byoff.get(end, len(self.ins))
            out.append((k, i0, i1))
        return out

    def run(self):
        HINTS.clear()
        NEGCONST.clear()
        self.routines = []
        # deux passes : la 1ère découvre les cibles de GOTO
        for pas in (0, 1):
            self.routines = []
            self.emitted_labels = set()
            for k, i0, i1 in self.routine_ranges():
                r = Routine()
                r.k = k; r.info = self.pc.routines[k]; r.i0 = i0; r.i1 = i1
                r.name = r.info['name']
                r.is_main = (k == 0)
                self.cur = r
                self.setup_routine(r)
                for (rk, idx), ks in HINTS.items():
                    if rk == k and idx in r.locals and r.locals[idx][1] is None:
                        kk = [z for z in ('real', 'bool', 'int', 'str') if z in ks]
                        if kk and kk[0] != 'str':
                            r.locals[idx][1] = ({'int': 0x10, 'real': 0x11, 'bool': 0x12}[kk[0]], [])
                if not self.unknown:
                    r.body = self.block(r.bstart, r.i1)
                else:                              # opcode inconnu : ne jamais perdre tout le fichier
                    nw = len(self.warn)
                    try:
                        r.body = self.block(r.bstart, r.i1)
                    except Exception as e:
                        del self.warn[nw:]
                        r.body = self.raw_body(r, e)
                self.routines.append(r)
        return self

    def raw_body(self, r, err):
        """Corps d'une routine que la reconstruction n'a pas pu traiter (structure cassée par un
        opcode inconnu) : le désassemblage est rendu en commentaires."""
        ln = self.line_before(r.bstart + 1) or 0
        bar = '-- ' + '#' * 70
        unk = [x for x in self.ins[r.i0:r.i1] if x.op == -1]
        out = [Stmt(ln, bar),
               Stmt(ln, '-- ?? ROUTINE NON DÉCOMPILÉE : la structure n\'a pas pu être reconstruite (%s)'
                    % ', '.join('opcode %02X inconnu @%04x' % (x.b[0], x.off) for x in unk[:5]) if unk
                    else '-- ?? ROUTINE NON DÉCOMPILÉE (%s)' % type(err).__name__),
               Stmt(ln, '-- ??   désassemblage (offset: octets) :')]
        cur = ln
        for x in self.ins[r.i0:r.i1]:
            if x.op == 0x3e:
                cur = x.u16()
            out.append(Stmt(cur, '-- ' + repr(x)))
        out.append(Stmt(cur, bar))
        self.warn.append('routine %s non décompilée (%r)' % (r.name, err))
        return out

    def setup_routine(self, r):
        info = r.info
        r.params = []
        # slots des paramètres : dernier param = 0, en remontant
        np_ = len(info['params'])
        slots = []
        for (t) in info['params']:
            k = self.tc.kind(t)
            slots.append(2 if k in ('str', 'pos') else 1)
        total = sum(slots)
        pos = -total + 1
        r.pslot = {}
        r.descslots = set()
        for j, t in enumerate(info['params']):
            nm = 'p%d' % (j + 1)
            r.params.append((nm, t))
            r.pslot[pos] = (nm, t)
            if slots[j] == 2 and self.tc.kind(t) == 'pos':
                r.descslots.add(pos + 1)
            pos += slots[j]
        r.locals = {}      # slot -> [nom, type, declared]
        r.localtypes = {}
        i = r.i0
        # prologue : 2b (locales structurées), 2c 01 00 n (scalaires), 7b
        ns = 0
        while i < r.i1 and self.ins[i].op in (0x2b, 0x2c, 0x7b):
            x = self.ins[i]
            if x.op == 0x2b:
                rr = R(x.b, 1)
                slot = 0
                while True:
                    t = rr.u16()
                    if t == 0:
                        break
                    t = norm_type(t)
                    nd = (t >> 13) & 3
                    dims = [rr.u16() for _ in range(nd)]
                    if t == 0x001f:
                        dims = [rr.u16(), rr.u16(), rr.u16()]
                    ty = (t, dims)
                    sz = self.tc.size(ty)
                    slot += (sz + 3) // 4
                    r.locals[slot] = ['l_%d' % slot, ty, True]
                ns = slot
            elif x.op == 0x2c and x.u8() == 1:
                n = x.s16(2)
                for s in range(ns + 1, ns + n + 1):
                    r.locals[s] = ['l_%d' % s, None, False]
                ns += n
            i += 1
        r.bstart = i
        r.localname = lambda idx, r=r: self._localname(r, idx)

    def _localname(self, r, idx):
        if idx <= 0 or idx - 0 in r.pslot and idx <= 0:
            if idx in r.pslot:
                return r.pslot[idx]
            return 'p_slot%d' % idx, None
        if idx not in r.locals:
            r.locals[idx] = ['l_%d' % idx, None, False]
        l = r.locals[idx]
        return l[0], l[1]

    def field0(self, a, op):
        """anciens compilateurs : l'accès au 1er champ (offset 0) n'émet pas d'op 32"""
        if not isinstance(a, E):
            return a
        for _ in range(6):
            ty = a.ty
            if ty is None and getattr(a, 'lkey', None) is not None and op in (0x34, 0x35):
                self.note_local_struct(a.lkey[1], 12, 0x13); ty = (0x13, [])
            if ty is None:
                return a
            k = self.tc.kind(ty)
            if k not in ('vec', 'struct', 'pos'):
                return a
            if op == 0x5d and k != 'struct':       # 5D écrit une position entière : on ne descend que dans
                return a                           # une STRUCTURE (1er champ d'un noeud de PATH en V6)
            if k == 'pos' and op in (0x36,):
                return a
            fn, fty = self.tc.field_at(ty, 0)
            if fn is None:
                if k == 'pos':
                    # en-tête : premier champ utile
                    return a
                return a
            a = E('%s.%s' % (txt(a), fn), PREC_ATOM, self.tc.kind(fty) if fty else None, fty, True)
        return a

    def note_local_struct(self, idx, size, kind):
        r = self.cur
        if idx <= 0 or idx not in r.locals or r.locals[idx][2]:
            return
        if kind == 0x13 or (kind is None and size == 0x0c):
            ty = (0x13, [])
        elif kind is not None:
            ty = ((1 << 8) | kind, [])
        else:
            return
        n = (size + 3) // 4
        r.locals[idx][1] = ty
        r.locals[idx][2] = True
        for k in range(idx - n + 1, idx):
            r.locals.pop(k, None)

    def note_local_type(self, idx, kind):
        r = self.cur
        if idx > 0 and idx in r.locals and r.locals[idx][1] is None and kind in ('int', 'real', 'bool'):
            r.locals[idx][1] = ({'int': 0x10, 'real': 0x11, 'bool': 0x12}[kind], [])

    def enum_name(self, ty, v):
        """constante d'un type énuméré système ($MOTYPE = LINEAR...) ; None sinon"""
        if not isinstance(v, Const) or not ty:
            return None
        code = ty if isinstance(ty, int) else ty[0]
        if code >> 8 != 0x11 or (code & 0xff) >= len(self.pc.tdefs):
            return None
        return ENUMS.get(self.pc.tdefs[code & 0xff]['name'], {}).get(v.raw)

    # ------------------------------------------------------------ helpers
    def labpos(self, n):
        return self.labels[n] if n < len(self.labels) else None

    def labidx(self, n):
        p = self.labpos(n)
        return self.byoff.get(p) if p is not None else None

    def line_before(self, idx, lo=0):
        """numéro de ligne du dernier 3e avant idx"""
        j = idx - 1
        while j >= lo:
            if self.ins[j].op == 0x3e:
                return self.ins[j].u16()
            j -= 1
        return None

    def varexpr(self, scope, idx, addr=False):
        nm, ty = self.varinfo(scope, idx)
        if isinstance(nm, tuple):
            nm, ty = nm
        k = self.tc.kind(ty) if ty else None
        e = E(nm, PREC_ATOM, k, ty, addr)
        if scope == 0xff and idx > 0 and ty is None:
            e.lkey = (self.cur.k, idx)
        return e

    # ------------------------------------------------------------ bloc
    def block(self, i, end):
        out = []
        st = []
        line = [self.line_before(i) or 0]

        def emit(text, off=None, kids=None, ln=None):
            out.append(Stmt(ln if ln is not None else line[0], text, off, kids))

        def pop():
            if st:
                return st.pop()
            self.warn.append('pile vide @%04x' % self.ins[i].off)
            return E('?', PREC_ATOM)

        mark = {}
        while i < end:
            x = self.ins[i]
            op = x.op
            mark[i] = len(out)
            # étiquettes utilisateur
            if x.off in self.goto_targets_pos():
                n = self.goto_label_at(x.off)
                if n not in self.emitted_labels:
                    self.emitted_labels.add(n)
                    emit('%s::' % self.lab(n), ln=self.line_before(i))
            if op == -1:                         # opcode inconnu : octets non décodés, on reprend après
                op0 = x.b[0]
                hx = x.b.hex(' ')
                if len(hx) > 60:
                    hx = hx[:60] + ' ...'
                pile = ', '.join(txt(e) for e in st if not isinstance(e, Marker))
                bar = '-- ' + '#' * 70
                emit(bar)
                emit('-- ?? OPCODE %02X INCONNU @%04x : %d octet(s) non décodé(s) : %s' % (op0, x.off, len(x.b), hx))
                if pile:
                    emit('-- ??   pile avant l\'instruction : %s' % pile)
                emit('-- ??   instruction(s) de cette ligne source manquante(s) ou incomplète(s)')
                emit(bar)
                self.warn.append('opcode %02X inconnu @%04x (ligne %d) : %d octet(s) ignoré(s)' % (op0, x.off, line[0], len(x.b)))
                st = []
                i += 1
                continue
            if op == 0x3e:
                line[0] = x.u16()
                if st:
                    for e in st:
                        if not isinstance(e, Marker):
                            emit('-- ?? reste de pile : %s' % txt(e))
                    st = []
                i += 1
                continue
            # ---------------- contrôle
            if op == 0x79:                       # JMPF
                cond = pop()
                n = x.u32()
                t = self.labidx(n)
                if t is None:
                    emit('-- ?? saut vers étiquette inconnue %d' % n); i += 1; continue
                if t <= i:                       # REPEAT ... UNTIL
                    # le corps a déjà été émis : on le récupère
                    k0 = mark.get(t)
                    if k0 is None:
                        # la cible est avant le début du bloc : on prend tout
                        k0 = 0
                        self.warn.append('REPEAT hors bloc @%04x' % x.off)
                    body = out[k0:]
                    del out[k0:]
                    rline = self.line_before(t)
                    out.append(Stmt(rline, 'REPEAT', self.ins[t].off, None))
                    out.append(Stmt(None, None, None, body))
                    out.append(Stmt(line[0], 'UNTIL %s' % txt(cond, 'bool'), x.off))
                    self.used_labels.add(n)
                    i += 1
                    continue
                prev = self.ins[t - 1]
                if prev.op == 0x7a:
                    n2 = prev.u32(); t2 = self.labidx(n2)
                    if t2 is not None and t2 <= i:          # WHILE
                        body = self.block(i + 1, t - 2 if self.ins[t - 2].op == 0x3e else t - 1)
                        wl = line[0]
                        endl = self.ins[t - 2].u16() if self.ins[t - 2].op == 0x3e else None
                        out.append(Stmt(wl, 'WHILE %s DO' % txt(cond, 'bool'), x.off))
                        out.append(Stmt(None, None, None, body))
                        out.append(Stmt(endl, 'ENDWHILE', None))
                        self.used_labels.update([n, n2])
                        i = t
                        continue
                    if t2 is not None and t2 > t:           # IF ... ELSE
                        e_idx = t - 2 if self.ins[t - 2].op == 0x3e else t - 1
                        thenb = self.block(i + 1, e_idx)
                        elsel = self.ins[t - 2].u16() if self.ins[t - 2].op == 0x3e else None
                        endi = t2 - 1 if self.ins[t2 - 1].op == 0x3e else t2
                        elseb = self.block(t, endi)
                        endl = self.ins[t2 - 1].u16() if self.ins[t2 - 1].op == 0x3e else None
                        out.append(Stmt(line[0], 'IF %s THEN' % txt(cond, 'bool'), x.off))
                        out.append(Stmt(None, None, None, thenb))
                        out.append(Stmt(elsel, 'ELSE', None))
                        out.append(Stmt(None, None, None, elseb))
                        out.append(Stmt(endl, 'ENDIF', None))
                        self.used_labels.update([n, n2])
                        i = endi
                        continue
                # IF sans ELSE
                endi = t - 1 if self.ins[t - 1].op == 0x3e else t
                thenb = self.block(i + 1, endi)
                endl = self.ins[t - 1].u16() if self.ins[t - 1].op == 0x3e else None
                out.append(Stmt(line[0], 'IF %s THEN' % txt(cond, 'bool'), x.off))
                out.append(Stmt(None, None, None, thenb))
                out.append(Stmt(endl, 'ENDIF', None))
                self.used_labels.add(n)
                i = endi
                continue
            if op == 0x7a:                       # GOTO
                n = x.u32()
                self.goto_targets.add(n)
                emit('GOTO %s' % self.lab(n), x.off)
                i += 1
                continue
            if op in (0x9e, 0x9f, 0xa0, 0xa1):   # FOR
                var = self.varexpr(0xff if op in (0xa0, 0xa1) else x.u8(), x.s32(2))
                init = None
                if out and out[-1].text and out[-1].text.startswith(var.text + ' = '):
                    init = out.pop().text[len(var.text) + 3:]
                # limite jusqu'au 22 var ; 7a Ltest
                j = i + 1
                while j < end and not (self.ins[j].op == 0x7a and self.ins[j - 1].op in (0x22, 0x17)):
                    j += 1
                lim_st = self.expr_range(i + 1, j - 1)
                lim = txt(lim_st[-1], 'int') if lim_st else '?'
                n = self.ins[j].u32(); tt = self.labidx(n)
                # corps : j+1 .. ligne ENDFOR (3e avant tt)
                bend = tt - 1 if self.ins[tt - 1].op == 0x3e else tt
                body = self.block(j + 1, bend)
                endl = self.ins[tt - 1].u16() if self.ins[tt - 1].op == 0x3e else None
                d = 'TO' if op in (0x9e, 0xa0) else 'DOWNTO'
                out.append(Stmt(line[0], 'FOR %s = %s %s %s DO' % (var.text, init, d, lim), x.off))
                out.append(Stmt(None, None, None, body))
                out.append(Stmt(endl, 'ENDFOR', None))
                self.used_labels.add(n)
                # sauter 20/45 L ; 2c 00 00 01 ; 23 var
                k = tt
                if self.ins[k].op in (0x20, 0x45):
                    self.used_labels.add(self.ins[k].u32()); k += 1
                if k < end and self.ins[k].op == 0x2c and self.ins[k].u8() == 0:
                    k += 1
                    if k < end and self.ins[k].op in (0x23, 0x2f):
                        k += 1
                i = k
                continue
            if op == 0x40:                       # SELECT
                sel = pop()
                cases = []
                k = i
                endsel = None
                while True:
                    y = self.ins[k]
                    if y.op == 0x40:
                        nxt = y.u32(); vals = []
                        k += 1
                        while self.ins[k].op == 0x41:
                            vals.append(self.ins[k].s32()); k += 1
                        assert self.ins[k].op == 0x42
                        k += 1
                        nk = self.labidx(nxt)
                        if nk is None:           # étiquette hors du code décodé (opcode inconnu plus loin)
                            self.warn.append('SELECT @%04x : étiquette %d introuvable' % (y.off, nxt))
                            nk = end
                        # corps jusqu'à 7a Lend juste avant nk
                        be = nk - 1 if self.ins[nk - 1].op == 0x7a else nk
                        if self.ins[nk - 1].op == 0x7a:
                            endsel = self.ins[nk - 1].u32()
                        body = self.block(k, be)
                        cases.append(('CASE(%s):' % ','.join(str(v) for v in vals), body))
                        self.used_labels.add(nxt)
                        k = nk
                        continue
                    if y.op == 0x43:
                        e = self.labidx(endsel) if endsel is not None else end
                        e2 = e - 1 if (e and self.ins[e - 1].op == 0x3e) else e
                        body = self.block(k + 1, e2 if e2 else e)
                        cases.append(('ELSE:', body))
                        k = e2 if e2 else e
                        break
                    if y.op == 0x44:
                        k += 1
                        break
                    break
                sl = line[0]
                out.append(Stmt(sl, 'SELECT %s OF' % txt(sel, 'int'), x.off))
                for (h, b) in cases:
                    out.append(Stmt(None, h, None, None))
                    out.append(Stmt(None, None, None, b))
                if endsel is not None:
                    self.used_labels.add(endsel)
                    ei = self.labidx(endsel)
                    if ei is not None and self.ins[ei].op == 0x3e:
                        out.append(Stmt(self.ins[ei].u16(), 'ENDSELECT', None))
                        k = max(k, ei + 1)
                        line[0] = self.ins[ei].u16()
                    else:
                        out.append(Stmt(None, 'ENDSELECT', None))
                else:
                    out.append(Stmt(None, 'ENDSELECT', None))
                i = k
                continue
            if op == 0x7f:                       # RETURN
                r = self.cur
                rs = x.s16(2)
                last = (i == r.i1 - 1) or (i + 1 < len(self.ins) and self.ins[i + 1].op == 0x7b and i + 1 >= r.i1 - 1)
                if rs == -3 or (last and rs == 0 and not st):
                    i += 1; continue              # END de routine
                if rs == 0 and not st:
                    emit('RETURN', x.off)
                else:
                    v = pop()
                    k = self.tc.kind(r.info['ret'])
                    emit('RETURN(%s)' % txt(v, k), x.off)
                i += 1
                continue
            if op == 0x7b:
                i += 1; continue
            # ---------------- instructions simples
            res = self.simple(x, st, emit, i)
            if res is False:
                emit('-- ?? op %s' % x.b.hex(' '), x.off)
            i += 1
        if st:
            for e in st:
                if not isinstance(e, Marker):
                    emit('-- ?? reste de pile : %s' % txt(e))
        if end < len(self.ins) and self.ins[end].off in self.goto_targets_pos():
            n = self.goto_label_at(self.ins[end].off)
            if n not in self.emitted_labels:
                self.emitted_labels.add(n)
                emit('%s::' % self.lab(n), ln=self.line_before(end))
        return out

    def expr_range(self, a, b):
        st = []
        dummy = []
        for j in range(a, b):
            self.simple(self.ins[j], st, lambda *a, **k: dummy.append(a), j)
        return st

    def goto_targets_pos(self):
        if not hasattr(self, '_gtp') or self._gtp_n != len(self.goto_targets):
            self._gtp = {self.labpos(n): n for n in self.goto_targets if self.labpos(n) is not None}
            self._gtp_n = len(self.goto_targets)
        return self._gtp

    def goto_label_at(self, off):
        return self.goto_targets_pos()[off]

    # ------------------------------------------------------------ opérations
    def call_args(self, st, params, name):
        """dépile les arguments d'un appel (params = liste de types)"""
        args = []
        for t in reversed(params):
            if not st:
                args.append('?'); continue
            a = st.pop()
            if st and isinstance(st[-1], Marker):
                st.pop()
            k = self.tc.kind(t) if t is not None else None
            if k in ('int', 'real', 'bool', 'str') and isinstance(a, E) and a.ty is not None \
                    and self.tc.kind(a.ty) in ('struct', 'vec'):
                a = self.field0(a, 0x34)          # 1er champ (offset 0 implicite, anciens compilateurs)
            args.append(txt(a, k))
        # marqueur de trame
        if st and isinstance(st[-1], Marker):
            st.pop()
        args.reverse()
        # supprimer les paramètres optionnels à leur valeur par défaut ? (on les garde)
        return args

    def simple(self, x, st, emit, i):
        op = x.op
        tc = self.tc

        def pop():
            if st:
                return st.pop()
            return E('?')

        def push(e):
            st.append(e)

        def binop(sym, prec, kind, argkind=None, cmp=False):
            b = pop(); a = pop()
            if getattr(a, 'swp', None) is not None and a.swp == getattr(b, 'swp', None):
                a, b = b, a                        # opérandes échangés par le compilateur
            k = argkind or unify(a, b)
            if isinstance(a, Const) and k: a.kind = k
            if isinstance(b, Const) and k: b.kind = k
            s = '%s %s %s' % (wrap(a, prec, k), sym, wrap(b, prec + 1, k))
            push(E(s, prec, kind))

        # constantes
        if op == 0x9c: push(Const(0)); return
        if op == 0x9d: push(Const(1)); return
        if op == 0x9b: push(Const(0xffffffff)); return
        if op == 0x2e: push(Const(x.u32())); return
        if op == 0x3f:
            s = x.b[2:].decode('latin-1').replace("'", "''")
            push(E("'%s'" % s, PREC_ATOM, 'str')); return
        if op == 0x27: push(Marker()); return
        # variables
        if op in (0x21, 0x73):
            push(self.varexpr(x.u8(), x.s32(2))); return
        if op == 0x22:
            e = self.varexpr(x.u8(), x.s32(2), addr=True); push(e); return
        if op == 0x17 and x.s32(2) in getattr(self.cur, 'descslots', ()):
            return                                 # descripteur de type d'un paramètre position
        if op in (0x2d, 0x74, 0x17):
            e = self.varexpr(0xff, x.s32(2), addr=(op == 0x17)); push(e); return
        if op in (0x23, 0x75, 0x2f, 0xa2):
            sc = 0xff if op in (0x2f, 0xa2) else x.u8()
            idx = x.s32(2)
            v = self.varexpr(sc, idx)
            val = pop()
            k = v.kind or (val.kind if isinstance(val, E) else None)
            if sc == 0xff and idx > 0 and isinstance(val, E):
                self.note_local_type(idx, val.kind if not isinstance(val, Const) else (val.kind or None))
            emit('%s = %s' % (v.text, txt(val, k)), x.off)
            return
        if op == 0x4b:                             # load position param
            push(self.varexpr(0xff, x.s32(2))); return
        if op == 0x4c:                             # store position param
            v = self.varexpr(0xff, x.s32(2)); val = pop()
            emit('%s = %s' % (v.text, txt(val)), x.off); return
        if op == 0x4a:                             # store position var
            if x.u8() == 0xff:
                self.note_local_struct(x.s32(2), x.u8(6), None)
            v = self.varexpr(x.u8(), x.s32(2)); val = pop()
            emit('%s = %s' % (v.text, txt(val)), x.off); return
        if op == 0x49:                             # load position var
            if x.u8() == 0xff:
                self.note_local_struct(x.s32(2), x.u8(6), x.u8(7))
            v = self.varexpr(x.u8(), x.s32(2)); v.addr = False; push(v); return
        if op == 0x33:                             # indexation
            idx = pop(); base = pop()
            bty = base.ty if isinstance(base, E) else None
            ety = tc.elem(bty) if bty else None
            if isinstance(base, E) and base.text.endswith(']') and getattr(base, 'multi', 0):
                s = base.text[:-1] + ',%s]' % txt(idx, 'int')
                e = E(s, PREC_ATOM, None, None, True)
                e.multi = base.multi - 1
                e.ety = base.ety
                if e.multi == 0:
                    e.ty = base.ety; e.kind = tc.kind(base.ety) if base.ety else None
                push(e); return
            s = '%s[%s]' % (txt(base), txt(idx, 'int'))
            e = E(s, PREC_ATOM, tc.kind(ety) if ety else None, ety, True)
            if bty and ((bty[0] >> 13) & 3) > 1:
                e.multi = ((bty[0] >> 13) & 3) - 1
                e.ety = ety; e.ty = None; e.kind = None
            push(e); return
        if op == 0x98:                             # en-tête de PATH : pth.champ
            base = pop()
            bty = base.ty if isinstance(base, E) else None
            hty = tc.path_header(bty) if bty else None
            e = E(txt(base), PREC_ATOM, tc.kind(hty) if hty else None, hty, True)
            push(e); return
        if op == 0x99:                             # noeud de PATH : pth[i]
            idx = pop(); base = pop()
            bty = base.ty if isinstance(base, E) else None
            nty = tc.path_node(bty) if bty else None
            s = '%s[%s]' % (txt(base), txt(idx, 'int'))
            push(E(s, PREC_ATOM, tc.kind(nty) if nty else None, nty, True)); return
        if op == 0x32:                             # champ
            base = pop()
            off = x.u16()
            if isinstance(base, FileN) or (isinstance(base, E) and base.text == '<sysfiles>'):
                push(FileN(PREDEF_FILES.get(off, 'FILE_%d' % off))); return
            bty = base.ty if isinstance(base, E) else None
            if bty is None and getattr(base, 'lkey', None) is not None:
                self.note_local_struct(base.lkey[1], 12, 0x13)   # local scalaire structuré = VECTOR
                bty = (0x13, [])
            fn, fty = (tc.field_at(bty, off) if bty else (None, None))
            if fn is None:
                fn = 'FIELD_%X' % off
            s = '%s.%s' % (txt(base), fn)
            push(E(s, PREC_ATOM, tc.kind(fty) if fty else None, fty, True)); return
        if op in (0xa4, 0xa5):                     # champ d'un CONFIG (bits) : A4/A5 bb ww
            a = pop()                              # (bit de départ, largeur) ; A4 lecture, A5 écriture
            fn = CFG_FIELDS.get((x.u8(1), x.u8(2)), 'CFG_BITS_%d_%d' % (x.u8(1), x.u8(2)))
            k = 'int' if x.u8(2) > 1 else 'bool'
            s = '%s.%s' % (txt(a), fn)
            if op == 0xa4:
                push(E(s, PREC_ATOM, k)); return
            v = pop()
            emit('%s = %s' % (s, txt(v, k)), x.off); return
        if op in (0x34, 0xb1, 0xb3, 0x5e):         # déréf
            a = self.field0(pop(), op)
            push(E(txt(a), PREC_ATOM, a.kind if isinstance(a, E) else None, a.ty if isinstance(a, E) else None))
            return
        if op == 0x36:                             # déréf position
            a = pop(); push(E(txt(a), PREC_ATOM, 'pos', getattr(a, 'ty', None))); return
        if op == 0x1e:                             # affectation d'un tableau renvoyé par une fonction
            a = pop(); v = pop()                   # (valeur, adresse) -> 1E <nb dimensions> (vérifié : t_arrfunc, t_arrfunc3)
            emit('%s = %s' % (txt(a), txt(v)), x.off); return
        if op in (0x35, 0xb2, 0xb4, 0x61, 0x5d):   # stockage via adresse
            a = self.field0(pop(), op); v = pop()
            k = a.kind if isinstance(a, E) else None
            en = self.enum_name(a.ty if isinstance(a, E) else None, v)
            emit('%s = %s' % (txt(a), en or txt(v, k)), x.off); return
        # ports
        if op == 0x19:
            idx = pop(); pn = PORTS.get(x.u8(), 'PORT_%02X' % x.u8())
            push(E('%s[%s]' % (pn, txt(idx, 'int')), PREC_ATOM, PORT_KIND.get(pn))); return
        if op == 0x1a:
            idx = pop(); v = pop(); pn = PORTS.get(x.u8(), 'PORT_%02X' % x.u8())
            emit('%s[%s] = %s' % (pn, txt(idx, 'int'), txt(v, PORT_KIND.get(pn))), x.off); return
        if op in (0x0f, 0x1f):                     # PULSE
            t = pop(); idx = pop(); pn = PORTS.get(x.u8(), 'PORT_%02X' % x.u8())
            emit('PULSE %s[%s] FOR %s%s' % (pn, txt(idx, 'int'), txt(t, 'int'), ' NOWAIT' if op == 0x1f else ''), x.off)
            return
        # arithmétique entière / booléenne
        BIN = {0x52: ('+', PREC_ADD, 'int'), 0x53: ('-', PREC_ADD, 'int'), 0x54: ('*', PREC_MUL, 'int'),
               0x55: ('DIV', PREC_MUL, 'int'), 0x56: ('MOD', PREC_MUL, 'int'),
               0x69: ('+', PREC_ADD, 'real'), 0x6a: ('-', PREC_ADD, 'real'), 0x6b: ('*', PREC_MUL, 'real'),
               0x6c: ('/', PREC_MUL, 'real'), 0x7d: ('+', PREC_ADD, 'str')}
        if op in BIN:
            s, p, k = BIN[op]; binop(s, p, k, k); return
        VEC = {0x91: ('+', PREC_ADD, 'vec', 'vec'), 0x92: ('-', PREC_ADD, 'vec', 'vec'),
               0x89: ('*', PREC_MUL, 'vec', 'int'), 0x8a: ('*', PREC_MUL, 'vec', 'real'),
               0x8b: ('*', PREC_MUL, 'vec', 'int'), 0x8c: ('*', PREC_MUL, 'vec', 'real'),
               0x8d: ('/', PREC_MUL, 'vec', 'int'), 0x8e: ('/', PREC_MUL, 'vec', 'real'),
               0x93: ('#', PREC_POS, 'vec', 'vec'), 0x94: ('@', PREC_POS, 'real', 'vec'),
               0x9a: (':', PREC_POS, 'vec', 'pos'), 0x60: (':', PREC_POS, 'pos', 'pos'),
               0x95: ('=', PREC_REL, 'bool', 'vec'), 0x96: ('<>', PREC_REL, 'bool', 'vec'),
               0xac: ('>=<', PREC_REL, 'bool', 'pos')}
        if op in VEC:
            s, p, k, ak = VEC[op]
            b = pop(); a = pop()
            if op in (0x8b, 0x8c):      # scalaire * vecteur
                sa, sb = wrap(a, p, 'int' if op == 0x8b else 'real'), wrap(b, p + 1, 'vec')
            elif op in (0x89, 0x8a, 0x8d, 0x8e):
                sa, sb = wrap(a, p, 'vec'), wrap(b, p + 1, 'int' if op in (0x89, 0x8d) else 'real')
            else:
                sa, sb = wrap(a, p, ak), wrap(b, p + 1, ak)
            push(E('%s %s %s' % (sa, s, sb), p, k)); return
        if op == 0x97:
            a = pop(); push(E('-%s' % wrap(a, PREC_MUL, 'vec'), PREC_ADD, 'vec')); return
        if op == 0x7e:                             # conversion implicite de type position
            return
        if op == 0x2c and x.u8() == 0:             # valeurs non initialisées
            for _ in range(x.s16(2)):
                push(E('<UNINIT>', PREC_ATOM, 'uninit'))
            return
        # mouvement
        if op == 0x01:
            push(Motion(x.u16())); return
        if op == 0x02:                             # clause WITH : valeur, groupe -> 02 id
            mi = max((j for j in range(len(st)) if isinstance(st[j], Motion)), default=None)
            if mi is None or len(st) - mi < 3:
                return False
            g = st.pop(); v = st.pop()
            nm, k = WITH_IDS.get(x.u8(), ('$WITH_%d' % x.u8(), None))
            if k in ENUMS and isinstance(v, Const) and v.raw in ENUMS[k]:
                vt = ENUMS[k][v.raw]
            else:
                vt = txt(v, k if k in ('int', 'real', 'bool') else ('int' if k in ENUMS else None))
            gn = g.raw if isinstance(g, Const) else txt(g, "int")
            st[mi].withs.append((nm, gn, vt))
            return
        if op == 0x05:                             # masque de groupes après les clauses WITH
            # jamais produit par ktrans dans nos tests (ni directive, ni robot.ini) : ignoré,
            # sans effet sur la recompilation mais le .pc recompilé sera 3 octets plus court
            self.warn.append('instruction 05 %04x @%04x ignorée (non reproductible avec ktrans)' % (x.u16(), x.off))
            return
        if op == 0x0c:                             # MOVE TO noeud de PATH : pth[i]
            mi = max((j for j in range(len(st)) if isinstance(st[j], Motion)), default=None)
            if mi is None or len(st) - mi < 3:
                return False
            m = st[mi]; args = st[mi + 1:]; del st[mi + 1:]
            m.parts.append('MOVE TO %s[%s]' % (txt(args[0]), txt(args[1], 'int')))
            return
        if op in (0x06, 0x07, 0x08, 0x0a):
            mi = max((j for j in range(len(st)) if isinstance(st[j], Motion)), default=None)
            if mi is None:
                return False
            m = st[mi]; args = st[mi + 1:]; del st[mi + 1:]
            A = [txt(a) for a in args]
            if op == 0x06:
                m.parts.append('MOVE TO %s' % A[0])
            elif op == 0x07:
                m.parts.append('VIA %s' % A[0])
            elif op == 0x08:
                rng = ''
                if len(A) >= 3 and args[2].kind != 'uninit':
                    rng = '[%s..%s]' % (txt(args[1], 'int'), txt(args[2], 'int'))
                m.parts.append('MOVE ALONG %s%s' % (A[0], rng))
            else:
                k = x.u8()
                if k == 1: m.parts.append('MOVE NEAR %s BY %s' % (A[0], txt(args[1], 'real')))
                elif k == 2: m.parts.append('MOVE AWAY %s' % txt(args[0], 'real'))
                elif k == 4: m.parts.append('MOVE ABOUT %s BY %s' % (A[0], txt(args[1], 'real')))
                elif k == 5: m.parts.append('MOVE AXIS %s BY %s' % (txt(args[0], 'int'), txt(args[1], 'real')))
                elif k == 6: m.parts.append('MOVE RELATIVE %s' % A[0])
                else: m.parts.append('MOVE ?%d %s' % (k, ', '.join(A)))
            return
        if op == 0x82:
            return
        if op == 0x09:
            mi = max((j for j in range(len(st)) if isinstance(st[j], Motion)), default=None)
            if mi is not None:
                st[mi].nowait = True; return
            return False
        if op == 0x0b:
            mi = max((j for j in range(len(st)) if isinstance(st[j], Motion)), default=None)
            if mi is None:
                return False
            conds = [c for c in st[mi + 1:] if isinstance(c, CondN) and c.done]
            del st[mi + 1:]
            m = st.pop(mi)
            head = ' '.join(m.parts) + (' NOWAIT' if m.nowait else '')
            if m.withs:
                head = 'WITH %s %s' % (', '.join(
                    '%s = %s' % (n if (g == 1 and m.grp == 1) else '$GROUP[%s].%s' % (g, n), v)
                    for (n, g, v) in m.withs), head)
            if conds:                              # conditions locales : MOVE ..., WHEN ... ENDMOVE
                lines = [head + ',']
                for c in conds:
                    for (cs, acts, orf) in c.clauses:
                        lines.append('\tWHEN %s DO %s' % ((' OR ' if orf else ' AND ').join(cs), ', '.join(acts)))
                lines.append('ENDMOVE')
                head = '\n'.join(lines)
            emit(head, x.off)
            return
        if op in (0x46, 0x47):
            b = st[-1] if st else None
            k = 'bool' if (b is not None and b.kind == 'bool') else None
            a2 = st[-2] if len(st) > 1 else None
            if a2 is not None and a2.kind == 'bool': k = 'bool'
            binop('AND' if op == 0x46 else 'OR', PREC_MUL if op == 0x46 else PREC_ADD, k or 'int', k)
            return
        CMP = {0x57: '=', 0x58: '<>', 0x59: '<', 0x5a: '<=', 0x5b: '>', 0x5c: '>=',
               0x6d: '=', 0x6e: '<>', 0x6f: '<', 0x70: '<=', 0x71: '>', 0x72: '>=',
               0x83: '=', 0x84: '<>', 0x85: '<', 0x86: '<=', 0x87: '>', 0x88: '>='}
        if op in CMP:
            ak = 'real' if 0x6d <= op <= 0x72 else ('str' if op >= 0x83 else None)
            if ak is None:
                b = st[-1] if st else None; a = st[-2] if len(st) > 1 else None
                ak = (a.kind if a is not None and not isinstance(a, Const) else None) or \
                     (b.kind if b is not None and not isinstance(b, Const) else None) or 'int'
            binop(CMP[op], PREC_REL, 'bool', ak); return
        if op == 0x5f:
            a = pop(); push(E('NOT %s' % wrap(a, PREC_UN, 'bool'), PREC_UN, 'bool')); return
        if op == 0x48:
            a = pop(); push(E('NOT %s' % wrap(a, PREC_UN, 'int'), PREC_UN, 'int')); return
        if op in (0x51, 0x68):
            a = pop(); k = 'int' if op == 0x51 else 'real'
            if isinstance(a, Const): a.kind = k
            push(E('-%s' % wrap(a, PREC_MUL, k), PREC_ADD, k)); return
        if op in (0x50, 0x67):
            a = pop(); k = 'int' if op == 0x50 else 'real'
            push(E('ABS(%s)' % txt(a, k), PREC_ATOM, k)); return
        if op == 0x64:                             # INT -> REAL (implicite)
            if len(st) >= 2 and isinstance(st[-1], E) and st[-1].addr and not isinstance(st[-1], Const):
                ad = st.pop()
                self.simple(x, st, emit, i)
                st.append(ad)
                return
            a = pop()
            if isinstance(a, Const):
                a.kind = 'int'
                n = E(a.render('int'), PREC_ADD if a.render('int').startswith('-') else PREC_ATOM, 'real')
            else:
                n = E(txt(a, 'int'), a.prec if isinstance(a, E) else PREC_ATOM, 'real')
            n.swp = getattr(a, 'swp', None)
            push(n)
            return
        if op == 0x29:                             # SWAP
            if len(st) >= 2:
                a, b = st[-2], st[-1]
                if getattr(a, 'swp', None) is not None and a.swp == getattr(b, 'swp', None):
                    a.swp = b.swp = None
                else:
                    self._swp = getattr(self, '_swp', 0) + 1
                    a.swp = b.swp = self._swp
                st[-1], st[-2] = a, b
            return
        if op == 0x2a:                             # descripteur de chaîne (arg par réf.)
            return
        if op == 0x1c:                             # descripteur de type position
            return
        if op == 0x24:                             # BYNAME(prog, var, entry)
            e = pop(); v = pop(); p = pop()
            ty = (norm_type(x.u16()), [])
            push(E('BYNAME(%s, %s, %s)' % (txt(p), txt(v), txt(e)), PREC_ATOM, tc.kind(ty), ty, True)); return
        if op == 0x26:                             # libération BYNAME après appel
            return
        if op == 0x1d:                             # ARRAY_LEN
            a = pop(); push(E('ARRAY_LEN(%s)' % txt(a), PREC_ATOM, 'int')); return
        if op == 0x30:                             # copie de structure
            d = pop(); sv = pop()
            emit('%s = %s' % (txt(d), txt(sv)), x.off); return
        if op == 0x63:                             # UNINIT
            a = pop()
            if tc.kind((norm_type(x.u16()), [])) in ('int', 'real', 'bool', 'str'):
                a = self.field0(a, 0x34)
            push(E('UNINIT(%s)' % txt(a), PREC_ATOM, 'bool')); return
        # appels
        if op == 0xaa or op == 0x31:
            k = x.u16()
            r = self.pc.routines[k]
            (self.calledaa if op == 0xaa else self.called31).add(k)
            args = self.call_args(st, r['params'], r['name'])
            s = '%s(%s)' % (r['name'], ', '.join(args)) if args else r['name']
            if r['ret'][0]:
                push(E(s, PREC_ATOM, tc.kind(r['ret']), r['ret']))
            else:
                emit(s, x.off)
            return
        if op == 0x76:
            k = x.u8()
            if k in INTRINSICS:
                nm, rt, ps, hidden = INTRINSICS[k]
                params = [tuple(p[1]) for p in ps]
                args = self.call_args(st, params, nm)
                if hidden:                         # arguments ajoutés par le compilateur
                    args = args[:len(args) - hidden]
                # supprimer GROUP_NO optionnel s'il vaut la valeur par défaut ? on garde tout
                s = '%s(%s)' % (nm, ', '.join(args))
                rt = tuple(rt)
                if rt[0]:
                    push(E(s, PREC_ATOM, tc.kind(rt), rt))
                else:
                    emit(s, x.off)
            else:
                emit('-- ?? intrinsèque 76 %02x' % k, x.off)
            return
        if op in (0xaf, 0xb0):                     # GET_VAR / SET_VAR
            t = norm_type(x.u16())
            params = [(0x10, []), (0x1f00, []), (0x1f00, []), (t, []), (0x10, [])]
            args = self.call_args(st, params, '')
            emit('%s(%s)' % ('GET_VAR' if op == 0xaf else 'SET_VAR', ', '.join(args)), x.off)
            return
        # instructions
        if op == 0x11:
            a = pop(); emit('DELAY %s' % txt(a, 'int'), x.off); return
        if op == 0x3a:
            a = pop(); emit('ABORT', x.off); return
        if op == 0x10:
            a = pop(); emit('PAUSE', x.off); return
        if op == 0x28:
            a = pop(); emit('DISCONNECT TIMER %s' % txt(a), x.off); return
        if op == 0x62:
            a = pop(); emit('CONNECT TIMER TO %s' % txt(a), x.off); return
        if op == 0x39:
            a = pop(); emit('CLOSE FILE %s' % txt(a), x.off); return
        if op == 0xa3:
            a = pop(); emit('CANCEL FILE %s' % txt(a), x.off); return
        if op == 0x3d:
            nm = pop(); md = pop(); f = pop()
            emit('OPEN FILE %s(%s, %s)' % (txt(f), txt(md), txt(nm)), x.off); return
        # WRITE / READ
        if op == 0xad:
            nx = self.ins[x.idx + 1] if x.idx + 1 < len(self.ins) else None
            if nx is not None and nx.op == 0x32:
                push(E('<sysfiles>'))
            return                                 # sinon : descripteur de type position (argument)
        if op in (0x37, 0x38):
            t = norm_type(x.u16())
            f2 = pop(); f1 = pop()
            v = pop() if t != 0x00d6 else None
            if v is not None and tc.kind((t, [])) in ('int', 'real', 'bool', 'str'):
                v = self.field0(v, 0x34)
            if t == 0x00d6:
                item = 'CR'
            else:
                k = tc.kind((t, []))
                item = txt(v, k)
                if t == 0x0011 and isinstance(f1, Const) and f1.raw == 13 and isinstance(f2, Const) and f2.raw == 0xfffffffb:
                    pass                           # format REAL par défaut
                elif not (isinstance(f1, Const) and f1.raw == 0 and isinstance(f2, Const) and f2.raw == 0):
                    item += '::%s' % txt(f1, 'int')
                    if not (isinstance(f2, Const) and f2.raw == 0):
                        item += '::%s' % txt(f2, 'int')
            # fichier : sous les items
            j = len(st) - 1
            while j >= 0 and not (isinstance(st[j], FileN) or (isinstance(st[j], E) and st[j].addr and st[j].kind == 'file')):
                j -= 1
            if j >= 0 and not isinstance(st[j], FileN):
                fn = FileN(st[j].text); st[j] = fn
            if j >= 0:
                st[j].items.append(item); st[j].mode = 'WRITE' if op == 0x37 else 'READ'
            else:
                emit('-- ?? %s item %s' % ('WRITE' if op == 0x37 else 'READ', item), x.off)
            return
        if op == 0x2c:
            if x.u8() == 1 and x.s16(2) == -1 and st and isinstance(st[-1], FileN):
                f = st.pop()
                fname = '' if f.text == 'TPDISPLAY' and False else ' ' + f.text
                emit('%s%s(%s)' % (f.mode or 'WRITE', fname, ', '.join(f.items)), x.off)
                return
            if x.u8() == 1 and x.s16(2) < 0:
                for _ in range(-x.s16(2)):
                    pop()
                return
            return
        if op == 0x3e:
            return
        r = self.cond_ops(x, st, emit)
        if r is not None:
            return r
        return False

    RELOPS = ['>', '>=', '=', '<>', '<=', '<']

    def cond_ops(self, x, st, emit):
        op = x.op

        def pop():
            return st.pop() if st else E('?')

        def cnode():
            for j in range(len(st) - 1, -1, -1):
                if isinstance(st[j], CondN) and not st[j].done:
                    return st[j]
            return None
        if op == 0xb5:
            st.append(E('<OR>', PREC_ATOM, 'ormark')); return True
        if op == 0x03:
            c = CondN('WAIT')
            if st and st[-1].kind == 'ormark':
                st.pop(); c.pending_or = True
            c.clauses.append([[], [], c.pending_or])
            st.append(c); return True
        if op == 0x25:
            v = pop(); st.append(E(txt(v, 'int'), PREC_ATOM, 'with%d' % x.u8())); return True
        if op == 0x81:
            w = None
            if st and st[-1].kind and str(st[-1].kind).startswith('with'):
                w = st.pop()
            n = pop()
            wt = None
            if w is not None:
                wt = '%s = %s' % ({1: '$SCAN_TIME'}.get(int(w.kind[4:]), '$WITH_%s' % w.kind[4:]), w.text)
            st.append(CondN('COND', txt(n, 'int'), wt)); return True
        if op == 0x18:
            orf = False
            if st and st[-1].kind == 'ormark':
                st.pop(); orf = True
            c = cnode()
            if c is None: return False
            c.clauses.append([[], [], orf]); return True
        if op == 0x1b:
            idx = pop(); pn = PORTS.get(x.u8(), 'PORT_%02X' % x.u8())
            st.append(E('%s[%s]' % (pn, txt(idx, 'int')), PREC_ATOM, PORT_KIND.get(pn), None, True)); return True
        if op == 0x12:
            cc = x.u8(); R = self.RELOPS
            c = cnode()
            if cc in (2, 3, 4, 5):
                p = pop(); t = txt(p)
                t = {2: t, 3: 'NOT ' + t, 4: t + '+', 5: t + '-'}[cc]
            elif 0x06 <= cc <= 0x0b or 0x0c <= cc <= 0x11:
                b = pop(); a = pop(); base = 0x06 if cc <= 0x0b else 0x0c
                k = 'real' if base == 0x0c else None
                t = '%s %s %s' % (txt(a, k), R[cc - base], txt(b, k))
            elif 0x1b <= cc <= 0x20 or 0x21 <= cc <= 0x26:
                b = pop(); a = pop(); base = 0x1b if cc <= 0x20 else 0x21
                k = 'real' if base == 0x21 else (a.kind if isinstance(a, E) and a.kind in ('int', 'bool') else 'int')
                t = '%s %s %s' % (txt(a), R[cc - base], txt(b, k))
            elif 0x27 <= cc <= 0x32 or 0x41 <= cc <= 0x4c:
                b = pop(); a = pop()
                base = {0x27: 0x27, 0x2d: 0x2d, 0x41: 0x41, 0x47: 0x47}[max(v for v in (0x27, 0x2d, 0x41, 0x47) if v <= cc)]
                k = 'bool' if cc >= 0x41 else 'int'
                t = '%s %s %s' % (txt(a), R[cc - base], txt(b, k))
            elif cc == 0x12:
                n = pop(); t = 'ERROR[%s]' % ('*' if isinstance(n, Const) and n.raw == 0xffffffff else txt(n, 'int'))
            elif cc == 0x13:
                n = pop(); t = 'EVENT[%s]' % txt(n, 'int')
            elif cc == 0x34:
                n = pop(); t = 'SEMAPHORE[%s]' % txt(n, 'int')
            elif cc in (0x18, 0x19, 0x33):
                pop(); t = {0x18: 'ABORT', 0x19: 'PAUSE', 0x33: 'CONTINUE'}[cc]
            else:
                t = '?? condition %02X' % cc
            if c is None: return False
            c.clause()[0].append(t); return True
        if op == 0x13:
            aa = x.u8(); c = cnode()
            if aa == 0x10:
                return True
            if aa in (0x14, 0x03):
                v = pop(); a = pop()
                t = '%s = %s' % (txt(a), txt(v, a.kind if isinstance(a, E) else None))
            elif aa in (0x15, 0x01):
                v = pop(); p = pop()
                t = '%s = %s' % (txt(p), txt(v, p.kind if isinstance(p, E) else None))
            elif aa == 0x02:
                p = pop(); a = pop(); t = '%s = %s' % (txt(a), txt(p))
            elif aa == 0x05:
                r = pop(); t = txt(r)
            elif aa in (0x0d, 0x0e):
                n = pop(); t = '%s CONDITION[%s]' % ('ENABLE' if aa == 0x0d else 'DISABLE', txt(n, 'int'))
            elif aa == 0x04:
                n = pop(); t = 'SIGNAL EVENT[%s]' % txt(n, 'int')
            elif aa == 0x0f:
                tm = pop(); p = pop(); t = 'PULSE %s FOR %s' % (txt(p), txt(tm, 'int'))
            elif aa in (0x1a, 0x09):
                t = 'NOABORT' if aa == 0x1a else 'NOPAUSE'
            elif aa in (0x1b, 0x1c, 0x07, 0x08, 0x11, 0x12, 0x0b, 0x16):
                pop()
                t = {0x1b: 'PAUSE', 0x1c: 'ABORT', 0x07: 'CANCEL', 0x08: 'STOP', 0x11: 'HOLD',
                     0x12: 'UNHOLD', 0x0b: 'RESUME', 0x16: 'UNPAUSE'}[aa]
            else:
                t = '?? action %02X' % aa
            if c is None: return False
            c.clause()[1].append(t); return True
        if op == 0xab:
            r = self.pc.routines[x.u16()]
            self.calledaa.add(x.u16())
            st.append(E(r['name'], PREC_ATOM, 'routine')); return True
        if op == 0x04:
            c = cnode()
            if c is None: return False
            c.done = True
            if c.ckind == 'COND':
                st.remove(c)
                lines = ['CONDITION[%s]:%s' % (c.num, (' WITH ' + c.with_) if c.with_ else '')]
                for (cs, acts, orf) in c.clauses:
                    lines.append('\tWHEN %s DO %s' % ((' OR ' if orf else ' AND ').join(cs), ', '.join(acts)))
                lines.append('ENDCONDITION')
                emit('\n'.join(lines), x.off)
            return True
        if op == 0x14:
            for j in range(len(st) - 1, -1, -1):
                if isinstance(st[j], CondN) and st[j].ckind == 'WAIT':
                    c = st.pop(j)
                    cs, _, orf = c.clauses[0]
                    emit('WAIT FOR %s' % (' OR ' if orf else ' AND ').join(cs), x.off)
                    return True
            return False
        SIMPLE_ST = {0x0d: 'ENABLE CONDITION[%s]', 0x0e: 'DISABLE CONDITION[%s]', 0x3c: 'PURGE CONDITION[%s]',
                     0x4d: 'SIGNAL EVENT[%s]'}
        if op in SIMPLE_ST:
            n = pop(); emit(SIMPLE_ST[op] % txt(n, 'int'), x.off); return True
        NOARG = {0x3b: 'CANCEL', 0x65: 'HOLD', 0x66: 'UNHOLD', 0x4f: 'STOP', 0x4e: 'RESUME'}
        if op in NOARG:
            pop(); emit(NOARG[op], x.off); return True
        return None

    # ------------------------------------------------------------ sortie
    def is_builtin_routine(self, k):
        r = self.pc.routines[k]
        if r['mod'] == 0:
            return False
        if k in self.called31:
            return True
        if k in self.calledaa:
            return False
        mod = self.pc.modules[r['mod'] - 1] if r['mod'] - 1 < len(self.pc.modules) else ''
        return False

    def emit_source(self, keep_lines=True):
        pc = self.pc; tc = self.tc
        L = []          # (ligne_souhaitée|None, texte)

        def add(t, ln=None):
            L.append((ln, t))

        add('PROGRAM %s' % pc.name)
        a = pc.attr
        if pc.comment:
            add("%%COMMENT = '%s'" % pc.comment)
        if a[0]: add('%POWERFAIL')
        if a[1]: add('%INVISIBLE')
        if a[2]: add('%SYSTEM')
        if a[3]: add('%NOBUSYLAMP')
        m = {1: 'ERROR', 2: 'COMMAND', 4: 'TPENABLE'}
        if a[4]: add('%NOABORT = ' + '+'.join(v for k, v in m.items() if a[4] & k))
        if a[5]: add('%NOPAUSE = ' + '+'.join(v for k, v in m.items() if a[5] & k))
        if a[7]: add('%TPMOTION')
        if a[8]: add('%NOPAUSESHFT')
        ss = (a[9] << 8) | a[10]
        if ss != 0xffff: add('%%STACKSIZE = %d' % ss)
        pr = (a[11] << 8) | a[12]
        if pr != 0xffff: add('%%PRIORITY = %d' % pr)
        ts = (a[13] << 8) | a[14]
        if ts != 0xffff: add('%%TIMESLICE = %d' % ts)
        if a[15]: add('%ALPHABETIZE')
        if a[18]: add('%FLASHROM')
        lg = a[17]
        if lg == 0:
            add('%NOLOCKGROUP')
        elif lg != 0xff:
            add('%%LOCKGROUP = %s' % ','.join(str(g + 1) for g in range(8) if lg & (1 << g)))
        # %UNINITVARS : le traducteur marque chaque variable du programme avec l'indicateur 0xFA
        own = [v for v in pc.vars if v[0] == 0 and not v[1].startswith('$')]
        if any(v[2] == 0xfa for v in own):
            add('%UNINITVARS')
            if any(v[2] == 0x00 for v in own):
                add('-- attention : variables avec et sans indicateur UNINITVARS (0xFA) mélangées')
        # %NOSCANSVARS (V7.50+) et %FASTCMOSVAR (V7.20-V7.40) : indicateur porté par chaque
        # variable sans IN CMOS / IN SHADOW explicite ; 0x03 et 0xFC respectivement
        for fl_, dname in ((0x03, '%NOSCANSVARS'), (0xfc, '%FASTCMOSVAR')):
            if any(v[2] == fl_ for v in own):
                add(dname)
                if any(v[2] == 0x00 for v in own):
                    add('-- attention : variables avec et sans indicateur %s (0x%02X) mélangées' % (dname[1:], fl_))
        unk = [(i, a[i]) for i in (6, 16, 19) if a[i]]
        if unk:
            add('-- attributs inconnus : %s' % unk)
        if NEGCONST:
            add('')
            add('CONST')
            for v, n in sorted(NEGCONST.items(), key=lambda z: z[1]):
                add('\t%s = %s' % (n, v))
        # types utilisateur
        ut = [t for t in pc.tdefs if not t['system']]
        if ut:
            add('')
            add('TYPE')
            for t in ut:
                if t['alias'] is not None:
                    add('\t%s = %s' % (t['name'], tc.name(t['alias'])))
                    continue
                add('\t%s = STRUCTURE' % t['name'])
                for (fn, fl, ft) in t['fields']:
                    if fn.startswith('$DUMMY'):
                        continue
                    add('\t\t%s : %s' % (fn, tc.name(ft)))
                add('\tENDSTRUCTURE')
        # variables
        vs = [v for v in pc.vars if v[0] != 0xff]
        if vs:
            add('')
            add('VAR')
            for (attr, nm, fl, ty) in vs:
                where = ''
                if fl == 0xfd: where = ' IN CMOS'
                elif fl == 0x02: where = ' IN SHADOW'
                frm = ''
                if attr:
                    frm = ' FROM %s' % (pc.modules[attr - 1] if attr - 1 < len(pc.modules) else '?')
                tn = tc.name(ty)
                note = '' if fl in (0x00, 0x02, 0x03, 0xfa, 0xfc, 0xfd) else '  -- indicateur de stockage inconnu 0x%02x' % fl
                add('\t%s%s%s : %s%s' % (nm, where, frm, tn, note))
        # déclarations de routines externes / avant (ordre de la table)
        order = sorted(self.routines, key=lambda r: r.i0)
        pos = {r.k: r.i0 for r in order}
        fwd = set()
        for r in order:
            for j in range(r.i0, r.i1):
                x = self.ins[j]
                if x.op == 0xaa:
                    k = x.u16()
                    if k in pos and pos[k] > r.i0:
                        fwd.add(k)
        decl = []
        for k, rr in enumerate(pc.routines):
            if k == 0:
                continue
            if rr['mod'] == 0 and k in fwd:
                decl.append((k, pc.name))
            elif rr['mod'] != 0 and not self.is_builtin_routine(k):
                decl.append((k, pc.modules[rr['mod'] - 1]))
        if decl:
            add('')
        self.fwd = fwd
        byk = {r.k: r for r in self.routines}
        for k, mod in decl:
            rr = pc.routines[k]
            names = byk[k].params if k in byk else None
            add('ROUTINE %s%s FROM %s' % (rr['name'], self.sig(rr, names), mod))
        for r in order:
            add('')
            if r.is_main:
                first = self.first_line(r.body)
                add('BEGIN', (first - 1) if (first and keep_lines) else None)
                self.emit_body(r.body, add, 1)
                add('END %s' % pc.name, self.end_line(r))
                continue
            if r.k in fwd:
                add('ROUTINE %s' % r.name)
            else:
                add('ROUTINE %s%s' % (r.name, self.sig(r.info, r.params)))
            self.emit_locals(r, add)
            first = self.first_line(r.body)
            add('BEGIN', (first - 1) if (first and keep_lines) else None)
            self.emit_body(r.body, add, 1)
            add('END %s' % r.name, self.end_line(r))
        if not any(r.is_main for r in self.routines):
            add('BEGIN')
            add('END %s' % pc.name)
        return self.layout(L, keep_lines)

    def end_line(self, r):
        # dernière instruction 3e du bloc de la routine
        for j in range(r.i1 - 1, r.i0 - 1, -1):
            if self.ins[j].op == 0x3e:
                return self.ins[j].u16()
        return None

    def first_line(self, body):
        for s in body:
            if s.kids is not None:
                v = self.first_line(s.kids)
                if v: return v
            elif s.line:
                return s.line
        return None

    def sig(self, info, names=None):
        ps = info['params']
        out = ''
        if ps:
            parts = []
            for j, t in enumerate(ps):
                nm = names[j][0] if names else 'p%d' % (j + 1)
                parts.append('%s: %s' % (nm, self.tc.name(t)))
            out = '(' + '; '.join(parts) + ')'
        if info['ret'][0]:
            out += ': %s' % self.tc.name(info['ret'])
        return out

    def emit_locals(self, r, add):
        if not r.locals:
            return
        add('VAR')
        for s in sorted(r.locals):
            nm, ty, _ = r.locals[s]
            add('\t%s : %s' % (nm, self.tc.name(ty) if ty else 'INTEGER'))

    def emit_body(self, body, add, depth):
        ind = '\t' * depth
        for s in body:
            if s.kids is not None:
                self.emit_body(s.kids, add, depth + 1)
                continue
            if s.text is None:
                continue
            t = s.text
            d = depth
            if t.startswith('CASE(') or t == 'ELSE:':
                add(ind + '\t' * 0 + t, s.line)
                continue
            add(ind + t, s.line)

    def layout(self, L, keep_lines):
        """place les lignes à leur numéro d'origine si possible"""
        out = []
        for (ln, t) in L:
            if keep_lines and ln:
                while len(out) + 1 < ln:
                    out.append('')
            out.append(t)
        return '\n'.join(out) + '\n'


def decompile_file(path, keep_lines=True, asm=False):
    pc = PC(load(path))
    d = Decompiler(pc, path).run()
    src = d.emit_source(keep_lines)
    if d.unknown:
        ops = ', '.join(sorted({'%02X' % x.b[0] for x in d.unknown}))
        bar = '-- ' + '#' * 70 + '\n'
        src = (bar +
               '-- ?? ATTENTION : %d instruction(s) non décodée(s) (opcode(s) inconnu(s) : %s).\n' % (len(d.unknown), ops) +
               '-- ??   Le programme est INCOMPLET : chercher "-- ??" et compléter à la main.\n' +
               bar + src)
    warn = list(dict.fromkeys(d.warn))            # un bloc peut être analysé deux fois
    if warn:
        src += '\n-- Avertissements du décompilateur :\n' + '\n'.join('--   ' + w for w in warn[:50]) + '\n'
    return src, d


def main():
    ap = argparse.ArgumentParser(description='Décompilateur KAREL .pc -> .kl')
    ap.add_argument('pc', nargs='+')
    ap.add_argument('-o', '--out', help='fichier de sortie (un seul .pc) ou dossier')
    ap.add_argument('--asm', action='store_true', help='affiche le désassemblage')
    ap.add_argument('--no-lines', action='store_true', help='ne pas recaler les numéros de ligne')
    a = ap.parse_args()
    files = []
    for p in a.pc:
        if os.path.isdir(p):
            files += sorted(os.path.join(p, f) for f in os.listdir(p) if f.lower().endswith('.pc'))
        else:
            files.append(p)
    if len(files) > 1 and a.out and not os.path.isdir(a.out):
        os.makedirs(a.out, exist_ok=True)
    for p in files:
        try:
            src, d = decompile_file(p, not a.no_lines)
        except Exception as e:
            msg = repr(e)
            try:                                   # diagnostic : opcode jamais observé ?
                ins = disasm(PC(load(p)).pcode)
                if ins and ins[-1].op == -1:
                    msg = ('opcode %02X inconnu à @%04x : construction absente du corpus de test, '
                           'la suite du programme ne peut pas être décodée (%r)' % (ins[-1].b[0], ins[-1].off, e))
                    if a.asm:
                        for x in ins:
                            print(x)
            except Exception:
                pass
            print('ERREUR %s : %s' % (p, msg), file=sys.stderr)
            continue
        if a.asm:
            for x in d.ins:
                print(x)
        if a.out:
            o = a.out
            if os.path.isdir(o):
                o = os.path.join(o, os.path.splitext(os.path.basename(p))[0] + '.kl')
            open(o, 'w', encoding='latin-1').write(src)
            n = src.count('-- ??')
            print('%s -> %s%s' % (p, o, ('   (%d point(s) à vérifier : chercher "-- ??")' % n) if n else ''))
            if d.unknown:
                print('  ATTENTION : %d instruction(s) non décodée(s), opcode(s) inconnu(s) %s : sortie INCOMPLÈTE'
                      % (len(d.unknown), ', '.join(sorted({'%02X' % x.b[0] for x in d.unknown}))), file=sys.stderr)
        else:
            sys.stdout.write(src)


if __name__ == '__main__':
    main()
