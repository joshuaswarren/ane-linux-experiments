/* ane-probe2.c — timing + byte-identity instrumentation over libane boundaries.
 *
 * Measures, per ANE program (anec), with no behaviour change to the stack:
 *   info    — anec header + derived channel map
 *   floor   — back-to-back single-TD submits (exec ioctl round trip only)
 *   decomp  — per-submit phase split: send (staging) / exec / read (retrieval)
 *   chain   — N identical TDs in ONE submission (td_count=N, TD array at
 *             stride td_size in a dedicated btsp BO)
 *   verify  — numeric spot check against an expected fp16 file (signed-zero
 *             tolerant, same rule as the worker tool)
 *   verify2 — reps× same-input submits in ONE process: per-dst FNV per rep,
 *             every rep must equal rep 0 (reuse-staleness cell); rep-0
 *             hashes are the byte-identity reference across mapping modes
 *
 * Build: gcc -O2 -o ane-probe ane-probe.c -I<uapi> -I<libane>
 */
/* ane-probe2.c — ane-probe + verify2 for mapping-mode A/B.
 *
 * verify2 — one process, one nn, reps× same-input submits: send all srcs
 * (fixed deterministic fill; optional file for src0), then per rep exec and
 * FNV-hash every dst. Every rep must match rep 0 (catches reuse staleness:
 * missing invalidation between rounds is intermittent by nature). Printed
 * rep-0 hashes are the byte-identity reference for a baseline mapping mode.
 *
 * Build: gcc -O2 -o ane-probe2 ane-probe2.c -I<uapi> -I<libane>
 */
#include <asm/types.h>
#include <drm.h>
#define LIBANE_CONFIG_NO_STATIC_ASSERT
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <time.h>

#include "ane_accel.h"
#include "ane.h"
#include "ane_bind.h"
#include "ane.c"

static uint64_t ns_now(void)
{
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}

static int cmp_u64(const void *a, const void *b)
{
	uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b;
	return (x > y) - (x < y);
}

static void stats(const char *label, uint64_t *v, int n)
{
	uint64_t sum = 0;
	qsort(v, n, sizeof(uint64_t), cmp_u64);
	for (int i = 0; i < n; i++)
		sum += v[i];
	printf("%s n=%d min=%.3f p10=%.3f med=%.3f p90=%.3f max=%.3f mean=%.3f (us)\n",
	       label, n, v[0] / 1e3, v[n / 10] / 1e3, v[n / 2] / 1e3,
	       v[(n * 9) / 10] / 1e3, v[n - 1] / 1e3,
	       (double)sum / n / 1e3);
}

static void fill_inputs(struct ane_nn *nn, int rep)
{
	for (uint32_t i = 0; i < ane_src_count(nn); i++) {
		uint64_t bytes = ane_src_size(nn, i);
		uint16_t *buf = malloc(bytes);
		uint64_t n = bytes / 2;
		for (uint64_t k = 0; k < n; k++)
			buf[k] = (uint16_t)(0x3800 + ((k + (uint64_t)rep * 7) % 13));
		__ane_send(nn, buf, i);
		free(buf);
	}
}

static int do_submit(struct ane_nn *nn, uint32_t td_count, uint32_t btsp_handle)
{
	const struct anec *anec = to_anec(nn);
	struct drm_ane_submit args;

	memset(&args, 0, sizeof(args));
	args.tsk_size = anec->tsk_size;
	args.td_count = td_count;
	args.td_size = anec->td_size;
	for (int bdx = 0; bdx < ANE_TILE_COUNT; bdx++)
		if (anec->tiles[bdx])
			args.handles[bdx] = nn->chans[bdx].handle;
	if (btsp_handle)
		args.btsp_handle = btsp_handle;
	else
		args.btsp_handle = nn->btsp_chan.handle;
	return ioctl(nn->fd, DRM_IOCTL_ANE_SUBMIT, &args);
}

