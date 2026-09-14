# 2026-09-14 review followthrough

Close remaining OrchestrationReview and LandedCodeReview findings, or name why each stays open.
Did not re-litigate landed items (driver `6fa243a`, compiler pin, status sync, bundle derived channels, LSTM CPU contract, occupancy, SPIR-V cache, projector). Did not merge `63c1d3cf`. No fleet, no GPU/ANE, no formatter.

resolved_model: this session (`xai-oauth/grok-4.6`). fallback: true (assigned route was mlx-openai).

## Proof

```text
python3 -m unittest tools.test_hwxv2_to_anec -q
----------------------------------------------------------------------
Ran 31 tests in 0.271s

OK
```

Host: omp-studio-local, cwd `ane-linux-experiments` `4ed82cf` then local converter edits. mil-hwx-compiler `27cb730` then local `docs/ane/numerics.md` edit.

## LandedCodeReview

| Finding | Action |
|---|---|
| P0 GEM free path / kfree live BOs (`8554583`) | already closed — driver `6fa243a` |
| P0 `ane_submit` leaks `bo_lookup` refs | already closed — driver `6fa243a` |
| P0 T6001 debug scaffolding | already closed — driver `6fa243a` |
| P1 `drm_mm_init` end-as-size | already closed — driver `6fa243a` |
| P1 unmap dangling mm/iova | already closed — driver `6fa243a` |
| P1 PM open/ioctl swallow/unbalance | already closed — driver `6fa243a` |
| P1 `walk_registers` ignores optional extra word | **fixed** — `tools/hwxv2-to-anec.py` `extra_header_bytes`: skip one word iff `header[9] & 0x3 == 0x3` (not bit 1 alone) |
| P1 genpd `device_link_del` / single-PD | already closed — driver `6fa243a` |
| P2 submit/BO size bounds removed | already closed with the lifecycle rebase; not reopened |
| P2 `ane_bind_init` silent positional map | already closed — `5113ef6` `STRICT_BIND` |
| P2 predecessor scan hardcodes `TD_SIZE 0x274` | **fixed** — scan floor is `TASK_HEADER_SIZE`; unused `TD_SIZE` constant deleted |
| P3 TM `dev_info` hot-path | already closed with the lifecycle rebase; not reopened |

New tests: extra word is not a record; `0x26` does not skip; predecessor at `0x200` in a `0x400` section is found.

## OrchestrationReview

| Finding | Action |
|---|---|
| Retire 1x896 forbidden status | already closed — status sync / GATES G5 / THEORY pin |
| Pin compiler past select scratch (`7ab3eb5`) | already closed — compiler pin |
| Rewrite mil THEORY off retracted L2 hole | already closed — THEORY names scratch arena and retracts `h13.select-first-l2-tile` |
| Banner-supersede `select-l2-tile` receipt | already closed — `SUPERSEDED-BY` header |
| Land omarchy-ane libane vs T6001 kmod | already closed — driver `6fa243a` |
| Refresh GATES G5 | already closed |
| Correct jw16 islands `named_hole` | **leftover** — `mlx-omarchy/receipts/2026-09-14-encoder-islands-exec-jw16mbp1-linux.json` still stores `h13.select-first-l2-tile` as the run's second-hand label. Historical receipt; THEORY/fix receipt already retract it. Not rewritten here. |
| Refresh Parakeet plan appendix gates 6-10 | **leftover** — plan appendix is a persistence snapshot; live receipts exist. Parent owns publication. |
| Rewrite ane-linux THEORY pin block | already closed — mlx-omarchy pin is `7f8786b0` |
| Land 1x896 converter onto main | already closed on this `main` (`4ed82cf`; fixture tests cover 1x896 geometry) |
| Collapse three duplicate MIL numpy evaluators | **leftover** — receipt-local copies; parent owns overlay consolidation. Closed after this review by mlx-omarchy `9fd0e1c7` (`overlay/tools/coreml/mil_numpy.py` + `CANONICAL-EVALUATOR.md` pointers). |
| Record `resolved_model` on 1x896 family | already closed on `1x896-export-fix.json` |
| Name unmerged T6001 DTS branch | **leftover** — packaging status, not this slice |
| Interpolator open question in `docs/ane/numerics.md` | **fixed** — measured rule (ties-away, magnitude-indexed): 1536/1536 tanh, 1533/1536 sigmoid vs H13 LUT on T8103. LUT is not the decoder contract. Open-questions bullet removed. |

## Not done

- No merge of `63c1d3cf`.
- No hardware pass. Converter tests are host-only.
- jw16 JSON `named_hole`, duplicate evaluators, plan appendix, T6001 DTS naming left as named leftovers.
