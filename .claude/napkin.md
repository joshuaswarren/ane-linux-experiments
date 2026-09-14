# Napkin

## Corrections

| Date | Source | What Went Wrong | What To Do Instead |
|------|--------|-----------------|-------------------|
| 2026-09-13 | user | Stopped after ANE-on-Max findings and parked ANE/CoreML/parity | Keep all three plans plus jw16 ANE bind running. Findings are not a stop. |
| 2026-09-13 | self | Left GATES G1 on power-reset after cycle 11 bound `/dev/accel/accel0` | Update the gate when the device node exists. Bind is not execute: T6001 still TM `-110` on the T8103-exact 64-el program. |
| 2026-09-14 | self | T6001 SET0 read ACTUAL=0 while accel0 still live | Idle runtime suspend gates SET. open(accel0) restores 0xf via genpd. Not a lost bind. Never write 0xf. |
| 2026-09-14 | environment | Several `mlx-openai-deep` leaves in one batch resolved to `anthropic/claude-opus-5`, not the OpenAI route; each disclosed it in its receipt | Treat the label as a request, not proof. Require `resolved_model` with a `fallback` flag in every receipt and keep the artifacts when the work is independently verifiable. |
| 2026-09-13 | self | Conv-as-matmul compiled (375,1024,2048) as 15000 programs / 1.6GB | rc=0 is not an envelope. Do not land that rewrite. |
| 2026-09-13 | review | Accepted eager constant snapshots after two hashes of mutable source paths; a flip/read/restore sequence returned wrong cached bits while both hashes passed | Hash the exact immutable byte buffer used for parsing/decoding; before/after path hashes do not authenticate consumed bytes. |
| 2026-09-13 | self | Used established HTTP socket counts as an empty-queue gate, delaying real readiness probes | Keepalive sockets are not active requests; use a bounded completion and correlated engine lifecycle evidence. A client timeout does not prove server cancellation. |
| 2026-09-13 | self | Left trailing commas on final JSON fields and tried an inverted edit range for insertion | Preserve whole object boundaries, use valid replacement ranges, and parse JSON before commit. Failed validation blocks publication. |
| 2026-09-13 | self | Assumed test bootstrap _TOOLS was a Path and guessed compiler target directories | Inspect exported types and the repo root first; _TOOLS is a string and H13 lives under plugins/H13. A wrong test setup is not a regression reproduction. |
| 2026-09-13 | self | Treated grep skip as an exclusion list and assumed a pinned receipt existed in the current checkout | skip is pagination, not exclusions; resolve the actual file or read its pinned source URL instead of guessing local paths. |
| 2026-09-13 | review | A typed ADT export labeled node.reg as translated addresses; the low addresses exposed the mistake | Preserve raw cells separately and invoke node.get_reg() for bus-range translation; typed parsing alone does not translate addresses or establish live Linux bindings. |
| 2026-09-12 | self | Merging an authorized_keys line on CT350 filtered with `split()[1]`, which is the key TYPE, so the existing nexus key line matched and was silently deleted | Match auth-key lines on the base64 material field (`split()[2]`) and print the full file before and after any merge; a one-index-off filter silently deletes live credentials. |
| 2026-09-12 | self | Put `rm /tmp/<staged>` inside `pct exec ... sh -c` cleanup strings twice, deleting files just pushed INTO the CT | `pct exec` strings run inside the container; host-side /tmp cleanup runs outside it, and staged remote files get re-verified after any cleanup step. |
| 2026-09-12 | self | Killed a long ssh at the default 300s tool timeout while the remote forced command lived on holding /run/lock, so the retry failed ERROR(8) lock busy | Run long exclusive remote operations with an explicit raised timeout or async, and confirm the remote process is gone before retrying. |
| 2026-09-12 | user | Laptop bring-up displaced active ANE, CoreML, and performance-parity workers | Keep all three full plans running concurrently. A leaf result or release gate is not permission to park its whole lane; resume the next unblocked step and keep blocked decisions visible. |
| 2026-09-12 | user | Root did too much implementation and generic task workers inherited GPT-6 | Delegate independent implementation to explicitly named OMP agents. Verified mlx-openai-deep resolves gpt-5.6-sol and mlx-openai-operator resolves gpt-5.6-terra; inspect child model_change records and fallback flags, not just labels. Keep root on integration and decisions. |
| 2026-09-12 | self | Classified a retrying smoke as failed from truncated output; its final attempt passed | Read the complete final result and exit status before reporting a retry job verdict. Individual failed attempts are not the aggregate outcome. |
| 2026-09-12 | environment | Direct todo after resume again shows 8 completed despite Eval reconciliation to 71; a single block call loses prior states | Published mlx-omarchy receipts/2026-09-12-acceptance-state.json is authoritative. Do not confuse tool state regression with undone work or repeat restoration loops; reported through xd://report_issue |
| 2026-09-12 | self | Used unsupported edit syntax, then inserted a receipt paragraph inside an unfinished sentence | Use anchored PUT N..M with + payload rows; re-read after a failed edit and replace complete paragraphs or constructs. |
| 2026-09-12 | self | Pushed local `main` while working on `main-land2`; stale local ref was correctly rejected | After checking remote ancestry, push `HEAD:main` from the integration worktree; never force-push |
| 2026-08-29 | self | Used `Path.read_bytes()[:4096]` on multi-gigabyte ANEC files while extracting headers | Open the file and read only 4,096 bytes. Never materialize a large artifact to take a prefix |
| 2026-08-28 | self | Assumed fresh-compiled TD failure was a converter bug; burned cycles on tiles/nchw guessing before isolating with a same-plist two-compiler TD diff | When a graph times out, first run the CONTROL: same plist compiled by the known-good compiler. Diff the TDs. Config-shaped words vs format words |
| 2026-08-28 | self | nchw plane-stride fields feed host `ane_tile` memcpy size: `N*C*pS` from a 0x4000 BO segfaulted with pS=0x1000 for 2048 fp16 | libane nchw serves TWO masters: host tiling (N*C*pS <= map) and device PS0-7 regs. For big inputs give tiles[bdx] = ceil(N*C*pS/0x4000) instead of shrinking pS |
| 2026-08-28 | self | -1 vs -110 from run-anec looked like distinct kernel rejections; actually -110 (KMD execute timeout) printed as -1 by the python wrapper path | Read `sudo dmesg` for the KMD receipt (`tm execution failed w/ -110`) before interpreting exec_result codes |
| 2026-08-28 | self | Put the public article in `ane-linux-experiments` instead of `~/src/joshuawarrendotcom` | Before committing public articles, check the destination repo and its `src/content/blog/` convention |
| 2026-08-29 | self | Used JSON `null` inside a Python `eval` cell, which raised `NameError` before parallel research ran | Use Python `None` in `eval(language="py")`; JSON literals apply only inside tool argument objects |
| 2026-08-29 | self | Passed `Metal/MLX` in a general last30days topic; the engine parsed slash-separated terms as comparison mode | Rewrite grouped slash terms with commas before invoking last30days unless the user asked for a comparison |
| 2026-08-29 | environment | `skill://ce-plan` requires `scripts/context.mjs`, but the installed skill directory lacks that file | Run the required fence once, record `MODULE_NOT_FOUND`, then continue with the normal planning workflow as the skill directs |
| 2026-08-29 | user | Proposed an ANE plus MLX CPU hybrid as the fastest compatibility target | The Linux MLX plan must use Apple GPU compute for fallback tensor work; CPU may orchestrate but must not be the tensor-compute backend |
| 2026-08-29 | self | Guessed `render-markdown.md`, then tried unsupported globbing on `skill://` after the read failed | Read the internal directory first; use the returned exact filename such as `markdown-rendering.md` |
| 2026-08-29 | self | Used `glob` on an absent `.compound-engineering` directory after learning nonexistent paths fail | For optional exact paths, use a bounded `test -f` check; reserve `glob` for existing search roots |
| 2026-08-29 | self | Started `mkdir` with the new repository path as the working directory before it existed | Create a new repository root from its existing parent directory, then use the new path |
| 2026-08-29 | self | Used `PUT 1*:` on a Markdown H1 because the edit contract says headings are block openers, but this runtime rejected it | Use `write` for a deliberate whole-document rewrite when the Markdown block resolver rejects the H1 |
| 2026-08-29 | self | Replaced `main()` lines with stale pre-insertion anchors in one multi-hunk edit and broke its prologue | Re-read the full construct after any surprise and replace the whole block once; do not repair syntax damage incrementally |
| 2026-08-29 | self | Used `await completion(...)` in a Python eval even though the eval prelude marks `completion` as synchronous | Call Python `completion(...)` directly; only the JavaScript helper is async |
| 2026-08-29 | environment | `gh repo create` used GraphQL and failed after the shared user quota was exhausted | Create repositories with REST `POST /user/repos`, then add the remote and push |
| 2026-08-29 | user | Named the public MLX project after Asahi despite the owner's repeated rule against crediting Asahi | Name the repo, package, backend, CLI, build flags, and docs after Omarchy: `mlx-omarchy` |
| 2026-08-30 | self | Treated `ANECCompile=0` as proof that Espresso retained the complete graph | Inspect exported `net.plist` Outputs and Units. Require the named final output before hardware execution |
| 2026-08-30 | user | Asked before rebooting the dedicated Linux M1 | The Linux M1 is dedicated to this work. Reboot it when recovery requires it |
| 2026-08-30 | self | Left completed work on a branch instead of updating GitHub main during a long run | Push completed slices to GitHub main at least once every 12 hours |
| 2026-08-30 | self | Markdown backticks inside JavaScript template literals caused parse/interpolation errors; repeated with a doubled escape on 2026-09-12 | Use the structured Write tool for full Markdown rewrites instead of nesting Markdown inside JavaScript literals |
| 2026-09-13 | self | Approved local runner hashes after a remote preflight, but the remote staged runner and preflight were older; the promised group scanner was absent | Hash every actual remote executable and dependency immediately before exec. A successful preflight output does not prove reviewed bytes ran. Preserve mismatched-run numerics separately from failed lifecycle acceptance. |
| 2026-08-30 | self | Copied an unrelated dirty probe into a hardware bundle and mismatched its committed parser dependency | Stage validation dependencies from the intended commit, then compare local and remote hashes |
| 2026-08-30 | self | Replaced the wrong JSON line range and duplicated source hash keys | Re-read the complete JSON object and replace the whole object after any syntax error |
| 2026-08-30 | self | Squared a large fp16 inverse-root estimate before multiplying by its small source and overflowed on near-zero model state | Evaluate the Newton term as `(source * estimate) * estimate`; both intermediates stay representable |
| 2026-08-30 | self | Raised while an `np.frombuffer` view still referenced an mmap, so cleanup raised `BufferError` | Copy the result and delete the mmap view before validation can raise |
| 2026-08-30 | self | Used one SCP destination for mixed source directories and flattened staged tool paths | Copy each source directory to its matching remote directory, then remove accidental duplicates |
| 2026-09-12 | self | Retried anchored edits with invalid range syntax, then shell `--flags` were parsed as diff rows | Use `[PATH#HASH]`, `PUT N..M:`, and prefix every literal payload row with `+`; inspect edit success before launching dependent commands |
| 2026-09-12 | self | CTest/doctest reported passes while device guards returned early, including 0 fast-op assertions | Read raw skip messages and assertion counts. Local software-Vulkan checks require MLX_OMARCHY_ALLOW_NON_APPLE=1; even then their device-specific skips are not M1 qualification |

