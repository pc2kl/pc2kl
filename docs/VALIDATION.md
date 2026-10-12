# Validation

The decompiler is validated by a **round trip** on the whole test corpus:

1. every test source in `tests/src` (about 325 programs written from the KAREL
   reference manual) is compiled with each of the 20 translator versions installed on
   the author's licensed workstation (V6.40 to V10.13);
2. each `.pc` is decompiled with `pc2kl` (`tests/outils/decompiler_tout.py`);
3. the decompiled source is recompiled with the same translator version
   (`tests/recompiler_decompiles.bat`);
4. the recompiled `.pc` is compared with the original
   (`tests/outils/compare_pc_strict.py`, called by `tests/outils/roundtrip.py`).

## What the comparator checks

`compare_pc_strict.py` requires, between the original and the recompiled `.pc`:

* the same instruction sequence, line markers excepted (the layout of the regenerated
  source differs). References to **global variables** are resolved to their names
  through the used-variable map, and calls to **routines** to the routine names, so a
  reference bound to the wrong variable or routine is a difference. Only local
  variables and parameters, whose names are not stored in a `.pc`, are compared up to a
  consistent renaming (order of first use). Branch targets are compared as instruction
  positions;
* the same declarations, in the same order: name, `FROM` module, storage (`IN CMOS`,
  `IN SHADOW`, `%UNINITVARS` flag) and type;
* the same user types (field names, order and types);
* the same routine table: name, module, return type, parameter types and first
  instruction of the body;
* the same program name, `%COMMENT` and configuration attributes (`%STACKSIZE`,
  `%PRIORITY`, `%NOPAUSE`, `%LOCKGROUP`, …) and the same `FROM` modules.

Not compared: the `*ID*` module (a program identifier that changes at every
compilation) and the last bytes of the file (see [FORMAT.md](FORMAT.md)); differences
there are reported as `INFO` only.

The comparator is itself tested by mutation (`tests/outils/test_comparateur.py`): an
original `.pc` is altered in a way that changes the program (two globals of the same
type swapped, a variable moved to CMOS, `%STACKSIZE`/`%NOPAUSE`/`%LOCKGROUP` changed,
program name changed, a parameter type changed, the bodies of two routines swapped,
two branch targets swapped) and the comparator must report a difference. On V8.33
(299 programs) and V6.40 every mutation is detected.

An earlier comparator (`compare_pc.py`, kept for reference) renamed global variables
and routines as well and did not compare storage flags, configuration attributes,
types or the routine table; such mutations went undetected. It was replaced on
30 September 2026 after a user report.

## Results

Strict comparison of the round trip, 12 October 2026 (current `pc2kl`, `compare_pc_strict`):
**6,402 / 6,402 identical**.

| Versions | Programs | Identical |
|---|---|---|
| V6.40, V6.43 | 300 each | 300 |
| V7.20, V7.30 | 304 each | 304 |
| V7.40 | 314 | 314 |
| V7.50, V7.70 | 323 each | 323 |
| V8.10, V8.13 | 325 each | 325 |
| V8.20 | 326 | 326 |
| V8.23 to V9.40 | 327 each | 327 |
| V10.10, V10.13 | 321 each | 321 |

The `WITH`, directive and `%INVISIBLE` suites (`pc_with`, `pc_dir`, `pc_inv` in the
working corpus, 1,413 more `.pc` files) were run through the same round trip on
12 October 2026: all identical.

History. When the strict comparator was introduced (30 September 2026), the previous
version of `pc2kl` showed 22 differences, all fixed on 30 September – 1 October 2026:

* `w_d_uninit`, V7.20 to V10.13 (18): `%UNINITVARS` was not regenerated;
* `t_strsize4` and `w_path`, V6.40/V6.43 (4): in the V6 format the `PATHHEADER` type
  code of a `PATH` was not normalised, and the implicit first field of a `PATH` node
  was not restored (`pth.HS = …` became `pth = …`, `pth[1].J1 = …` became `pth[1] = …`).
  These 4 had previously been validated only with hand-corrected sources.

The tests `t_arrfunc` and `t_arrfunc3` (functions returning an array, opcode `1E`)
were added on 1 October 2026.

On 8 October 2026, after a user report, the tests `tests/src/langage/f_*.kl` (24
programs: PATH types and parameters, `GROUP_ASSOC`/`COMMON_ASSOC`, `XYZWPREXT`, `MOVE`
variants and local conditions, `AT NODE`, condition handlers with `EVAL`/`WITH`/all
actions, `HAND`, `FRAME` with three arguments, `SELECT`, `BYNAME`, routines, directives,
real constants) and `tests/src/builtins/FRAME__3.kl` were added. Before the fixes, 7 of
them failed to recompile or differed (`HAND`, `FRAME` with three arguments, `AT NODE`,
`MOVE RELATIVE` of a VECTOR, only the last `WHEN` of a `MOVE` kept, unknown condition
actions and missing `EVAL`, mislabelled `COMMON_ASSOC`/`GROUP_ASSOC`, PATH parameters,
`%ENVIRONMENT`, forward declarations of routines only called from the main program).

On 12 October 2026 a contributor sent a program calling every built-in routine of the
manual, with and without optional arguments (format 0x27, compiled with option packages).
Decompiled with the 8 October version, it recompiled but differed: the group number of
`IN_RANGE(p, i)` / `J_IN_RANGE(j, i)` was dropped, and `CNCL_STP_MTN` / `MOTION_CTL`
without arguments came back with their default value written out. Both are fixed
(see [FORMAT.md](FORMAT.md#optional-parameters-of-built-ins)) and covered by
`tests/src/langage/f_optarg_t.kl`. The contributor's program itself is not part of the
corpus; decompiled and recompiled with the same ROBOGUIDE configuration, it is identical
to its source compiled with that configuration.

The counts per version differ because some translators reject some tests (for example
strings longer than 128 characters before V7.40, or `WITH` on `MOVE ALONG pth[1..2]` in
V10.x); such tests are listed in the compilation logs.

The per-program report is `tests/roundtrip_rapport.txt`. A test corpus cannot cover
every construct: programs using option packages (vision, iRVision, DAQ, remote
registers…) or unusual code may still expose unknown instructions, which the tool
reports explicitly instead of guessing.
