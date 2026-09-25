# prog_001 (stage B) TD DMA word table — 55 TDs, unrolled per-position recurrence

| bank (chan) | role | DMA word(s) | surface |
| --- | --- | --- | --- |
| src 4 | q/k/v-class (4096 B) | 0x33881 | one of q/k/v |
| src 5 | same class | 0x33881 | |
| src 9 | same class | 0x33881 | |
| src 11 | same class | 0x33881 | |
| src 10 | distinct geometry | 0x3bb81 | |
| src 6 | recurrent state, two variants (0x33b01 first pass, 0x73b01 bit-18 on later passes) | S (16,128,128) 524288 B |
| dst 6/3 | intermediate writes | 0x40003c1 | |
| dst 8 | state write | 0x40000c1 | Sout (16,128,128) |

4096 B-class vs 32 B-class surfaces are not yet distinguished in the words;
next step: per-TD correlation against the known per-surface byte sizes
(ane_channels.py already pairs every TD with its bank).
