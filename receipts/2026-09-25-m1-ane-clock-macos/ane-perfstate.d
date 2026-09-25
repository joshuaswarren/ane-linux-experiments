#!/bin/sh
# dtrace/fbt capture for the macOS ANE perf-state write path (jwm1 macOS window).
# Logs: _handlePerfStateRequest(domain, state) entries for domain 8 (ANE),
# and the apply routine's byte write. Run during an encoder run.
# Requires SIP with dtrace allowed (csrutil status check first).
# Usage: sudo dtrace -s ane-perfstate.d -o /tmp/ane-perfstate.out &
#        <run encoder bench>; sudo pkill -INT dtrace
#pragma D option quiet
#pragma D option bufsize=64m

/* ApplePMGR::_handlePerfStateRequest(uint client?, uchar domain, uint state)
 * Entry prologue: x21=x3, x22=x2, x20=x1 at +0x44..0x4c.
 * Signature from call sites: handle(obj, x1?, domain=x2, state=x3).
 * fbt arg0..arg3 map to x0..x3 at function entry.
 */
fbt::0xfffffe000986fb08:entry
{
    printf("HANDLE entry t=%d domain=%d state=%d x1=%d\n",
        timestamp / 1000, arg2, arg3, arg1);
}

/* apply routine 0x...86e7bc: same arg shape (x1, domain=x2, state=x3).
 * Log the composed byte inputs before the accessor write.
 */
fbt::0xfffffe000986e7bc:entry
{
    printf("APPLY entry t=%d domain=%d state=%d x1=%d\n",
        timestamp / 1000, arg2, arg3, arg1);
}

/* Return values: did the request stick? */
fbt::0xfffffe000986fb08:return
{
    printf("HANDLE return t=%d\n", timestamp / 1000);
}

fbt::0xfffffe000986e7bc:return
{
    printf("APPLY return t=%d\n", timestamp / 1000);
}

/* Guard: only trace while an encoder run is live is manual (start/stop dtrace
 * around the bench). Post-hoc filter: domain == 8 lines.
 */
dtrace:::BEGIN
{
    printf("ane-perfstate trace start. Filter: domain == 8 (ANE).\n");
}
