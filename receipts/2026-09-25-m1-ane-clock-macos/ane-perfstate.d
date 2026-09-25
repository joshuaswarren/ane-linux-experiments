#!/usr/sbin/dtrace -s
/*
 * ANE perf-state write capture for a macOS window (T6001 jw16 or T8103 jwm1).
 * Logs what macOS itself writes for the ANE perf domain during an encoder run.
 * No MMIO from this script: it only observes.
 *
 * Prerequisites (read-only checks first):
 *   csrutil status            # fbt needs the dtrace restriction off
 *   sw_vers
 *   sudo dtrace -l -n 'fbt:com.apple.driver.ApplePMGR:*PerfState*:entry' | head -40
 * If the listing is empty, STOP: probe names differ on that build.
 *
 * Usage:
 *   sudo dtrace -s ane-perfstate.d -o /tmp/ane-perfstate.out &
 *   <run encoder_bench ane-arm during the capture>
 *   sudo pkill -INT dtrace
 * Post-hoc filter: domain == 8 (ANE) lines.
 *
 * Provenance (mac13g kernelcache, T8103, sha256 861adca1...):
 * - ApplePMGR::_handlePerfStateRequest(obj, x1, domain=x2, state=x3)
 *   accepts domains 8 (ANE) and 14 only; its prologue copies
 *   x3->x21, x2->x22, x1->x20, so fbt arg2=domain, arg3=state.
 * - ApplePMGR::_setPerfState applies the request; the ANE write is an
 *   8-bit state composed as (old & ~0xf) | (new & 0xf), pushed through the
 *   device register accessor: ApplePMGR::readReg32(map, reg) for the old
 *   byte and AppleT810xPMGR::writeReg32(map, reg, value, die) for the new
 *   one. Probing the accessor entry logs the resolved (map, reg, value).
 * Symbol names are stable across the 13.x/25.x kext builds; the T6001
 * kernelcache check (25G83) confirms them via the dtrace -l listing above.
 */
#pragma D option quiet
#pragma D option bufsize=64m
#pragma D option switchrate=10hz

dtrace:::BEGIN
{
    printf("ane-perfstate trace start. Filter: domain == 8 (ANE).\n");
}

/* Gate: 1 while inside a domain-8 _handlePerfStateRequest, else 0.
 * Narrows the accessor probes to the ANE request only.
 */
ApplePMGR::_handlePerfStateRequest:entry
/arg2 == 8/
{
    self->ane = 1;
    printf("HANDLE entry t=%d domain=%d state=%d x1=%d\n",
        timestamp / 1000, arg2, arg3, arg1);
}

ApplePMGR::_handlePerfStateRequest:return
/self->ane/
{
    printf("HANDLE return t=%d\n", timestamp / 1000);
    self->ane = 0;
}

/* The composed byte write. writeReg32(map=arg1, reg=arg2, value=arg3, die=arg4)
 * on the T810x subclass; the base-class name also matches via the module
 * wildcard below if the build inlines the subclass override.
 */
ApplePMGR::writeReg32:entry
/self->ane/
{
    printf("WRITE t=%d map=%d reg=%d value=0x%x die=%d\n",
        timestamp / 1000, arg1, arg2, arg3, arg4);
}

/* The readback of the old byte (same arg shape minus value). */
ApplePMGR::readReg32:entry
/self->ane/
{
    printf("READ t=%d map=%d reg=%d\n",
        timestamp / 1000, arg1, arg2);
}

ApplePMGR::readReg32:return
/self->ane/
{
    printf("READ return t=%d value=0x%x\n", timestamp / 1000, arg0);
}

/* The top-level nub entry: which enum the caller used (2 -> domain 8). */
ApplePMGRNub::requestPerfState:entry
{
    printf("NUB t=%d enum=%d\n", timestamp / 1000, arg1);
}

/* CLPC computes the ANE state from submitted work; log its begin/submit. */
clpc::aneWorkBegin:entry,
clpc::aneWorkSubmit:entry
{
    printf("CLPC %s t=%d\n", probefunc, timestamp / 1000);
}
