"""Parser du format FANUC KAREL .pc (p-code)."""
import struct
from lzss import unlzss


class R:
    def __init__(s,d,p=0): s.d=d; s.p=p
    def u8(s): v=s.d[s.p]; s.p+=1; return v
    def u16(s): v=struct.unpack_from('>H',s.d,s.p)[0]; s.p+=2; return v
    def s16(s): v=struct.unpack_from('>h',s.d,s.p)[0]; s.p+=2; return v
    def u32(s): v=struct.unpack_from('>I',s.d,s.p)[0]; s.p+=4; return v
    def cstr(s):
        e=s.d.index(0,s.p); v=s.d[s.p:e].decode('latin-1'); s.p=e+1; return v
    def raw(s,n): v=s.d[s.p:s.p+n]; s.p+=n; return v

def load(path):
    raw=open(path,'rb').read()
    if raw[:2]==b'\xfe\xef':
        size=struct.unpack_from('>I',raw,4)[0]
        d=unlzss(raw[8:])[:size]
    else:
        d=raw
    return d

OLDFMT=[False]
def norm_type(t):
    if not OLDFMT[0]: return t
    hi,lo=t>>8,t&0xff
    b=hi&0x1f
    if b==0x08: b=0x1f
    elif b in (0x10,0x18): b=0x11
    return ((hi&0x60)|b)<<8|lo
def read_type(r, withdims=True):
    """Type code u16 + dimensions (tableaux) + extras (PATH)."""
    t=norm_type(r.u16())
    hi=t>>8
    dims=[]
    nd=(hi>>5)&3
    if withdims:
        for _ in range(nd): dims.append(r.u16())
    if t==0x001f:          # PATH : type d'en-tête, ?, type de noeud
        dims=[norm_type(r.u16()),r.u16(),norm_type(r.u16())]
    return (t,dims)

def parse_types(raws):
    out=[]
    for b in raws:
        r=R(b); attr=r.u8(); name=r.cstr(); nf=r.u8(); fields=[]
        for _ in range(nf):
            fn=r.cstr(); fl=r.u8(); ft=read_type(r); fields.append((fn,fl,ft))
        alias = fields[0][2] if (nf==1 and fields[0][0]=='') else None
        out.append(dict(name=name, system=(attr!=0), fields=fields, alias=alias))
    return out

class PC:
    def __init__(s,d):
        s.d=d; r=R(d)
        s.fmt=r.u16(); s.pcsize=r.u16()
        OLDFMT[0] = s.fmt < 0x26
        s.name=r.cstr(); s.comment=r.cstr()
        s.old = s.fmt < 0x26          # anciens formats (V6.x) : codes de type et en-tête différents
        if s.old:
            a=r.raw(19); s.attr=a[:16]+b'\x00'+a[16:]
            if s.attr[17]==0x1f: s.attr=s.attr[:17]+b'\xff'+s.attr[18:]
        else:
            s.attr=r.raw(20)
        s.pc_off=r.p
        s.pcode=d[r.p:r.p+s.pcsize]
        r.p+=s.pcsize
        s.post_off=r.p
        s.pfx = 2 if s.fmt>=0x27 else 1
        while d[r.p]!=0xff: r.p+=1
        r.p+=1
        nl=r.u16(); s.labels=[r.u32() for _ in range(nl)]
        nm=r.u16(); s.modules=[r.cstr() for _ in range(nm)]
        s.types_off=r.p
        nt=r.u16(); s.types=[]
        for _ in range(nt):
            ln=r.u16(); s.types.append(r.raw(ln))
        s.tdefs=parse_types(s.types)
        s.vars_off=r.p
        nv=r.u16(); s.vars=[]
        for _ in range(nv):
            a=r.u8(); nm_=r.cstr(); fl=r.u8()
            ty=read_type(r)
            s.vars.append((a,nm_,fl,ty))
        nu=r.u16(); s.usedvars=[r.u16() for _ in range(nu)]
        nr=r.u16(); s.routines=[]
        for _ in range(nr):
            nm_=r.cstr(); mod=r.u8(); off=r.u16(); rt=read_type(r,False); np_=r.u8()
            ps=[read_type(r,False) for _ in range(np_)]
            s.routines.append(dict(name=nm_,mod=mod,off=off,ret=rt,params=ps))
        s.tail=d[r.p:]

if __name__=='__main__':
    import sys
    for f in sys.argv[1:]:
        try:
            p=PC(load(f))
            print(f, p.name, 'labels',len(p.labels),'mods',p.modules,'types',len(p.types),'vars',len(p.vars),'rout',[x['name'] for x in p.routines],'tail',p.tail.hex(' '))
        except Exception as e:
            import traceback; print(f,'ERR',repr(e))
