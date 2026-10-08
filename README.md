# pc2kl — KAREL p-code (.pc) to source (.kl) recovery tool

`pc2kl` rebuilds a readable, recompilable KAREL source file (`.kl`) from a compiled
KAREL program (`.pc`). Its purpose is **maintenance and interoperability**: recovering
the sources of *your own* programs when the original `.kl` has been lost, so that they
can be read, fixed, and recompiled for a newer robot controller.

> This is an independent project. It is not affiliated with, endorsed by, or supported
> by FANUC Corporation or any of its subsidiaries. FANUC, KAREL, ROBOGUIDE and WinOLPC
> are trademarks of their respective owners and are used here only to describe
> compatibility. See [LEGAL.md](LEGAL.md) before using or redistributing this project.

## Usage

```
python pc2kl/pc2kl.py [-h] [-o OUT] [--asm] [--no-lines] pc [pc ...]
```

| Argument | Effect |
|---|---|
| `pc` (one or more) | `.pc` file(s) to decompile, or folder(s): every `.pc` in a folder is processed, in alphabetical order |
| `-o OUT`, `--out OUT` | with a single `.pc`: output `.kl` file. With several `.pc` files, or if `OUT` is a folder: one `OUT/name.kl` per `name.pc` (the folder is created if needed). Without `-o`, the source is written to standard output |
| `--asm` | print the annotated p-code listing (offset and bytes of each instruction); unknown opcodes are flagged `<-- ?? opcode XX inconnu` |
| `--no-lines` | do not realign source line numbers (compact output, without the blank lines that restore the original numbering) |
| `-h`, `--help` | show the help |

Examples:

```
python pc2kl/pc2kl.py program.pc                   # source to standard output
python pc2kl/pc2kl.py program.pc -o program.kl     # write program.kl
python pc2kl/pc2kl.py program.pc --asm             # listing, then source, to standard output
python pc2kl/pc2kl.py program.pc --asm -o prog.kl  # listing to standard output, source to prog.kl
python pc2kl/pc2kl.py my_folder -o out/            # every .pc of a folder -> out/*.kl
python pc2kl/pc2kl.py a.pc b.pc -o out/            # several files
python pc2kl/pc2kl.py program.pc --no-lines -o program.kl
```

* For each file written, `program.pc -> program.kl` is printed, with the number of points
  to check (`-- ??` marks) if any.
* Errors and warnings (e.g. unknown opcode, incomplete output) go to standard error; a
  failing file does not stop the processing of the others.
* `.kl` files are written in Latin-1.
* The translator version does not need to be given: the format is detected from the
  `.pc` (V6.40 to V10.13).

Python 3.8+ is required, with no third-party packages. No FANUC software is needed to
run the tool; a licensed KAREL translator is only needed to recompile the recovered
source.

## What it does

* Decompresses the `.pc` container and parses its sections (program header, p-code,
  labels, modules, user types, variables, routine table).
* Rebuilds translator directives, declarations (`CONST`, `TYPE`, `VAR`, `ROUTINE`),
  control flow (`IF/ELSE`, `WHILE`, `REPEAT`, `FOR`, `SELECT`), expressions, condition
  handlers, motion statements, I/O ports, file I/O and built-in calls.
* Produces a `.kl` file that recompiles; the result is intended to be *functionally*
  equivalent to the original, not textually identical.

### What cannot be recovered

Some information is not stored in a `.pc` file at all:

