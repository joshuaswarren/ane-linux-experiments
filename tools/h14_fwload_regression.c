/* SPDX-License-Identifier: GPL-2.0-only OR MIT
 *
 * Offline regression for the W13 selene PRELOAD validator
 * (ane_fw_validate.h) — userspace twin of the kernel call path.
 * Builds as plain C (shims for the kernel types/macros the header
 * uses; SHA-256 via OpenSSL, same digest the kernel's sha256()
 * produces).
 *
 * Build:  gcc -Wall -O2 -o h14_fwload_regression h14_fwload_regression.c -lcrypto
 * Run:    ./h14_fwload_regression /path/to/t602x_ane0_fw_selene_rc4x.macho
 * Exit 0 = every positive and negative case behaved as asserted.
 */
#include <openssl/sha.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;

static u32 get_unaligned_le32(const u8 *p)
{
	return (u32)p[0] | ((u32)p[1] << 8) | ((u32)p[2] << 16) |
	       ((u32)p[3] << 24);
}

static u64 get_unaligned_le64(const u8 *p)
{
	return (u64)get_unaligned_le32(p) |
	       ((u64)get_unaligned_le32(p + 4) << 32);
}

#include "ane_fw_validate.h"

static const u8 pinned_sha[32] = {
	0x9f, 0x79, 0x15, 0xc4, 0x31, 0xd2, 0x88, 0xa2,
	0xbd, 0xc2, 0x13, 0x2c, 0x39, 0x9d, 0xb8, 0xcf,
	0x55, 0x74, 0x71, 0x6a, 0x3b, 0x1e, 0x94, 0xaf,
	0x76, 0xbe, 0x6a, 0x29, 0x1c, 0x2e, 0x66, 0x5b,
};

static int failures;
static int passes;

static void report(const char *case_name, int want_pass, int got,
		   const char *reason)
{
	if ((want_pass && got == 0) || (!want_pass && got != 0)) {
		passes++;
		printf("PASS %-28s (%s)\n", case_name,
		       want_pass ? "accepted" : reason ? reason : "rejected");
	} else {
		failures++;
		printf("FAIL %-28s want=%s got=%d reason=%s\n", case_name,
		       want_pass ? "pass" : "reject", got,
		       reason ? reason : "-");
	}
}

static u8 *slurp(const char *path, size_t *len)
{
	FILE *f = fopen(path, "rb");
	u8 *b;
	long sz;

	if (!f)
		return NULL;
	fseek(f, 0, SEEK_END);
	sz = ftell(f);
	fseek(f, 0, SEEK_SET);
	b = malloc((size_t)sz);
	if (!b || fread(b, 1, (size_t)sz, f) != (size_t)sz) {
		fclose(f);
		free(b);
		return NULL;
	}
	fclose(f);
	*len = (size_t)sz;
	return b;
}

int main(int argc, char **argv)
{
	size_t len;
	u8 *blob, sha[32], actual[32];
	u8 *mut;
	struct ane_fw_seg segs[8];
	u64 entry;
	const char *reason = NULL;
	u32 off, i;
	int got;

	if (argc != 2) {
		fprintf(stderr, "usage: %s <selene.macho>\n", argv[0]);
		return 2;
	}
	blob = slurp(argv[1], &len);
	if (!blob || len != ANE_FW_BLOB_SIZE) {
		fprintf(stderr, "cannot read %s (or wrong size)\n", argv[1]);
		return 2;
	}

	SHA256(blob, len, actual);
	got = ane_fw_validate_blob(blob, len, pinned_sha, actual, segs,
				   &entry, &reason);
	report("positive: staged image", 1, got, reason);
	if (got == 0) {
		printf("     segs: ");
		for (i = 0; i < ANE_FW_NSEGS; i++)
			printf("%s@%#llx ", segs[i].name,
			       (unsigned long long)segs[i].vmaddr);
		printf("entry=%#llx\n", (unsigned long long)entry);
	}

	/* negative: wrong sha (one bit flipped in the hash we claim) */
	memcpy(sha, actual, 32);
	sha[0] ^= 0x01;
	got = ane_fw_validate_blob(blob, len, sha, actual, segs, &entry,
				   &reason);
	report("negative: claimed-sha mismatch", 0, got, reason);

	/* negative: size truncation */
	got = ane_fw_validate_blob(blob, len - 1, pinned_sha, actual, segs,
				   &entry, &reason);
	report("negative: truncated size", 0, got, reason);

	/* negative: bad magic */
	mut = malloc(len);
	memcpy(mut, blob, len);
	mut[3] ^= 0xff;
	SHA256(mut, len, actual);
	got = ane_fw_validate_blob(mut, len, pinned_sha, actual, segs,
				   &entry, &reason);
	report("negative: magic", 0, got, reason);

	/* negative: cmdsize corruption -> out-of-bounds walk.
	 * expected=actual(sha of mutant): bypasses the hash gate so the
	 * structural assertion under test is what fires. */
	memcpy(mut, blob, len);
	/* first LC starts at 32; blow its cmdsize */
	off = 32;
	mut[off + 7] ^= 0xff;
	SHA256(mut, len, actual);
	got = ane_fw_validate_blob(mut, len, actual, actual, segs,
				   &entry, &reason);
	report("negative: cmdsize overflow", 0, got, reason);

	/* negative: entry pc != 0 — locate LC_UNIXTHREAD by walking
	 * commands with the same bounds checks, patch its pc field */
	memcpy(mut, blob, len);
	off = 32;
	for (i = 0; i < ANE_FW_NCMDS; i++) {
		u32 cmd = get_unaligned_le32(mut + off);
		u32 cmdsize = get_unaligned_le32(mut + off + 4);

		if (cmd == LC_UNIXTHREAD) {
			/* thread cmd: 8-byte head, 8-byte flavor+count,
			 * 33 regs; pc = index 32 -> byte offset +8+256 */
			u32 pc_off = off + 8 + 8 + 32 * 8;

			mut[pc_off + 3] = 0x01;
			break;
		}
		off += cmdsize;
	}
	SHA256(mut, len, actual);
	got = ane_fw_validate_blob(mut, len, actual, actual, segs,
				   &entry, &reason);
	report("negative: entry != 0", 0, got, reason);

	/* negative: segment vmaddr perturbation */
	memcpy(mut, blob, len);
	mut[32 + 24] ^= 0x01;	/* first LC_SEGMENT_64 vmaddr low byte */
	SHA256(mut, len, actual);
	got = ane_fw_validate_blob(mut, len, actual, actual, segs,
				   &entry, &reason);
	report("negative: segment layout", 0, got, reason);

	free(mut);
	free(blob);
	printf("\n%d passed, %d failed\n", passes, failures);
	return failures ? 1 : 0;
}
