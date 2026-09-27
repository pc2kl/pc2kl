# Validation

The decompiler is validated by a **round trip** on the whole test corpus:

1. every test source in `tests/src` (260 programs written from the KAREL
   reference manual) is compiled with each of the 20 translator versions installed on
   the author's licensed workstation (V6.40 to V10.13) — 5,074 `.pc` files;
2. each `.pc` is decompiled with `pc2kl`;
3. the decompiled source is recompiled with the same translator version;
4. the recompiled `.pc` is compared with the original (`tests/outils/compare_pc.py`):
   same declarations, same instruction sequence up to a consistent renaming of
   variables, routines and labels (line markers are ignored, since the layout of the
   regenerated source differs).

Result (26 September 2026): **5,074 / 5,074 identical**.

| Versions | Programs | Identical |
|---|---|---|
| V6.40, V6.43 | 238 each | 238 |
| V7.20, V7.30 | 240 each | 240 |
| V7.40 | 248 | 248 |
| V7.50, V7.70 | 255 each | 255 |
| V8.10, V8.13 | 257 each | 257 |
| V8.20 | 258 | 258 |
| V8.23 to V9.40 | 259 each | 259 |
| V10.10, V10.13 | 258 each | 258 |

The per-program report is `tests/roundtrip_rapport.txt`. A test corpus cannot cover
every construct: programs using option packages (vision, iRVision, DAQ, remote
registers…) or unusual code may still expose unknown instructions, which the tool
reports explicitly instead of guessing.