static int cmd_info(const char *path)
{
	struct ane_nn *nn = __ane_init(path, 0);
	if (!nn)
		return 1;
	const struct anec *a = to_anec(nn);
	printf("anec size=%llu td_size=%u td_count=%u tsk_size=%llu krn_size=%llu src=%u dst=%u\n",
	       (unsigned long long)a->size, a->td_size, a->td_count,
	       (unsigned long long)a->tsk_size, (unsigned long long)a->krn_size,
	       a->src_count, a->dst_count);
	for (int b = 0; b < ANE_TILE_COUNT; b++)
		if (a->tiles[b])
			printf("  chan[%d] tiles=%llu bytes=%llu nchw=%llu,%llu,%llu,%llu,%llu,%llu\n",
			       b, (unsigned long long)a->tiles[b],
			       (unsigned long long)(a->tiles[b] << 14),
			       (unsigned long long)a->nchw[b][0],
			       (unsigned long long)a->nchw[b][1],
			       (unsigned long long)a->nchw[b][2],
			       (unsigned long long)a->nchw[b][3],
			       (unsigned long long)a->nchw[b][4],
			       (unsigned long long)a->nchw[b][5]);
	for (uint32_t i = 0; i < a->src_count; i++)
		printf("  src[%u] chan=%u tile_bytes=%llu\n", i, src_bdx(nn, i),
		       (unsigned long long)ane_src_size(nn, i));
	for (uint32_t i = 0; i < a->dst_count; i++)
		printf("  dst[%u] chan=%u tile_bytes=%llu\n", i, dst_bdx(nn, i),
		       (unsigned long long)ane_dst_size(nn, i));
	__ane_free(nn);
	return 0;
}

static int cmd_floor(const char *path, int reps)
{
	struct ane_nn *nn = __ane_init(path, 0);
	if (!nn)
		return 1;
	fill_inputs(nn, 0);
	for (int i = 0; i < 20; i++)
		if (do_submit(nn, to_anec(nn)->td_count, 0) < 0) {
			printf("warm exec failed\n");
			return 1;
		}
	uint64_t *t = malloc(sizeof(uint64_t) * reps);
	for (int i = 0; i < reps; i++) {
		uint64_t a = ns_now();
		if (do_submit(nn, to_anec(nn)->td_count, 0) < 0) {
			printf("exec %d failed\n", i);
			return 1;
		}
		t[i] = ns_now() - a;
	}
	stats("floor_submit_us", t, reps);
	__ane_free(nn);
	free(t);
	return 0;
}

static int cmd_decomp(const char *path, int reps)
{
	struct ane_nn *nn = __ane_init(path, 0);
	if (!nn)
		return 1;
	const struct anec *a = to_anec(nn);
	uint32_t ns = a->src_count, nd = a->dst_count;
	uint64_t *ts = malloc(sizeof(uint64_t) * reps * ns);
	uint64_t *tx = malloc(sizeof(uint64_t) * reps);
	uint64_t *tr = malloc(sizeof(uint64_t) * reps * nd);
	int si = 0, ri = 0;
	for (int r = 0; r < reps; r++) {
		for (uint32_t i = 0; i < ns; i++) {
			uint64_t bytes = ane_src_size(nn, i);
			uint16_t *buf = malloc(bytes);
			uint64_t n = bytes / 2;
			for (uint64_t k = 0; k < n; k++)
				buf[k] = (uint16_t)(0x3800 + ((k + (uint64_t)r * 7) % 13));
			uint64_t t0 = ns_now();
			__ane_send(nn, buf, i);
			ts[si++] = ns_now() - t0;
			free(buf);
		}
		uint64_t t0 = ns_now();
		if (do_submit(nn, a->td_count, 0) < 0) {
			printf("exec %d failed\n", r);
			return 1;
		}
		tx[r] = ns_now() - t0;
		for (uint32_t i = 0; i < nd; i++) {
			uint64_t bytes = ane_dst_size(nn, i);
			uint16_t *buf = malloc(bytes);
			uint64_t t1 = ns_now();
			__ane_read(nn, buf, i);
			tr[ri++] = ns_now() - t1;
			uint64_t bad = 0;
			for (uint64_t k = 0; k < bytes / 2; k++)
				if (((buf[k] >> 10) & 0x1f) == 0x1f)
					bad++;
			if (bad)
				printf("rep %d dst[%u] nonfinite=%llu\n", r, i,
				       (unsigned long long)bad);
			free(buf);
		}
	}
	char lbl[64];
	snprintf(lbl, sizeof(lbl), "send_us(n=%u/submit)", ns);
	stats(lbl, ts, si);
	stats("exec_us", tx, reps);
	snprintf(lbl, sizeof(lbl), "read_us(n=%u/submit)", nd);
	stats(lbl, tr, ri);
	__ane_free(nn);
	free(ts); free(tx); free(tr);
	return 0;
}

