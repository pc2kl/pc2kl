# pc2kl — test corpus and derivation (clean-room)

This folder contains everything needed to reproduce how the decoder tables were
obtained and how the decompiler was validated. It contains **no FANUC file and no
translator output**: only the author's test sources, the scripts, and the reports.
The `.pc` files and translator logs are regenerated locally by anyone holding a
licensed KAREL translator (`ktrans`); they are not distributed (see `.gitignore`).

## Layout

| Path | Content |
|---|---|
| `src/langage/` | hand-written programs, one language feature per line (expressions, control flow, conditions, motion, files, ports, positions…) |
| `src/include/` | files included by `%INCLUDE` in some tests (copied next to the output by `compiler_tests.bat`) |
| `src/builtins/` | one program per documented built-in routine, generated from the manual's syntax (`outils/gen_builtins.py`, `outils/gen_builtins2.py`) |
| `non_compiles/` | test sources the translator rejected (keywords, option packages not installed, invalid tests); kept for completeness |
| `outils/` | analysis, derivation and validation scripts (Python 3, no dependency) |
| `analyse/` | bytes generated for each source line, for four representative versions |
| `rapport_derivation.txt` | derivation report produced by `outils/derive_tables.py` |
| `verification_oplen.txt` | instruction-length check on the whole corpus |
| `roundtrip_rapport.txt` | round-trip validation report |

## Method

1. **Test sources** (`src/`) are written from the KAREL reference manual. The manual
   itself is not distributed; `outils/parse_manual.py` extracts the built-in syntax
   from the user's own copy. The names of motion system variables and of their
   enumerated values used in `w*.kl` come from the public system variable reference;
   every value used by the decoder is the one the translator actually produced.
2. **Compilation** (`compiler_tests.bat`, run on the licensed PC) of every source with
   every installed translator version (20 versions, V6.40 to V10.13) → `pc/`, `log/`.
3. **Comparative analysis**: `analyse/segments_<version>.txt` lists, for each source
   line, the bytes generated between two line markers. Instruction lengths were read
   from these listings (`outils/oplen_analyse.py`, with the source line each one was
   observed on) and then **verified** on the whole corpus (`outils/verifier_oplen.py`):
   every program must split exactly, with every routine entry, label and line marker
   on an instruction boundary.
4. **Table derivation** (`outils/derive_tables.py` → `../pc2kl/karel_tables.json`,
   report in `rapport_derivation.txt`): I/O port codes (`port_*.kl`), predefined files
   (`file_*.kl`), built-in function numbers and signatures (`src/builtins`), position
   and vector field offsets (`t_posfields.kl`), `WITH` clause ids (`w*.kl`) and
   enumerated values of motion system variables (`w_enum.kl`).
5. **Round-trip validation**: every compiled test is decompiled with `pc2kl`
   (`outils/decompiler_tout.py`), the result is recompiled with the *same* translator
   version (`recompiler_decompiles.bat`), and the new `.pc` is compared with the
   original (`outils/compare_pc.py`, `outils/roundtrip.py`): same declarations, same
   instruction sequence up to consistent renaming of variables, routines and labels.

## Reproducing

On a Windows PC with a licensed translator, from this folder:

```
compiler_tests.bat                              :: src\  -> pc\, log\
python outils\verifier_oplen.py .               :: instruction lengths
python outils\derive_tables.py . tables.json    :: rebuild the tables, compare with ..\pc2kl\karel_tables.json
python outils\decompiler_tout.py                :: pc\   -> roundtrip\kl\
recompiler_decompiles.bat                       :: roundtrip\kl\ -> roundtrip\pc\, roundtrip\log\
python outils\roundtrip.py pc roundtrip\pc roundtrip\log roundtrip_rapport.txt
```

The translator is located through the `KTRANS` environment variable, `PATH`, or the
default WinOLPC install folder. It is never copied into this folder. Set `VERS`
(e.g. `set VERS=V9.40-1`) to limit compilation to some versions.
