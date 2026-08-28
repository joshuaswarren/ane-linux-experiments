# 791 milliseconds: the Neural Engine finally beats the CPU on Linux

791 ms. That is what the Apple Neural Engine charges for the tied output head of Qwen3.8-2B: a 248320x2048 fp16 GEMM, one matrix multiply per generated token, about 508 million multiply-adds. The CPU on the same host needs 1975 ms for the same work. 2.50x, measured, on Linux, with no macOS in the loop.

For years this comparison ran the other way. My last receipt for this exact head said 0.33x. Running the ANE from Linux has a graveyard of abandoned forks behind it: eiln/ane, apple-ane, each one getting partway in and stopping. This post is the story of the last two days on jwm1-linux, a 16 GB M1 MacBook Pro running Asahi Linux under Omarchy. The repo is public at github.com/joshuaswarren/ane-linux-experiments, and every number here has a line in receipts/ane-static-graph-loop.log.

## The 0.33x was never the device

The old loss looked like a hardware verdict. The engine needed 3.86 s for the full head while numpy needed 1.27 s. But when I profiled the per-tile path, the story changed. The runtime allocated four buffer objects for every 512x512 tile call and tore them down after. That churn cost about 2 ms per call, and the actual matrix math was buried inside it.

So the fix was boring. Keep the buffer objects alive. On a static head the weights never change, so the submit path rewrites nothing at all. New floor: 0.187 ms per tile submit. With a weight-blob rewrite between calls it is 0.304 ms. The 2 ms was allocation, not silicon.

Same device, same head, one less stupid thing per call: 0.33x became 2.50x. A 1024x512 smoke test ran 3.20x, overhead-dominated at that size. And in the interest of real numbers: an older receipt logged the CPU reference at 1.27 s for this shape, and last night's run measured 1975 ms. Take the faster CPU number and the result still holds. 791 ms beats 1270 ms.

## Persistent tiles

The head tiles as 485 by 8: 3,880 programs of 512x256. Setup programs them once, 6.3 s total at 1.64 ms per tile, and leaves the weights resident in device memory. A token then costs one submit per tile, with the CPU accumulating the 8 partials per row tile in fp32.

Quality held up under the usual abuse:

- Identity matrix bound into a tile: passthrough exact.
- Random tiles against numpy: max error 0.0003 to 0.0004.
- Full head against an fp32 reference: max error 0.0010, argmax match, top-10 match 10 for 10.

There is a ceiling worth naming. The ANE DART VM on this driver is 3.5 GiB, and resident tiles for every layer would need about 4.5 GiB of buffer objects. So the head is resident and the layers are not. Dispatch-bound is the honest label for the 791 ms: 3,880 submits at the 0.187 ms floor is 0.73 s of it.

## The fresh compiler format

Apple's ANECompilerService on macOS 26 emits a new format. It is a Mach-O container with the task descriptor in __TEXT,__text at file offset 0x4028 and the kernel in __TEXT,__const at 0x4280. The old anecc parser rejects it. Every attempt to run a fresh-compiled descriptor raw hit the same wall: the driver accepted the submit, then timed out with -110, and the output stayed at the 0x7c00 inf sentinel. Control graphs from the old compiler kept running green on the same driver seconds later, so the wall was in the format, not the host.

The diff between an old descriptor and a fresh one is 20 words out of 157, and most of it looked like config noise. The word that mattered sat in the bank fields. The fresh compiler assigns RBase0=4 and WBase=5. The old libane convention uses slot 4 as the destination and slot 5 as the source. Reversed. The fresh format reads its input window through bank 4 and writes its output window through bank 5.

I wrote a converter, tools/hwxv2-to-anec.py, that parses the Mach-O sections and emits an .anec payload, then submitted a compiler-generated 4-pixel conv with the handles swapped to match. It ran. Input row [2.041, -2.5566, 0.4182] came back as [3.041, -1.5566, 1.418, 0.4321]. Input plus the 1.0 bias, deterministic, every boot. As far as I can tell this is the first execution of macOS 26 compiler output on Asahi Linux.

## The kernel encoding, decoded by markers

The conv result had a smell. A [0, 1.875, 0] kernel should not behave like a pass-through plus bias. So I compiled the same net with single marker values and dumped the compiled kernel region after each compile.

