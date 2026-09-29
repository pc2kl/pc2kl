# Validation

The decompiler is validated by a **round trip** on the whole test corpus:

1. every test source in `tests/src` (300 programs written from the KAREL
   reference manual) is compiled with each of the 20 translator versions installed on
   the author's licensed workstation (V6.40 to V10.13) — 5,864 `.pc` files;
2. each `.pc` is decompiled with `pc2kl`;
3. the decompiled source is recompiled with the same translator version;
4. the recompiled `.pc` is compared with the original (`tests/outils/compare_pc.py`):
   same declarations, same instruction sequence up to a consistent renaming of
   variables, routines and labels (line markers are ignored, since the layout of the
   regenerated source differs).

Result (28 September 2026): **5,864 / 5,864 identical**.

| Versions | Programs | Identical |
|---|---|---|
| V6.40, V6.43 | 275 each | 275 |
| V7.20, V7.30 | 279 each | 279 |
| V7.40 | 288 | 288 |
| V7.50, V7.70 | 295 each | 295 |
| V8.10, V8.13 | 297 each | 297 |
| V8.20 | 298 | 298 |
| V8.23 to V9.40 | 299 each | 299 |
| V10.10, V10.13 | 297 each | 297 |

The counts differ between versions because some translators reject some tests (for
example strings longer than 128 characters before V7.40, or `WITH` on
`MOVE ALONG pth[1..2]` in V10.x); such tests are listed in the compilation logs.

The per-program report is `tests/roundtrip_rapport.txt`. A test corpus cannot cover
every construct: programs using option packages (vision, iRVision, DAQ, remote
registers…) or unusual code may still expose unknown instructions, which the tool
reports explicitly instead of guessing.