| 2026-08-30 | self | Guessed a nonexistent partial grep path and then used apply-patch syntax with the hashline edit tool | List the real tree before filtering, and use hashline PUT or CUT operations from fresh read hashes |
| 2026-08-30 | self | Passed the logarithmic recurrent decay into a graph that multiplies state by its input directly | Treat the recurrent graph gate as the final decay factor; compute softplus, scale, and exp before the graph |
| 2026-08-30 | self | Compared the watermark service's base64 `cleaned` field as plain text and got a false README mismatch | Decode the returned base64 before hashing or comparing container-clean results |
| 2026-08-30 | self | Kept the only validated recurrent ANEC under `/tmp`; reboot erased it | Persist compiled hardware artifacts outside `/tmp` and record the durable path before reboot |
| 2026-08-30 | self | The comparator read top-level generated IDs and sliced generated-only logits as if they included prefill | Follow the artifact schema: read `prompts[].runs[].generated_ids`, and distinguish generated-only from prefill-plus-generated traces |
| 2026-08-30 | self | Assumed macOS checkpoint steps combined prompt prefill from the checkpoint count alone | Read the reference `generate()` path. Lazy layer streaming disables batched prefill, so decoder checkpoint steps align directly with token positions |
| 2026-08-30 | self | Validated Linux RoPE against a reference that copied the same invalid section remap | Derive the oracle from the frozen implementation. Qwen text decode uses contiguous half-split NeoX frequencies |
| 2026-08-30 | self | Modeled native ANE RMSNorm as sqrt(mean square plus epsilon) | ANEForge's native op uses epsilon as a floor: divide by sqrt(max(mean square, epsilon)); low-energy DeltaNet outputs expose the difference |
| 2026-08-31 | self | Put escaped `find` grouping into a pi-natives command and hit a shell syntax error | Use specialized glob or simple fact commands for file inspection |
| 2026-08-31 | self | Assumed `saveModelFiles` might export compiled HWX | Inspect the saved directory contents; the physical path returned only `net.plist`, `weights.0`, and empty `data` |
## User Preferences
- Receipts first: every claim lands in `receipts/` with command output.
- Ship small milestones. Update GitHub and README after each milestone.
- README Current status leads with T8103 bound and T6001 blocked, not historic Qwen head speed.

