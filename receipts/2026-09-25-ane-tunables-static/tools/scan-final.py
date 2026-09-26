#!/usr/bin/env bash
# Comprehensive per-segment scan: every segment of every cache.
set -uo pipefail
python3 - <<'PY'
import struct, sys
sys.path.insert(0,'/var/tmp/tunables')
from scan3 import load_macho_segments, fo2va, TERM, Z4, ok_entry

def scan_range(data, segs, lo, hi, minn=4):
    out=[]
    s=lo
    while True:
        i=data.find(TERM,s,hi)
        if i<0: break
        s=i+1
        if data[i-4:i]!=Z4: continue
        entries=[]; ent=i-20
        while ent>=lo:
            if data[ent-4:ent]!=Z4: break
            off,clr,setv,pad=struct.unpack_from('<IIII',data,ent)
            if pad!=0 or not ok_entry(off): break
            entries.append((off,clr,setv)); ent-=20
        if len(entries)>=minn:
            va,seg=fo2va(segs,ent+20)
            out.append((ent+20,va,seg,len(entries),entries))
    return out

files={
 'T8103-mac13g':'/var/tmp/jwm1-kc/kernelcache.release.mac13g.macho',
 'T6001-mac13j':'/var/tmp/jw16-kc/kernelcache.release.mac13j.macho',
 'T6001-25G83':'/var/tmp/levers5/out/out/kernel-live.release.bin',
 'T6021-13.5':'/var/tmp/t6021-kc/kernelcache.t6020.13.5-22G74.macho',
 'T6021-27.0':'/var/tmp/t6021-kc/kernelcache.t6020.27.0-26A428.macho',
}
summary={}
for name,path in files.items():
    data=open(path,'rb').read()
    segs=load_macho_segments(data)
    tot=0
    per={}
    for sname,vm,msz,fo,fsz in segs:
        tabs=scan_range(data,segs,fo,fo+fsz)
        per[sname]=len(tabs)
        tot+=len(tabs)
        for tfo,tva,tseg,n,entries in tabs:
            if name!='T8103-mac13g':
                print(f'!! {name} TABLE {sname} file={tfo:#x} va={tva:#x} n={n} first={entries[0]}')
    summary[name]=(tot,per)
for name,(tot,per) in summary.items():
    print(f'{name}: total={tot} per-segment={per}')
PY