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

* Validated by round trip (decompile, recompile, compare) on about 300 test programs
  compiled with 20 translator versions (5,904 `.pc` files), V6.40 to V10.13 — see
  [docs/VALIDATION.md](docs/VALIDATION.md) for what is compared and the current results. Constructs absent from the test corpus may
  not be recognised yet; unknown opcodes are reported explicitly rather than guessed.
* Programs using vision, force, or other option packages may produce partial output.
* Always review and test recovered code on a simulator before running it on a robot.
  Robots are dangerous machines; you are solely responsible for what you run on them.

## Legitimate use only

Use this tool only on programs you own, or that you are authorised to maintain by
their owner. Do not use it to obtain or redistribute other people's code, to bypass
protections, or in breach of a licence agreement. See [LEGAL.md](LEGAL.md).

## Legal disclaimer

pc2kl is provided solely as an independent interoperability, maintenance, research and recovery tool.

The project and its contributors make no representation that use of this software is lawful or permitted in every jurisdiction, contractual situation or licensing environment. Laws and contractual restrictions relating to software reverse engineering, interoperability, copyright, trade secrets and technical protection measures may vary between countries and circumstances.
Nothing in this repository constitutes legal advice.

By downloading, using, modifying or redistributing this software, you accept full responsibility for:

* ensuring that you have the legal right and authorisation to process the relevant .pc files;

* complying with all applicable laws, licences, contracts and confidentiality obligations;

* reviewing and validating any source code produced by the tool;

* testing recovered programs in a safe environment before deployment;

* any consequences resulting from the use of the software or its generated output.

Recovered source code is not guaranteed to be complete, accurate, safe or functionally identical in every possible case.

This software must not be relied upon as a safety mechanism. Industrial robots and automated machinery can cause serious injury, death, equipment damage and production losses. Recovered or modified programs should be reviewed by appropriately qualified personnel and validated using appropriate simulation, testing, risk-assessment and safety procedures before being used on real equipment.

To the maximum extent permitted by applicable law, the authors and contributors shall not be liable for any direct, indirect, incidental, consequential or other damage arising from the use of, inability to use, or reliance upon this software or its output.

For the full legal notice, please read LEGAL.md.

## Contact

For technical questions, compatibility reports, bug reports, responsible legal enquiries, or rights-holder concerns:

Email: pc2klmail@gmail.com

Please do not send confidential, proprietary or customer-owned KAREL programs unless you are authorised to disclose them.

When reporting a compatibility issue, a minimal reproducible example is preferred whenever possible.

## License

See [LICENSE](LICENSE). The software is provided "as is", without warranty of any kind.