static int cmd_chain(const char *path, int n_td, int reps)
{
	struct ane_nn *nn = __ane_init(path, 0);
	if (!nn)
		return 1;
	const struct anec *a = to_anec(nn);

	/* dedicated btsp BO holding n_td copies of the task stream at
	 * stride td_size, each copy nid-stamped */
	struct ane_bo big;
	memset(&big, 0, sizeof(big));
	big.size = tile_align((uint64_t)a->td_size * n_td);
	if (bo_init(nn, &big) < 0 || bo_mmap(nn, &big) < 0) {
		printf("big bo failed\n");
		return 1;
	}
	for (int k = 0; k < n_td; k++) {
		memcpy((uint8_t *)big.map + (uint64_t)k * a->td_size,
		       nn->btsp_chan.map, a->td_size);
		set_nid((uint8_t *)big.map + (uint64_t)k * a->td_size, ANE_FIFO_NID);
	}

	fill_inputs(nn, 0);
	for (int i = 0; i < 5; i++)
		if (do_submit(nn, n_td, big.handle) < 0) {
			printf("chain warm exec failed (n=%d)\n", n_td);
			return 1;
		}
	uint64_t *t = malloc(sizeof(uint64_t) * reps);
	for (int i = 0; i < reps; i++) {
		uint64_t t0 = ns_now();
		if (do_submit(nn, n_td, big.handle) < 0) {
			printf("chain exec %d failed (n=%d)\n", i, n_td);
			return 1;
		}
		t[i] = ns_now() - t0;
	}
	char lbl[64];
	snprintf(lbl, sizeof(lbl), "chain_n%d_us", n_td);
	stats(lbl, t, reps);
	bo_munmap(nn, &big);
	bo_free(nn, &big);
	__ane_free(nn);
	free(t);
	return 0;
}

static int cmd_verify(const char *path, const char *in_file,
		      const char *expect_file)
{
	struct ane_nn *nn = __ane_init(path, 0);
	if (!nn)
		return 1;
	const struct anec *a = to_anec(nn);
	uint64_t in_bytes = ane_src_size(nn, 0);
	uint16_t *in = malloc(in_bytes);
	if (in_file) {
		FILE *f = fopen(in_file, "rb");
		if (!f || fread(in, 1, in_bytes, f) != in_bytes) {
			printf("input read failed\n");
			return 1;
		}
		fclose(f);
	} else {
		for (uint64_t k = 0; k < in_bytes / 2; k++)
			in[k] = 0x3800; /* 0.25 fp16 */
	}
	__ane_send(nn, in, 0);
	if (do_submit(nn, a->td_count, 0) < 0) {
		printf("exec failed\n");
		return 1;
	}
	uint64_t out_bytes = ane_dst_size(nn, 0);
	uint16_t *out = malloc(out_bytes);
	__ane_read(nn, out, 0);
	uint64_t hash = 1469598103934665603ull;
	for (uint64_t k = 0; k < out_bytes / 2; k++) {
		hash ^= out[k];
		hash *= 1099511628211ull;
	}
	printf("verify out_bytes=%llu fnv1a=%016llx\n",
	       (unsigned long long)out_bytes, (unsigned long long)hash);
	if (expect_file) {
		FILE *f = fopen(expect_file, "rb");
		if (!f) {
			printf("no expect file\n");
			return 1;
		}
		uint16_t *exp = malloc(out_bytes);
		size_t got = fread(exp, 1, out_bytes, f);
		fclose(f);
		if (got != out_bytes) {
			printf("expect size %zu != %llu\n", got,
			       (unsigned long long)out_bytes);
			return 1;
		}
		int mism = 0;
		for (uint64_t k = 0; k < out_bytes / 2; k++) {
			uint16_t x = out[k], y = exp[k];
			if (x == y)
				continue;
			if ((x & 0x7fff) == 0 && (y & 0x7fff) == 0)
				continue;
			mism++;
			if (mism <= 4)
				printf("lane %llu got %04x want %04x\n",
				       (unsigned long long)k, x, y);
		}
		printf("verify %s (%d mismatched lanes of %llu)\n",
		       mism ? "MISMATCH" : "EXACT", mism,
		       (unsigned long long)(out_bytes / 2));
	}
	return 0;
}

static uint64_t fnv1a(const uint16_t *buf, uint64_t words)
{
	uint64_t hash = 1469598103934665603ull;
	for (uint64_t k = 0; k < words; k++) {
		hash ^= buf[k];
		hash *= 1099511628211ull;
	}
	return hash;
}