| 2026-08-28 | self | `tile_gemm` paired the 256-in packer (+6 fp16 channel shift) with an aligned blob: every logit shifted +6 token ids | Pack geometry and blob offset are ONE contract: 256-in blob sits 12 bytes before the kernel bar; 512-in sits on it. Test logits argmax after ANY layout change |
| 2026-08-28 | self | Blob-swap cache keyed per tile (row0, col0): ENOSPC storm, 2 reboots | Shape-keyed caches for weight-swapped programs; identity-keyed only for true residency |
| 2026-08-28 | self | After an ENOSPC storm, the bring-up ladder alone leaves BO_INIT failing (EEXIST at iova 0x4000) | Reboot, THEN ladder, after any iova exhaustion |

## Patterns That Work
- Mutable raw GEMM programs can hold a KV ring in packed weight rows and columns. Update matching slots, mask unused score rows, and reserve output row 511 for completion polling.
- Compose 128-wide softmax from two 64-lane ANE halves. Reuse four BOs, clamp at -64, divide by 128, square seven times, and run twelve Newton reciprocal steps.
- A host-managed ring can schedule causal convolution without host tensor arithmetic. ANE runs four multiply and three add submissions per 64-lane chunk.
- Pack one RoPE head into 64 lanes. One direct multiply, one swapped-half multiply, and one add perform the rotation.
- Default ANE mode must require the token runtime before any model call. Explicit CPU is a separate backend, never a fallback.
- Partial projection tiles must accumulate through ANE elementwise addition. Host fp32 accumulation violates the ANE-only contract.
- macOS 26 HWX = real Mach-O: `__TEXT,__text` @ 0x4000 = TD (0x274), `__TEXT,__const` @ 0x4280 = kernel, KDMA offsets kernel-base-relative (0x280 base, step 0x4000).
- Old-format graphs (macOS-15-era anecc) still run on current Linux KMD; fresh macOS 26 TDs reach the device and hang it (-110 at `tm execution`). Patching engine-count/bit-26 words does not revive them.
- Control-first bisect: same plist through both compilers isolates format from config in one diff (20/157 words for net.plist).
- 2026-08-28: Fresh HWX fixture executes only when raw submit swaps ANEC BO
  slots (`handles[4]=input`, `handles[5]=output`); output is NCHW
  channel-major. Compare output planes by channel, and treat a single
  populated plane as partial parity, not a full multi-output result.
