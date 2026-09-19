import sys; sys.path.insert(0,'.')
from kx import KX
k=KX('../kext-h14j/AppleH11ANEInterface-10.19.2-mac14j-26A428')
m=k.m
B=0xfffffe0000000000
def find_start(pc, maxback=0x8000):
    a=pc
    while a>pc-maxback:
        v=k.insns.get(a)
        if v and v[0]=="bti" and v[1]=="c":
            return a
        a-=4
    return None
targets={
 "InitializeRTBuddyEndpoints":B|0x95ff924,
 "SetupEndpoints":B|0x95fe764,
 "EnableRTBuddyEndpoints":B|0x95fec30,
 "rtbuddyEndpointSendInPlace":B|0x95f33e8,
 "rtbuddyEndpointSendMessage":B|0x95f3a30,
 "handleSharedMemoryRequest_gated":B|0x95f9a84,
 "processSharedMallocRequestEndpoint":B|0x95f9434,
 "processTargetToHostIOCommand":B|0x959c290,
 "drainRtbuddyEndpointQueues":B|0x95ec0b8,
 "rtbuddyOpenEndpoint_helper":B|0x95fe660,
}
for tag,ref in targets.items():
    st=find_start(ref)
    if st is None: print("NOSTART",tag); continue
    end=st; saw_ret=False
    for ad in range(st, st+0xa000, 4):
        v=k.insns.get(ad)
        if v:
            mn=v[0]
            if saw_ret and mn=="bti": break
            if mn in ("retab","ret"): saw_ret=True
            end=ad+4
        else:
            end=ad+4
    lines=[]
    for ad in range(st,end,4):
        v=k.insns.get(ad)
        if v:
            mn,ops=v
            ann=""
            s=m.cstr(ad)
            if mn=="bl" and ops.startswith("#"):
                t=int(ops.lstrip('#'),0); n2=m.addr_name(t)
                if n2: ann=f"  ; {n2[:72]}"
            if s: ann+=f'  ; "{s[:56]}"'
            lines.append(f"{ad:#x}: {mn:<8s} {ops}{ann}")
    open(f"asm/{tag}.asm","w").write(f"; {tag} [{st:#x}-{end:#x}) {end-st:#x} bytes\n"+"\n".join(lines))
    print(f"{tag:36s} [{st:#x}-{end:#x}) {end-st:#x}")

extra={
 "HandleRTBuddyMessage_real":B|0x95ff024,
 "ANEFWRpcMsg_create_real":B|0x95a6d80,
 "ANEFWRpcMsg_use":B|0x95a84ec,
 "processSharedMemoryCommand_real":B|0x95f9070,
}
for tag,ref in extra.items():
    st=find_start(ref)
    if st is None: print("NOSTART",tag); continue
    end=st; saw_ret=False
    for ad in range(st, st+0xa000, 4):
        v=k.insns.get(ad)
        if v:
            mn=v[0]
            if saw_ret and mn=="bti": break
            if mn in ("retab","ret"): saw_ret=True
            end=ad+4
        else: end=ad+4
    lines=[]
    for ad in range(st,end,4):
        v=k.insns.get(ad)
        if v:
            mn,ops=v
            ann=""
            s=m.cstr(ad)
            if mn=="bl" and ops.startswith("#"):
                t=int(ops.lstrip('#'),0); n2=m.addr_name(t)
                if n2: ann=f"  ; {n2[:72]}"
            if s: ann+=f'  ; "{s[:56]}"'
            lines.append(f"{ad:#x}: {mn:<8s} {ops}{ann}")
    open(f"asm/{tag}.asm","w").write(f"; {tag} [{st:#x}-{end:#x}) {end-st:#x} bytes\n"+"\n".join(lines))
    print(f"{tag:36s} [{st:#x}-{end:#x}) {end-st:#x}")