* comments and source formatting;
* the names of local variables and routine parameters (regenerated as `p1`, `l_3`, ...);
* `CONST` names (replaced by their value) and the names of `%INCLUDE` files;
* the directives that leave no trace: `%INCLUDE`, `%RWACCESS`, `%CRTDEVICE`, `%DEFGROUP`,
  `%DELAY`; for `%ENVIRONMENT`, only its use is detectable (the environments needed by the
  built-ins called are written back, see [docs/FORMAT.md](docs/FORMAT.md#translator-directives)).

Default storage directives (`%CMOSVARS`, `%SHADOWVARS`, `%SHCMOSVARS`, `%CMOS2SHADOW`)
are restored as `IN CMOS` / `IN SHADOW` on each variable, which recompiles to the same
`.pc`. See [docs/FORMAT.md](docs/FORMAT.md#translator-directives) for the full list.

## Validation and limitations

* Validated by round trip (decompile, recompile, compare) on about 325 test programs
  compiled with 20 translator versions, V6.40 to V10.13 (6,387 `.pc` files). See
  [docs/VALIDATION.md](docs/VALIDATION.md) for what is compared and the current results.
* Constructs absent from the test corpus may not be recognised yet; unknown opcodes are
  reported explicitly rather than guessed. Decoding resumes at the next certain instruction
  boundary (label, routine entry, or a consistent line marker): the skipped bytes and the
  pending operands are written as a highlighted `-- ??` comment block, statements left
  with a missing operand (`?`) are tagged, and a warning is placed at the top of the file.
  If a routine's structure still cannot be rebuilt, its disassembly is written as comments
  so that the rest of the file is kept.
* Programs using vision, force, or other option packages may produce partial output.
* Always review and test recovered code on a simulator before running it on a robot.
  Robots are dangerous machines; you are solely responsible for what you run on them.

## How the format knowledge was obtained

The data tables used by the decoder (`pc2kl/karel_tables.json`) were obtained by
**black-box observation**: small test programs written from the KAREL reference manual
were compiled with a legitimately licensed translator, and the resulting `.pc` files
were compared with their sources. The complete, reproducible test corpus, scripts and
derivation reports are in the [`tests/`](tests/) folder. The observed format is
described in [docs/FORMAT.md](docs/FORMAT.md).

This repository contains **no FANUC software, library, executable, support file,
manual, or excerpt of manual**, and no `.pc` file produced from third-party programs.

## Legitimate use only

Use this tool only on programs you own, or that you are authorised to maintain by
their owner. Do not use it to obtain or redistribute other people's code, to bypass
protections, or in breach of a licence agreement. See [LEGAL.md](LEGAL.md).

## Legal disclaimer

pc2kl is provided solely as an independent interoperability, maintenance, research and
recovery tool.

The project and its contributors make no representation that use of this software is
lawful or permitted in every jurisdiction, contractual situation or licensing
environment. Laws and contractual restrictions relating to software reverse
engineering, interoperability, copyright, trade secrets and technical protection
measures may vary between countries and circumstances. Nothing in this repository
constitutes legal advice.

By downloading, using, modifying or redistributing this software, you accept full
responsibility for:

* ensuring that you have the legal right and authorisation to process the relevant
  `.pc` files;
* complying with all applicable laws, licences, contracts and confidentiality
  obligations;
* reviewing and validating any source code produced by the tool;
* testing recovered programs in a safe environment before deployment;
* any consequences resulting from the use of the software or its generated output.

Recovered source code is not guaranteed to be complete, accurate, safe or functionally
identical in every possible case.

This software must not be relied upon as a safety mechanism. Industrial robots and
automated machinery can cause serious injury, death, equipment damage and production
losses. Recovered or modified programs should be reviewed by appropriately qualified
personnel and validated using appropriate simulation, testing, risk-assessment and
safety procedures before being used on real equipment.

To the maximum extent permitted by applicable law, the authors and contributors shall
not be liable for any direct, indirect, incidental, consequential or other damage
arising from the use of, inability to use, or reliance upon this software or its
output.

For the full legal notice, please read [LEGAL.md](LEGAL.md).

## Contact

For technical questions, compatibility reports, bug reports, responsible legal
enquiries, or rights-holder concerns: **pc2klmail@gmail.com**

Please do not send confidential, proprietary or customer-owned KAREL programs unless
you are authorised to disclose them. When reporting a compatibility issue, a minimal
reproducible example is preferred whenever possible.

## License

See [LICENSE](LICENSE). The software is provided "as is", without warranty of any kind.