static int cmd_verify2(const char *path, const char *in_file, int reps)
{
	struct ane_nn *nn = __ane_init(path, 0);
	if (!nn)
		return 1;
	const struct anec *a = to_anec(nn);
	uint32_t ns = a->src_count, nd = a->dst_count;
	if (reps < 2)
		reps = 8;
	/* "-" means no input file: use the deterministic fill everywhere */
	if (in_file && !strcmp(in_file, "-"))
		in_file = NULL;

	/*
	 * Two alternating input patterns: rep N fills pattern N&1. Stale
	 * CPU->device lines surface as the device computing the previous
	 * pattern's output; stale device->CPU lines surface as the host
	 * reading the previous rep's bytes. Both break the per-pattern
	 * reference hash on their next occurrence.
	 */
	uint64_t *ref = calloc(nd * 2, sizeof(uint64_t));
	int seen[2] = { 0, 0 };
	int mism = 0;
	for (int r = 0; r < reps; r++) {
		int pat = r & 1;
		for (uint32_t i = 0; i < ns; i++) {
			uint64_t bytes = ane_src_size(nn, i);
			uint16_t *buf = malloc(bytes);
			if (i == 0 && in_file && pat == 0) {
				FILE *f = fopen(in_file, "rb");
				if (!f || fread(buf, 1, bytes, f) != bytes) {
					printf("input read failed\n");
					free(buf);
					return 1;
				}
				fclose(f);
			} else {
				for (uint64_t k = 0; k < bytes / 2; k++)
					buf[k] = (uint16_t)(0x3800 +
						((k + i + (uint64_t)pat * 519) % 13));
			}
			__ane_send(nn, buf, i);
			free(buf);
		}
		if (do_submit(nn, a->td_count, 0) < 0) {
			printf("exec %d failed\n", r);
			return 1;
		}
		for (uint32_t i = 0; i < nd; i++) {
			uint64_t bytes = ane_dst_size(nn, i);
			uint16_t *buf = malloc(bytes);
			__ane_read(nn, buf, i);
			uint64_t h = fnv1a(buf, bytes / 2);
			if (!seen[pat]) {
				ref[pat * nd + i] = h;
				printf("dst[%u] pat%d bytes=%llu fnv1a=%016llx\n",
				       i, pat, (unsigned long long)bytes,
				       (unsigned long long)h);
			} else if (h != ref[pat * nd + i]) {
				mism++;
				printf("rep %d dst[%u] pat%d DIVERGED fnv1a=%016llx want %016llx\n",
				       r, i, pat, (unsigned long long)h,
				       (unsigned long long)ref[pat * nd + i]);
			}
			free(buf);
		}
		seen[pat] = 1;
	}
	printf("verify2 reps=%d dsts=%u %s (diverged=%d)\n", reps, nd,
	       mism ? "DIVERGED" : "STABLE", mism);
	free(ref);
	__ane_free(nn);
	return mism ? 1 : 0;
}

int main(int argc, char **argv)
{
	if (argc < 3) {
		fprintf(stderr,
			"usage: %s info <anec>\n"
			"       %s floor <anec> <reps>\n"
			"       %s decomp <anec> <reps>\n"
			"       %s chain <anec> <n_td> <reps>\n"
			"       %s verify <anec> [in.bin] [expect.bin]\n"
			"       %s verify2 <anec> [in.bin] [reps]\n",
			argv[0], argv[0], argv[0], argv[0], argv[0], argv[0]);
		return 2;
	}
	if (!strcmp(argv[1], "info"))
		return cmd_info(argv[2]);
	if (!strcmp(argv[1], "floor"))
		return cmd_floor(argv[2], atoi(argv[3]));
	if (!strcmp(argv[1], "decomp"))
		return cmd_decomp(argv[2], atoi(argv[3]));
	if (!strcmp(argv[1], "chain"))
		return cmd_chain(argv[2], atoi(argv[3]), atoi(argv[4]));
	if (!strcmp(argv[1], "verify"))
		return cmd_verify(argv[2], argc > 3 ? argv[3] : NULL,
				  argc > 4 ? argv[4] : NULL);
	if (!strcmp(argv[1], "verify2"))
		return cmd_verify2(argv[2], argc > 3 ? argv[3] : NULL,
				   argc > 4 ? atoi(argv[4]) : 8);
	return 2;
}
