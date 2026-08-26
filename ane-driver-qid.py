#!/usr/bin/env python3
"""Patch the KMD to select a task queue through submit.pad.

The upstream driver hardcodes qid 4. The uapi has an unused pad field, so use
0x80|qid as an explicit selector and keep pad=0 backward compatible.
"""
import sys

OLD = """\tif (args->pad || !args->tsk_size || !args->td_count || !args->td_size ||
\t    !args->handles[CMD_BUF_BDX] || args->handles[KRN_BUF_BDX] ||
\t    !args->btsp_handle) {
\t\treturn -EINVAL;
\t}

\treq.qid = 4;"""
NEW = """\tif (!args->tsk_size || !args->td_count || !args->td_size ||
\t    !args->handles[CMD_BUF_BDX] || args->handles[KRN_BUF_BDX] ||
\t    !args->btsp_handle) {
\t\treturn -EINVAL;
\t}

\t/* pad==0 keeps qid 4; 0x80|qid selects one of eight queues. */
\tif (args->pad & 0x80)
\t\treq.qid = args->pad & 0x7;
\telse if (args->pad)
\t\treturn -EINVAL;
\telse
\t\treq.qid = 4;"""


def main():
    path = sys.argv[1]
    with open(path) as fh:
        src = fh.read()
    if "pad==0 keeps qid 4" in src:
        print("already patched")
        return
    if OLD not in src:
        raise SystemExit("submit anchor not found")
    with open(path, "w") as fh:
        fh.write(src.replace(OLD, NEW, 1))
    print("patched qid selector")


if __name__ == "__main__":
    main()