The layout is per-channel groups of 0x40 bytes, each group holding an fp16 bias followed by packed values. The packed values follow a quantized encoding. One marker value per compile mapped it: 1.0 stores as 0x2000, 2.0 as 0x4000, 1.875 as 0x3c00. That is Q13 fixed point, 8192 counts per unit, linear out to |k| = 4.0 and saturating at 0x7c00. Multi-channel rows bring in a dynamic per-channel scale fit, value-dependent, and that part is still not fully mapped.

Here is the punchline. The device multiplies the input by the fp16 interpretation of the stored bits. Q13(1.875) is 0x3c00. Read those same bits as fp16 and you get 1.0. The kernel executed as identity plus bias because the two number formats share bits and not values.

## What does not work

Most of the session lived in the negative space, so here it is.

Hot-swapping fresh kernels is dead. Patching the compiled tap value in the constant bank, plain fp16 written over the Q13 bits at the exact group offset, hangs the task. The microcode is compiled for the quantized encoding present at compile time. Weights have to be right when the compiler runs. Not swappable, period.

Hand-rolled multi-TD descriptors are closed. The chain protocol itself decoded cleanly from the compiler's own register map, aneregs.json in the tinygrad-ane tree: TID in W0 bits 0-15 is the chain index, EON and LNID in W0 bits 25 and 24 mark the last TD, and NextSize reads 156 on non-last TDs. With those fields set, a 2-TD GEMM chain went from hard hang to clean completion for the first time, tools/fresh-td-bisect.py driving. Tile 0 came back exact. Tile 2's output window stayed unwritten, and the bisect that followed ended the track: three boots, one first submit each. TID=1 alone, timeout. KBase0=1 alone, timeout. Nonzero buffer bases alone, timeout. Any single-field deviation from the exact proven TD word-set hangs the task, and a hang poisons the device until reboot. Hand-assembled TDs are not a construction path on this stack. Compiler-generated descriptors are the only road.

In-process oMLX compiles segfault. Calling the compile entry point from Python, even in the venv with the working extension, exits 139 about 90 to 330 seconds into the ANECompilerService invocation. The tuner's successful compiles ran inside the oMLX server process, which sets up the private-ANE entitlements at startup. Server-mediated is the documented route.

## The recovery ladder

Each hang costs about 3 minutes, so recovery is a solved procedure, learned the expensive way. The ladder, run after any wedge:

```
sudo ANE_KO=/home/joshuawarren/ane-boot/ane-qid.ko bash ~/ane-boot/jwm1-ane-bringup.sh
```

Plain insmod without the ladder resets the whole SoC. That lesson cost me two hard reboots. If BO_INIT starts failing with EEXIST at iova 0x4000, the machine needs a reboot first and the ladder second. The discipline that finally stuck: run the ladder immediately before each device session, run a control submit first, re-run the control after every experiment config, and throw out results if the control breaks. A degraded device will happily produce confident garbage.

## The rest of the model

The crossover is one head, so here is what the whole model does. Qwen3.8-2B runs on this stack with every linear projection and the tied head on the ANE and the non-linear ops on CPU. Generated tokens match the CPU backend: [11, 488] with next token 628, the same ids the CPU backend emits, and the logits chain matches step for step. Against an fp32 cross-check the logits land within 0.0023. The full one-token path is still not faster than CPU in wall time. Quality parity is done. The token-rate win needs the same churn cleanup the head got.

## Where this goes

Two things are open, and one of them is inviting.

The first is multi-TD chaining, the dispatch multiplier. 3,880 submits at a 0.187 ms floor put a 0.73 s tax under every token. Chaining tiles into one submit is a theoretical 4 to 8x. The chain protocol fields are decoded and the hardware accepts the walk. The TD field interlock is the locked door.

The second is Apple's quantizer packing. Multi-channel rows interleave values at differing scales with a dynamic per-channel fit, and that code lives inside ANECompilerService, which is opaque. Single-tap-per-channel kernels work through the fresh path today. The full multi-channel decode is one determined bit-level session away, or a patient run of single-value compiles at about two seconds each.

The 791 ms stands. Compiler-generated graphs now run on Linux. The device that spent years as a question mark runs a real language model's head faster than the CPU that boots it.

If you have ANECompilerService under a disassembler, or old HWX files and curiosity, the packing decode is a good group project. My receipts are public.