- 2026-08-28: A successful isolated oMLX production compile does not prove a
  raw HWX export. The private compiler can retain only transient files, and a
  `DYLD_INSERT_LIBRARIES` export hook can stall in the Apple ANE bank retry.
  Record compile success and artifact capture as separate gates.
- 2026-08-28: `_ANEVirtualClient.copyAllModelFiles:dictionary:ioSurfaceRefs:`
  is present, but `_ANEVirtualClient sharedConnection` returns nil on
  one physical M1 compiler host. `saveModelFiles` retains MIL text and weights, not raw HWX.
- 2026-08-28: A second physical M1 compiler host reproduced four production ANE
  compile callbacks, but every `saveModelFiles` directory still contained
  MIL text and weights only. The second Mac confirms the missing raw HWX is
  an export-surface limitation, not one host's compiler state.
- 2026-08-28: `_ANEVirtualClient` is unavailable on the physical ANE path,
  even when allocated directly. The discovered `copyAllModelFiles` method
  cannot export production HWX from a physical Mac.
- 2026-08-28: Core ML `coremlc` expects an MLModel protobuf, not the
  `program(1.3)` MIL text that `saveModelFiles` returns. This path did not
  bridge the physical ANE HWX export gap.
- 2026-08-28: A fresh scan of the oMLX cache directories on three physical
  M1 compiler hosts returned zero `.hwx` files after production compiles.
