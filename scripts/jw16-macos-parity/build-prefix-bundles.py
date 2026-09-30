#!/usr/bin/env python3
"""Build well-formed TD-prefix bundles from the whole-encoder ANEC (jw16 /tmp/decomp).

Prefix of k tasks: copy stream bytes through end of task k-1, zero its
header[7] next-pointer, append a copy of the file's 1-word final terminator
(0x84354003), declare td_count=k+1, fix manifest task_descriptors +
payload sha256. The kernel section is the FULL original (prefix tasks address
weights by absolute kernel-BO offset up to the prefix reach, and the tail must
stay valid); only the task stream is truncated. tsk/krn header fields are kept
from the original; size = len(task stream) + krn section. Run from /tmp/decomp
on jw16; outputs pfx-{k}/.
"""
import struct, json, hashlib, os, sys

SRC = "/var/tmp/encoder-whole/bundle"
HDR = 0x1000

def main(ks):
    with open(SRC + "/program-0.anec", "rb") as f:
        data = f.read()
    offs = [HDR]
    while True:
        h = struct.unpack("<10I", data[offs[-1]:offs[-1] + 40])
        if h[7] == 0:
            break
        offs.append(HDR + h[7])
    fterm = data[offs[-1]:offs[-1] + 4]
    for k in ks:
        assert 0 < k < len(offs)
        last = offs[k - 1]
        h = list(struct.unpack("<10I", data[last:last + 40]))
        sz = ((h[1] >> 16) & 0x1FF) + 1
        ext = 1 if ((h[9] & 3) == 3) else 0
        p, used = last + 40 + ext * 4, 10 + ext
        while used < sz:
            rh = struct.unpack("<I", data[p:p + 4])[0]
            cnt = (rh >> 26) + 1
            p += 4 + cnt * 4
            used += 1 + cnt
        # kernel reach of this prefix: max over tasks of (16 addrs @0x1f848 +
        # 16 sizes @0x1f888); tasks without the pair contribute 0.
        reach = 0
        ro = HDR
        for _ in range(k):
            hh = struct.unpack("<10I", data[ro:ro + 40])
            ssz = ((hh[1] >> 16) & 0x1FF) + 1
            xext = 1 if ((hh[9] & 3) == 3) else 0
            pp, uused = ro + 40 + xext * 4, 10 + xext
            aaddrs, ssizes = [], []
            while uused < ssz:
                rrh = struct.unpack("<I", data[pp:pp + 4])[0]
                ccnt = (rrh >> 26) + 1
                bbase = rrh & 0x03FFFFFF
                if bbase <= 0x1F848 < bbase + ccnt * 4:
                    ii = (0x1F848 - bbase) // 4
                    aaddrs = list(struct.unpack("<%dI" % 16, data[pp + 4 + ii * 4:pp + 4 + ii * 4 + 64]))
                if bbase <= 0x1F888 < bbase + ccnt * 4:
                    ii = (0x1F888 - bbase) // 4
                    ssizes = list(struct.unpack("<%dI" % 16, data[pp + 4 + ii * 4:pp + 4 + ii * 4 + 64]))
                pp += 4 + ccnt * 4
                uused += 1 + ccnt
            if aaddrs and ssizes:
                reach = max(reach, max(a + s for a, s in zip(aaddrs, ssizes)))
            if hh[7] == 0:
                break
            ro = HDR + hh[7]
        reach = (reach + 15) & ~15
        # original kernel section starts at file HDR+align16(tsk_orig)
        tsk_orig = struct.unpack("<Q", data[16:24])[0]
        krn_orig = struct.unpack("<Q", data[24:32])[0]
        ksrc = HDR + ((tsk_orig + 15) & ~15)
        kbytes = data[ksrc:ksrc + krn_orig]
        assert len(kbytes) == krn_orig, (len(kbytes), krn_orig)
        new_stream = bytearray(data[HDR:p])
        lo = last - HDR
        new_stream[lo + 28:lo + 32] = struct.pack("<I", 0)
        new_stream += fterm
        # pad stream to 16 so the kernel section keeps its alignment
        while len(new_stream) % 16:
            new_stream.append(0)
        tsk_new = len(new_stream)
        # keep only the kernel bytes this prefix can address (reach), cut to
        # 16; the tail is unaddressable by construction (addrs are dense per
        # the kreach scan: task 13699 reaches 447806272 = krn end).
        kcut = (reach + 15) & ~15
        assert kcut <= krn_orig, (kcut, krn_orig)
        hdr = bytearray(data[:HDR])
        struct.pack_into("<Q", hdr, 0, tsk_new + kcut)
        struct.pack_into("<I", hdr, 12, k + 1)
        struct.pack_into("<Q", hdr, 16, tsk_new)
        struct.pack_into("<Q", hdr, 24, kcut)
        blob = bytes(hdr) + bytes(new_stream) + kbytes[:kcut]
        outdir = "/tmp/decomp/pfx-%d" % k
        os.makedirs(outdir, exist_ok=True)
        open(outdir + "/program-0.anec", "wb").write(blob)
        m = json.load(open(SRC + "/manifest.json"))
        m["programs"][0]["task_descriptors"] = k + 1
        m["task_descriptors"] = k + 1
        m["payloads"][0]["byte_size"] = len(blob)
        m["payloads"][0]["sha256"] = hashlib.sha256(blob).hexdigest()
        # collection hash: nlohmann object_t is std::map -> keys ALPHABETICAL
        # (byte_size,path,role,sha256). Reproduces whole model_sha256 b4f906dc.
        m["release_asset"]["model_sha256"] = hashlib.sha256(
            ('[{"byte_size":%d,"path":"program-0.anec","role":"anec","sha256":"%s"}]'
             % (len(blob), m["payloads"][0]["sha256"])).encode()).hexdigest()
        json.dump(m, open(outdir + "/manifest.json", "w"), indent=1)

if __name__ == "__main__":
    main([int(x) for x in sys.argv[1:]] or [10, 100, 1000, 4567])
