/* SPDX-License-Identifier: GPL-2.0-only OR MIT */
/*
 * ane_fw_validate.h — selene PRELOAD payload validator, W13.
 *
 * Single source of truth shared by the kernel loader
 * (ane_t6021_fwload.c) and the offline regression
 * (tools/h14_fwload_regression.c, userspace). Strict EXACT-image
 * assertions (no generic Mach-O parsing): the pinned t6021 selene
 * payload has exactly 7 load commands, 3 segments, entry 0, and zeroed
 * bootstrap page tables, per
 * receipts/2026-09-19-h14-w13-boot-contract.md.
 *
 * Userspace consumers typedef u8/u32/u64/size_t/bool and provide
 * get_unaligned_le32/64 + memcmp (see tools/h14_fwload_regression.c);
 * kernel consumers get these from linux/types.h + linux/string.h.
 * This header intentionally includes nothing.
 */
#ifndef __ANE_FW_VALIDATE_H__
#define __ANE_FW_VALIDATE_H__

#define ANE_FW_BLOB_SIZE	0x1a4000
#define ANE_FW_BUF_SIZE		0x400000	/* covers vmsize 0x36c000 */
#define ANE_FW_ENTRY_PC		0x0

#define MH_MAGIC_64	0xfeedfacfU
#define MH_PRELOAD	5
#define CPU_TYPE_ARM64	0x0100000cU
#define LC_SEGMENT_64	0x19
#define LC_UNIXTHREAD	0x5
#define ARM_THREAD_STATE64 6

#define ANE_FW_NCMDS		7
#define ANE_FW_SIZEOF_CMDS	0xae8
#define ANE_FW_FLAGS		0x200001
#define ANE_FW_NSEGS		3

struct ane_fw_seg {
	u64 vmaddr;
	u64 vmsize;
	u64 fileoff;
	u64 filesize;
	char name[17];		/* 16 + NUL */
};

/* exact pinned layout (W13 parse of payload 9f7915c431d288a2…) */
static const struct ane_fw_seg ane_fw_expected_segs[ANE_FW_NSEGS] = {
	{ 0x000000, 0x0e8000, 0x004000, 0x0e8000, "__TEXT" },
	{ 0x0e8000, 0x284000, 0x0ec000, 0x0b8000, "__DATA" },
	{ 0x36c000, 0x000000, 0x1a4000, 0x000000, "__DATA_CONST" },
};

/* Validate a candidate payload.  Returns 0 on pass, else -1 with
 * *reason set.  expected_sha = pinned SHA-256; actual_sha =
 * caller-computed SHA-256 of blob (kernel: sha256(); regression: local
 * implementation). */
static inline int
ane_fw_validate_blob(const u8 *blob, size_t size,
		     const u8 expected_sha[32], const u8 actual_sha[32],
		     struct ane_fw_seg *segs_out, u64 *entry_out,
		     const char **reason)
{
	u32 magic, cputype, filetype, ncmds, sizeofcmds, flags;
	u32 off, i, nsegs = 0;
	u64 entry = (u64)~0ULL;

	if (size != ANE_FW_BLOB_SIZE) {
		*reason = "size != 0x1a4000";
		return -1;
	}
	if (memcmp(expected_sha, actual_sha, 32) != 0) {
		*reason = "sha256 != pinned payload hash";
		return -1;
	}

	magic = get_unaligned_le32(blob + 0);
	cputype = get_unaligned_le32(blob + 4);
	filetype = get_unaligned_le32(blob + 12);
	ncmds = get_unaligned_le32(blob + 16);
	sizeofcmds = get_unaligned_le32(blob + 20);
	flags = get_unaligned_le32(blob + 24);

	if (magic != MH_MAGIC_64) {
		*reason = "magic";
		return -1;
	}
	if (cputype != CPU_TYPE_ARM64) {
		*reason = "cputype";
		return -1;
	}
	if (filetype != MH_PRELOAD) {
		*reason = "filetype != MH_PRELOAD";
		return -1;
	}
	if (ncmds != ANE_FW_NCMDS || sizeofcmds != ANE_FW_SIZEOF_CMDS ||
	    flags != ANE_FW_FLAGS) {
		*reason = "header fields != pinned image";
		return -1;
	}

	off = 32;
	for (i = 0; i < ncmds; i++) {
		u32 cmd, cmdsize;

		if (off + 8 > 32 + sizeofcmds || off + 8 > size) {
			*reason = "load command header out of bounds";
			return -1;
		}
		cmd = get_unaligned_le32(blob + off);
		cmdsize = get_unaligned_le32(blob + off + 4);
		if (cmdsize < 8 || off + cmdsize > 32 + sizeofcmds ||
		    off + cmdsize > size) {
			*reason = "cmdsize out of bounds";
			return -1;
		}

		if (cmd == LC_SEGMENT_64) {
			u64 vmaddr = get_unaligned_le64(blob + off + 24);
			u64 vmsize = get_unaligned_le64(blob + off + 32);
			u64 fileoff = get_unaligned_le64(blob + off + 40);
			u64 filesize = get_unaligned_le64(blob + off + 48);
			const char *sname = (const char *)blob + off + 8;
			unsigned int k;

			if (fileoff > size || filesize > size - fileoff) {
				*reason = "segment file range out of bounds";
				return -1;
			}
			if (filesize > vmsize) {
				*reason = "filesize > vmsize";
				return -1;
			}
			for (k = 0; k < ANE_FW_NSEGS; k++) {
				if (vmaddr == ane_fw_expected_segs[k].vmaddr &&
				    vmsize == ane_fw_expected_segs[k].vmsize &&
				    fileoff == ane_fw_expected_segs[k].fileoff &&
				    filesize == ane_fw_expected_segs[k].filesize &&
				    !memcmp(sname, ane_fw_expected_segs[k].name,
					    16)) {
					if (segs_out)
						segs_out[nsegs] =
							ane_fw_expected_segs[k];
					break;
				}
			}
			if (k == ANE_FW_NSEGS) {
				*reason = "segment != pinned layout";
				return -1;
			}
			nsegs++;
		} else if (cmd == LC_UNIXTHREAD) {
			u32 p = off + 8;

			/* thread commands: flavor u32, count u32
			 * (count = number of 32-bit words in state) */
			while (p + 8 <= off + cmdsize) {
				u32 flavor = get_unaligned_le32(blob + p);
				u32 count = get_unaligned_le32(blob + p + 4);

				if (count > (cmdsize - (p - off) - 8) / 4) {
					*reason = "thread state count out of bounds";
					return -1;
				}
				if (flavor == ARM_THREAD_STATE64) {
					/* 33 u64 registers; PC at index 32:
					 * requires count*4 >= 33*8 bytes */
					if (count < 66 ||
					    p + 8 + count * 4 > off + cmdsize) {
						*reason = "thread state too small for pc";
						return -1;
					}
					entry = get_unaligned_le64(blob + p + 8 +
								   32 * 8);
				}
				p += 8 + count * 4;
			}
		}
		off += cmdsize;
	}

	if (nsegs != ANE_FW_NSEGS) {
		*reason = "segment count != 3";
		return -1;
	}
	if (entry != ANE_FW_ENTRY_PC) {
		*reason = "entry pc != 0";
		return -1;
	}

	if (segs_out) {
		for (i = 0; i < ANE_FW_NSEGS; i++)
			segs_out[i] = ane_fw_expected_segs[i];
	}
	if (entry_out)
		*entry_out = entry;
	return 0;
}
#endif /* __ANE_FW_VALIDATE_H__ */