- 2026-08-28: The production exporter works through direct
  `ANECCompile` with `NetworkSourceFileName`/`NetworkSourcePath`; the source
  path must end in `/`, or the compiler joins `capture-0model.mil`.
- 2026-08-28: A production Qwen HWX has `3072` task descriptors,
  `0x300` descriptor spacing within each procedure, `0x3100` procedure
  spacing, and a `0xb4300000` kernel section. `tsk_size` is the
  `__TEXT,__text` section size, not one descriptor size.
- 2026-08-28: Convert multi-gigabyte HWX with mmap and chunked writes.
  `Path.read_bytes()` creates an avoidable 3.0 GiB allocation.
- 2026-08-28: NumPy views from ANE BO mmaps export pointers that prevent
  `Buffer.close()`. Delete every `np.frombuffer` view before ExitStack cleanup.
- 2026-08-28: Production task descriptors link across sparse source slots
  (`0x300`, `0x400`, `0x3100`). A packed BTSP must remap `NextPointer`;
  a selected prefix must terminate its last link at zero.
- 2026-08-28: The production header decodes `RBase0=4`, `WBase=5`,
  `KBase0=1`; raw execution uses input handle 4 and output handle 5.
- 2026-08-28: One production descriptor executes with finite output. A
  multi-descriptor submit times out with DART IOVA `0x0`, while separate
  task-0 then task-1 submits complete. The current KMD does not carry this
  production chain in one submit.
- 2026-08-28: Reboot clears `/tmp` on the Linux M1 target. Persist multi-gigabyte
  production HWX and ANEC artifacts in a persistent home directory.
- 2026-08-28: The production probe allocated a multi-gigabyte command BO but
  did not copy the ANEC content into it. Empty command memory caused zero
  output and the DART fault. Always stream the full content payload before
  submit.
- 2026-08-28: ANE output does not guarantee that element zero changes. A
  two-byte sentinel poll reported a false timeout after valid output arrived
  elsewhere. Poll the output map for any non-sentinel value and fail on no
  changed values.
- 2026-08-28: The corrected production probe executes all `3072` descriptors
  with finite, varied output. This proves graph execution, not numeric model
  parity. Keep that quality boundary explicit.
- 2026-08-28: `python -m unittest discover` skips tests under `tools/` because
  the directory is not a package. Use explicit module targets.
