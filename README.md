# pc2kl — KAREL p-code (.pc) to source (.kl) recovery tool

`pc2kl` rebuilds a readable, recompilable KAREL source file (`.kl`) from a compiled
KAREL program (`.pc`). Its purpose is **maintenance and interoperability**: recovering
the sources of *your own* programs when the original `.kl` has been lost, so that they
can be read, fixed, and recompiled for a newer robot controller.

> This is an independent project. It is not affiliated with, endorsed by, or supported
> by FANUC Corporation or any of its subsidiaries. FANUC, KAREL, ROBOGUIDE and WinOLPC
> are trademarks of their respective owners and are used here only to describe
> compatibility. See [LEGAL.md](LEGAL.md) before using or redistributing this project.

## What it does

* Decompresses the `.pc` container and parses its sections (program header, p-code,
  labels, modules, user types, variables, routine table).
* Rebuilds declarations (`CONST`, `TYPE`, `VAR`, `ROUTINE`), control flow
  (`IF/ELSE`, `WHILE`, `REPEAT`, `FOR`, `SELECT`), expressions, condition handlers,
  motion statements, I/O ports, file I/O and built-in calls.
* Produces a `.kl` file that recompiles; the result is intended to be *functionally*
  equivalent to the original, not textually identical.

What cannot be recovered because it is not stored in a `.pc`: comments, the names of
local variables and routine parameters (regenerated as `p1`, `l_3`, ...), `CONST`
names (replaced by their value), and source formatting.

## Usage

```
python pc2kl/pc2kl.py program.pc -o program.kl
python pc2kl/pc2kl.py program.pc --asm        # annotated p-code listing
```

Python 3.8+ is required. No third-party packages. No FANUC software is needed to run
the tool; a licensed KAREL translator is only needed to recompile the recovered source.

## How the format knowledge was obtained

The data tables used by the decoder (`pc2kl/karel_tables.json`) were obtained by
**black-box observation**: small test programs written from the KAREL
reference manual were compiled with a legitimately licensed translator, and the
resulting `.pc` files were compared with their sources. The complete, reproducible
test corpus, scripts and derivation reports are in the [`tests/`](tests/) folder of this
repository. See [docs/FORMAT.md](docs/FORMAT.md).

This repository contains **no FANUC software, library, executable, support file,
manual, or excerpt of manual**, and no `.pc` file produced from third-party programs.

## Limitations

* Validated by round trip (decompile, recompile, compare) on 5,074 test programs
  compiled with 20 translator versions, V6.40 to V10.13 — see
  [docs/VALIDATION.md](docs/VALIDATION.md). Constructs absent from the test corpus may
  not be recognised yet; unknown opcodes are reported explicitly rather than guessed.
* Programs using vision, force, or other option packages may produce partial output.
* Always review and test recovered code on a simulator before running it on a robot.
  Robots are dangerous machines; you are solely responsible for what you run on them.

## Legitimate use only

Use this tool only on programs you own, or that you are authorised to maintain by
their owner. Do not use it to obtain or redistribute other people's code, to bypass
protections, or in breach of a licence agreement. See [LEGAL.md](LEGAL.md).

## License

See [LICENSE](LICENSE). The software is provided "as is", without warranty of any kind.
