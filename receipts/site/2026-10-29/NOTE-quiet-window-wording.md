# Note: what "Measured quiet ... between <start>/<finish>" means in these receipts

Receipts published on 2026-10-29 carry a sentence of the form "Measured quiet: no other ticket or Neural Engine row on this machine between <first start>/<last finish> (guard record)". For a cell made of several rounds or several sessions, that window runs from the first round's start to the last round's finish. **The check was applied to each round's own start-to-finish window, not to the gaps between rounds**, and the lab's other jobs did run in some of those gaps. Receipts published after this note say so in the sentence itself.

It affects the multi-session cells: the Intel Arc Pro B60 27B at 32k (`receipts/site/2026-10-28/arc-pro-b60-24-qwen3.8-27b-ud-q4km-llamacpp-vulkan.json`; its window spans two boots, the rounds are from two sessions and the cell's note states that their decode speeds differ by 6.3 percent), the RTX 5060 Ti Qwen3.8-9B and Gemma 4 12B cells, the M2 Qwen3.8-9B 64k cell, and the jwm1 Qwen3.5-9B 32k cell.

The guard record is the lab's own list of finished GPU and Neural Engine tickets plus one busy/idle sample per minute per engine. It does not see CPU-only jobs such as builds or file copies; the ones we know of are listed in `NOTE-shared-host-cpu-only.md` (2026-10-28).