- 2026-08-28: After a failed production submit, the first reboot plus bring-up
  can still fail its self-test with `iommu_map failed at 0x4000`. A second
  reboot restored a clean ladder. Do not proceed from `ANE_SELFTEST_FAILED`.
- 2026-08-28: Vectorized ANE packing is exact only for contiguous row-major tiles. A direct non-contiguous GGUF slice produced huge logits; keep the padded contiguous tile and preserve the command-BO write.
- 2026-08-28: `blob_swap_gemm` must clear the output sentinel before each ioctl. Polling without a fresh sentinel can read stale output and report false completion.
- 2026-08-29: A production Qwen task chain mixes compute and noncompute
  descriptors. Find aligned compute seeds, follow `NextPointer`, then include
  valid predecessors. Exact `TD_MAGIC` counts undercount the graph.
- 2026-08-29: Qwen HWX descriptors use BDX 0, 1, 3, 4, and 5. BDX 3 maps
  `__DATA,__bss` workspace. Missing it reaches the engine but times out.
- 2026-08-29: Derive aggregate input and output BO sizes from all
  `__FVMLIB,__const` and `__FVMLIB,__data` virtual ranges.
- 2026-08-29: `ANECCompile` needs trailing slashes on both
  `NetworkSourcePath` and `OutputFilePath`. A zero callback status does not
  prove export. Require a nonempty `model.hwx`.
- 2026-08-29: Keep the public MLX work in one `mlx-omarchy` repository. Keep hardware research here and stable driver ABI changes in `eiln/ane`.
- 2026-08-29: `voice_lint.py` computes Flesch from raw Markdown, including link targets and code. A short README with relative links can meet the public voice gate.
- 2026-08-29: Exact original-layout Qwen prefixes of one and 108 tasks still
  time out. Dense packed-prefix failures were not valid isolation because
  task links fetch later descriptors through command buffer bank 0.
- 2026-08-29: A clean one-task Qwen timeout leaves all TM error registers at
  the fine value and raises no active DART fault. The task manager stays
  non-idle, so missing BO mappings are not the current cause.
- 2026-08-29: Build M1 diagnostic modules against
  `~/.local/apple-hardware-sdk/usr/lib/modules/7.1.6-1-1-ARCH/build` with
  `LD_LIBRARY_PATH=~/.local/apple-hardware-sdk/usr/lib`. The live
  `/lib/modules/.../build` link is absent.
- 2026-08-29: `ANE_KO=/path sudo -n bash bringup.sh` drops `ANE_KO` through
  sudo and loads the normal module. Use
  `sudo -n env ANE_KO=/path bash bringup.sh`, then verify the observed poll
  duration or diagnostic log before trusting the module variant.
- 2026-08-29: A warm reconnect can occur before the requested reboot starts.
  Confirm `uptime -s` changed before uploading `/tmp` diagnostics.
- 2026-08-30: TM_COMMITTED advancing to the final task does not mean ANE
  execution completed. A diagnostic fallback returned success while output
  stayed unchanged. Require TM_STATUS idle and an observed output change.
- 2026-08-30: The exact fresh-compiled linear graph executes on macOS ANE but
  not through the Linux raw-task path. Exact tensors, kernel placement, and
  descriptor-chain headers are not the remaining difference.
- 2026-08-30: The macOS 26 compiler accepts h13 but does not emit the old
  self-contained format. Monterey ANECompiler 5.5.0 emits that format from
  legacy Espresso XML and its artifacts execute through the Linux raw-task path.
- 2026-08-30: Qwen needs 186 decoder projection graphs plus 31 tied-head
  chunks. All 217 fp16 sources compiled successfully; staged programs avoid
  the 3.5 GiB DART residency limit.
- 2026-08-30: Never interpose a high-frequency IOKit method without a hard
  event cap. One diagnostic produced nearly one million files before timeout.
- 2026-08-30: Old HWX `__FVMLIB` sections can describe virtual buffers larger
  than the file when their segment has no file payload.
- 2026-08-30: Old-format projections can declare zero workspace. Leave submit
  handle 3 unset instead of allocating a zero-byte buffer.
