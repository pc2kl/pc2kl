import sys
def unlzss(data, N=4096, F=18, T=2, fill=0x00):
    buf = bytearray([fill])*N; r = N-F; out = bytearray(); i=0; flags=0
    while i < len(data):
        flags >>= 1
        if not (flags & 0x100):
            flags = data[i] | 0xff00; i+=1
            if i>=len(data): break
        if flags & 1:
            c=data[i]; i+=1; out.append(c); buf[r]=c; r=(r+1)&(N-1)
        else:
            if i+1>=len(data): break
            a=data[i]; b=data[i+1]; i+=2
            p = a | ((b&0xf0)<<4); l=(b&0x0f)+T
            for k in range(l+1):
                c=buf[(p+k)&(N-1)]; out.append(c); buf[r]=c; r=(r+1)&(N-1)
    return bytes(out)
if __name__=='__main__':
    d=open(sys.argv[1],'rb').read()
    off=int(sys.argv[2]) if len(sys.argv)>2 else 8
    o=unlzss(d[off:]); sys.stdout.buffer.write(o)