- 2026-08-30: The full compiled Qwen set has eight unique matrix shapes.
  Include the 2,048-by-2,048 class in geometry validation.
- 2026-08-30: Tool wrappers can add timing metadata outside raw stdout.
  Never write rendered command output back into source files.
- 2026-08-30: Monterey Espresso uses buffer index 4 for output and index 5
  for input. A square 2,048-by-2,048 graph hid the reversed binding. Verify
  asymmetric geometry before generalizing a buffer contract.
- 2026-08-30: `espresso_dump_ir` rejects a 270,368-element one-dimensional input with `-2`. Pack recurrent data as `(16, 133, 128)` rows instead of one huge width.
- 2026-08-30: Recurrent state can stay in two old-Espresso aggregate BOs. Write dynamic rows, submit, then swap buffer roles; do not copy the state between steps.
- 2026-08-30: A compiled Core ML neural network becomes Monterey ANECompiler input through `espresso_plan_add_network`, `espresso_plan_build`, and `espresso_dump_ir`.
- 2026-08-30: ANEForge exposes final decoder chunk output after output RMS normalization. Match that checkpoint only; keep the recurrent hidden state raw.
- 2026-08-30: Exact-input full-attention layers match the macOS reference within 0.0135 relative L2. DeltaNet layer 0 already differs by 0.2217 on its first token, so diagnose the DeltaNet path first.
- 2026-08-30: A second macOS M1 can clear ANECompiler resource exhaustion without rebooting the reference host. A precomputed prompt-to-token map removes the local tokenizer prerequisite.
- 2026-09-14: The 2026-08-30 Monterey buffer-index warning came true again on
  Linux/H13. libane bound roles positionally (`dst = 4 + i`,
  `src = 4 + dst_count + i`); that is only the order mil-hwxc normalizes
  Apple's selectors into, and Apple's own exports reverse it. The map lives in
  task word 8: three 5-bit selectors at shifts 0/6/12 for `0x13800`/`0x13804`/
  `0x17800`. Derive it; never assume a role order the header does not state.
- 2026-09-14: Order roles by ascending channel number, not by selector field
  position. Two proven artifacts carry the fields in opposite order
  (`0x00024966` and `0x000249a5`) and both put the destination on channel 4.
- 2026-09-14: A destination selector names the real output when its channel is
  an allocated surface, not when its config word takes some particular value.
  `0x000000c0`, `0x000000c1` and `0x040000c1` all appear on real output writes;
  a chain's in-flight result keeps its destination selector on channel 0.
  Gating on `0x040000c1` alone wrongly rejected `tile_r`, `reduce_mean`,
  `reduce_probe_max` and `select_rrb`.
- 2026-09-14: In a linked task stream, the NEXT descriptor's word count lives
  in bits 16:24 of word 1 of the CURRENT descriptor, and word 7 is its offset.
  Reading the count from the next descriptor degraded silently to the fallback
  path on all 60 multi-task programs instead of failing, so validate a decode
  against a corpus, not against one artifact.
- 2026-09-14: `td_size` must be truthful before any task-stream decode is
  possible. With the stale `0x274` the record walk runs into the CoreML weight
  blob and every exported bundle falls back. Two "independent" fixes were
  ordered.
- 2026-09-14: A check that compares a value to the formula that produced it
  cannot fail. `bundle.cpp` validates a manifest's declared channel against
  `4 + i`, and the adapter computed the declaration from `4 + i`, so a wrong
  channel passes. Look for the producer of a value before trusting its
  validator.
- 2026-09-14: Sentinel-seed every allocated channel before an execute. A
  per-channel tag in unwritten memory is what proves which surface the engine
  actually wrote, and it separated the destination-polarity fix from two
  further defects in the same artifact.
- 2026-09-14: Surface geometry is per-program, not a convention. The exported
  1x896 sets every tile-DMA byte count to `1792 = 896 * 2` (dense) while its
  header claims 64-byte planes; the proven 64-element program really does use
  `4096 = 64 * 64`. Read `0x13810`/`0x13814`/`0x17810` rather than assuming.
