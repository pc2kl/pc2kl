# The KAREL `.pc` format (as observed)

Everything below was established by compiling the test programs in `tests/src`
(written from the KAREL reference manual) with licensed translators, V6.40 to V10.13,
and comparing each source line with the bytes it produced. It describes observed
behaviour only; it is neither complete nor authoritative.

## Container

| Offset | Size | Content |
|---|---|---|
| 0 | 2 | magic `FE EF` |
| 2 | 2 | `00 01` |
| 4 | 4 | decompressed size (big-endian) |
| 8 | … | LZSS stream |

LZSS parameters (found by trial on the corpus until every file decompressed to the
announced size): 4096-byte window pre-filled with `0x00`, first write position 4078,
flag byte read LSB first (`1` = literal byte, `0` = back-reference), reference =
2 bytes: position `b0 | (b1 & 0xF0) << 4`, length `(b1 & 0x0F) + 3`.

## Decompressed image

All integers are big-endian.

1. `u16` format id (see below)
2. `u16` p-code size
3. program name, then `%COMMENT` text (both NUL-terminated)
4. header attributes: 20 bytes (19 in format 0x22), see [Header attributes](#header-attributes)
5. p-code
6. padding up to `FF`
7. labels: `u16` count + `u32` offsets
8. modules: `u16` count + NUL-terminated names (including a `*ID*xxxx` entry that
   depends on the source)
9. user types: `u16` count + (`u16` length + record)
10. variables: `u16` count + (attribute, name, storage flag, type), see
    [Storage flags](#storage-flags)
11. used-variable map, routine table (name, module, offset, return type, parameter types)
12. 3 trailing bytes: a `u16` whose meaning is not known, then `0A`

The trailing `u16` depends on the source and not only on the p-code: `t_misc.kl`, which
has two `USING ... ENDUSING` blocks, gives 20 more than its decompiled source (identical
p-code, `USING` leaves no trace). It is probably a size estimate made by the translator.

### Format id

| Id | Translator versions |
|---|---|
| `0x22` | V6.40, V6.43 |
| `0x24` | V7.20 |
| `0x25` | V7.30 |
| `0x26` | V7.40 – V7.70 |
| `0x27` | V8.10 – V8.33 |
| `0x28` | V8.36 |
| `0x29` | V9.10 – V9.40 |
| `0x2A` | V10.10, V10.13 |

### Header attributes

| Byte | Directive | Value |
|---|---|---|
| 0 | `%POWERFAIL` | `01` when set |
| 1 | `%INVISIBLE` | `01` when set |
| 2 | `%SYSTEM` | `01` when set |
| 3 | `%NOBUSYLAMP` | `01` when set |
| 4 | `%NOABORT` | mask: `1` ERROR, `2` COMMAND, `4` TPENABLE |
| 5 | `%NOPAUSE` | same mask as `%NOABORT` |
| 6 | — | never seen non-zero |
| 7 | `%TPMOTION` | `01` when set |
| 8 | `%NOPAUSESHFT` | `01` when set |
| 9–10 | `%STACKSIZE` | `u16`, `FFFF` when absent |
| 11–12 | `%PRIORITY` | `u16`, `FFFF` when absent |
| 13–14 | `%TIMESLICE` | `u16`, `FFFF` when absent |
| 15 | `%ALPHABETIZE` | `01` when set |
| 16 | — | never seen non-zero; absent in format 0x22 |
| 17 | `%LOCKGROUP` | group mask (bit 0 = group 1); `00` = `%NOLOCKGROUP`; default `FF` (`1F` in format 0x22, `7F` in V7.30) |
| 18 | `%FLASHROM` | `01` when set |
| 19 | — | never seen non-zero |

### Storage flags

Each variable carries a storage flag. Directives that change the default storage set
it on every variable declared without an explicit `IN CMOS` or `IN SHADOW`.

| Flag | Meaning |
|---|---|
| `00` | normal (DRAM) |
| `FD` | `IN CMOS`, `%CMOSVARS`, `%SHCMOSVARS`, `%FASTCMOSVAR` from V7.50 |
| `02` | `IN SHADOW`, `%SHADOWVARS`; also every `IN CMOS` variable under `%CMOS2SHADOW` |
| `FA` | `%UNINITVARS` (V7.20 and later; V6.40/V6.43 store `00`) |
| `03` | `%NOSCANSVARS` (V7.50 and later) |
| `FC` | `%FASTCMOSVAR` (V7.20 – V7.40) |

## Translator directives

Where each directive of the translator ends up, and what `pc2kl` writes back. Programs
compiled with directives that are only reflected in storage flags recompile to the same
`.pc` from `IN CMOS` / `IN SHADOW` declarations, so the directive itself is not needed.
Directives marked *not in the manual* are accepted by `ktrans` but undocumented in the
KAREL reference manual. Tests: `tests/src/langage/w_d_*.kl`, `inv_*.kl` and
`tests/src/directives/d_*.kl`.

| Directive | Stored as | Restored as | Notes |
|---|---|---|---|
| `%ALPHABETIZE` | byte 15 | directive | |
| `%CMOSVARS` | flag `FD` | `IN CMOS` | |
| `%CMOS2SHADOW` | flag `02` on `IN CMOS` variables | `IN SHADOW` | rejected by V6.x |
| `%COMMENT` | after the program name | directive | |
| `%CRTDEVICE` | no header trace | — | recompiles identically |
| `%DEFGROUP` | no header trace | — | recompiles identically |
| `%DELAY` | no header trace | — | recompiles identically |
| `%ENVIRONMENT` | no trace | — | translation only |
| `%FASTCMOSVAR` | flag `FC` (V7.20 – V7.40), `FD` later | directive / `IN CMOS` | not in the manual; rejected by V10.x |
| `%FLASHROM` | byte 18 | directive | not in the manual |
| `%INCLUDE` | no trace | included text | see [%INCLUDE and CONST](#include-and-const) |
| `%INVISIBLE` | byte 1 | directive | not in the manual |
| `%LOCKGROUP` | byte 17 | directive | |
| `%NOABORT` | byte 4 | directive | |
| `%NOBUSYLAMP` | byte 3 | directive | |
| `%NOLOCKGROUP` | byte 17 = `00` | directive | |
| `%NOPAUSE` | byte 5 | directive | |
| `%NOPAUSESHFT` | byte 8 | directive | |
| `%NOSCANSVARS` | flag `03` | directive | not in the manual; V7.50 and later |
| `%POWERFAIL` | byte 0 | directive | not in the manual |
| `%PRIORITY` | bytes 11–12 | directive | |
| `%RWACCESS` | no trace | — | not in the manual |
| `%SHADOWVARS` | flag `02` | `IN SHADOW` | |
| `%SHCMOSVARS` | flag `FD` | `IN CMOS` | not in the manual; rejected by V10.x |
| `%STACKSIZE` | bytes 9–10 | directive | |
| `%SYSTEM` | byte 2 | directive | not in the manual |
| `%TIMESLICE` | bytes 13–14 | directive | |
| `%TPMOTION` | byte 7 | directive | |
| `%UNINITVARS` | flag `FA` | directive | not recoverable from V6.x files (flag `00`) |

## Type codes

Observed by declaring one variable of each type: `0x10` INTEGER, `0x11` REAL,
`0x12` BOOLEAN, `0x13` VECTOR, `0x17` SHORT, `0x18` BYTE, `0x1C` CONFIG, `0x1D` FILE,
`0x1F` PATH, `0x1Fnn` STRING[nn], `0x11nn` user type nn, `0xgg01` POSITION,
`0xgg02` XYZWPR, `0xgg06` XYZWPREXT, `0xggN9` JOINTPOSN (gg = group). Bits `0x60` of
the high byte give the number of array dimensions.

A `PATH` (`0x001F`) is followed by three type codes: the standard header type, the
`PATHHEADER` type (0 when absent) and the `NODEDATA` type.

Format 0x22 (V6.40/V6.43) uses other base codes in the high byte: `0x08` for STRING
(`0x1F` later) and `0x10`/`0x18` for user types (`0x11` later). This applies to every
type code, including the three codes that follow a `PATH`.

Size of an array (used to number local variables): arrays are nested, each level
has a 4-byte header, so `ARRAY[d1,d2,...] OF t` = 4 + d1 x size(`ARRAY[d2,...] OF t`)
(observed: `ARRAY[2,3] OF INTEGER` = 36 bytes, `ARRAY[2,2,2] OF INTEGER` = 60).
`STRING[n]` = n + 2 bytes rounded up to an even number.

## P-code

A stack machine. Each source line starts with a line marker `3E llll oooo` (line
number, byte offset of the line in the source). Instruction lengths were established
from the test corpus and checked on every compiled program: all programs split
exactly, with every routine offset, label and line marker on an instruction boundary.

| Opcode | Length | Meaning |
|---|---|---|
| `3F` | 2 + n | string literal: `3F nn …` |
| `2B` | variable | local structured variables: list of type codes ended by `0000` |
| `01` | 3 | `MOVE TO p1`: `01 gggg` (group mask) |
| `02` | 2 | `WITH` clause: value, group, `02 ii` |
| `03` | 1 | `WAIT FOR ...`: start |
| `04` | 1 | end of condition |
| `05` | 3 | group mask after `WITH`: `05 gggg` (not in the corpus, see below) |
| `06` | 1 | `MOVE TO`: destination |
| `07` | 1 | `MOVE ... VIA` |
| `08` | 1 | `MOVE ALONG` |
| `09` | 1 | `NOWAIT` |
| `0A` | 2 | `MOVE NEAR/AWAY/RELATIVE/ABOUT/AXIS`: `0A kk` |
| `0B` | 1 | end of motion statement |
| `0C` | 1 | `MOVE TO pth[i]` (PATH node) |
| `0D` | 1 | `ENABLE CONDITION` |
| `0E` | 1 | `DISABLE CONDITION` |
| `0F` | 2 | `PULSE`: `0F pp` |
| `10` | 1 | `PAUSE` |
| `11` | 1 | `DELAY` |
| `12` | 2 | `WAIT FOR i > 5`: `12 cc` (comparison type) |
| `13` | 2 | condition/action: `13 aa` |
| `14` | 1 | end of `WAIT` |
| `17` | 6 | parameter: `17 ff xxxxxxxx` |
| `18` | 1 | `CONDITION`: start |
| `19` | 2 | `x = DIN[3]`: `19 pp` |
| `1A` | 2 | `DOUT[1] = TRUE`: `1A pp` |
| `1B` | 2 | `WAIT FOR DIN[1]`: `1B pp` |
| `1C` | 6 | `MOVE TO p1`: `1C 01 xxxxxxxx` |
| `1D` | 1 | `ARRAY_LEN` |
| `1E` | 2 | assignment of an array returned by a function: `1E nn` (number of dimensions) |
| `1F` | 2 | `PULSE ... NOWAIT`: `1F pp` |
| `20` | 5 | `ENDFOR` (`TO`) |
| `21` | 6 | read variable: `21 ss xxxxxxxx` |
| `22` | 6 | variable address |
| `23` | 6 | write variable |
| `24` | 3 | `BYNAME`: `24 tttt` |
| `25` | 2 | `WITH $SCAN_TIME` |
| `26` | 2 | end of a call using `BYNAME`: `26 nn` |
| `27` | 1 | call preparation |
| `28` | 1 | `DISCONNECT TIMER` |
| `29` | 1 | swap the two operands (`r = i * r`) |
| `2A` | 2 | `STRING` argument: `2A 01` |
| `2C` | 4 | `ENDFOR`: `2C 00 00 01` |
| `2D` | 6 | read parameter |
| `2E` | 5 | 32-bit constant |
| `2F` | 6 | parameter address (`FOR n`) |
| `30` | 3 | structure copy: `30 nnnn` |
| `31` | 3 | call external routine: `31 nnnn` |
| `32` | 3 | field: `32 oooo` |
| `33` | 1 | indexing |
| `34` | 1 | read through address |
| `35` | 1 | write through address |
| `36` | 3 | read position/vector: `36 tt tt` |
| `37` | 3 | `WRITE` item: `37 tttt` |
| `38` | 3 | `READ` item: `38 tttt` |
| `39` | 1 | `CLOSE FILE` |
| `3A` | 1 | `ABORT` |
| `3B` | 1 | `CANCEL` |
| `3C` | 1 | `PURGE CONDITION` |
| `3D` | 1 | `OPEN FILE` |
| `3E` | 5 | line marker: `3E llll oooo` |
| `40` | 5 | `SELECT`: `40 xxxxxxxx` |
| `41` | 5 | `CASE`: `41 xxxxxxxx` |
| `42` | 1 | end of `CASE` list |
| `43` | 1 | `ELSE` of `SELECT` |
| `44` | 1 | `SELECT` without `ELSE` |
| `45` | 5 | `ENDFOR` (`DOWNTO`) |
| `46` | 1 | `AND` |
| `47` | 1 | `OR` |
| `48` | 1 | `i = NOT j` (integer) |
| `49` | 8 | read position/vector |
| `4A` | 7 | write position/vector |
| `4B` | 8 | read local position |
| `4C` | 7 | write local position |
| `4D` | 1 | `SIGNAL EVENT` |
| `4E` | 1 | `RESUME` |
| `4F` | 1 | `STOP` |
| `50` | 1 | `ABS` (integer) |
| `51` | 1 | integer negation |
| `52` | 1 | `+` |
| `53` | 1 | `-` |
| `54` | 1 | `*` |
| `55` | 1 | `DIV` |
| `56` | 1 | `MOD` |
| `57` | 1 | `=` |
| `58` | 1 | `<>` (integer) |
| `59` | 1 | `<` |
| `5A` | 1 | `<=` |
| `5B` | 1 | `>` |
| `5C` | 1 | `>=` (integer) |
| `5D` | 2 | write vector through address: `5D tt` |
| `5E` | 1 | read string through address |
| `5F` | 1 | `NOT` |
| `60` | 1 | `p1 : p2` |
| `61` | 1 | write string through address |
| `62` | 1 | `CONNECT TIMER` |
| `63` | 3 | `UNINIT`: `63 tttt` |
| `64` | 1 | integer to real |
| `65` | 1 | `HOLD` |
| `66` | 1 | `UNHOLD` |
| `67` | 1 | `ABS` (real) |
| `68` | 1 | real negation |
| `69` | 1 | `+` (real) |
| `6A` | 1 | `-` (real) |
| `6B` | 1 | `*` (real) |
| `6C` | 1 | `/` (real) |
| `6D` | 1 | `=` (real) |
| `6E` | 1 | `<>` (real) |
| `6F` | 1 | `<` (real) |
| `70` | 1 | `<=` (real) |
| `71` | 1 | `>` (real) |
| `72` | 1 | `>=` (real) |
| `73` | 6 | read string |
| `74` | 6 | read local string |
| `75` | 6 | write string |
| `76` | 2 | built-in function: `76 nn` |
| `79` | 5 | jump if false: `79 label` |
| `7A` | 5 | jump: `7A label` |
| `7B` | 1 | routine start |
| `7D` | 1 | `+` (string) |
| `7E` | 5 | position conversion: `7E 01 tt gg tt` |
| `7F` | 4 | `RETURN` / end: `7F np rrrr` |
| `81` | 1 | `CONDITION` |
| `82` | 2 | end of motion clauses: `82 03` |
| `83` | 1 | `=` (string) |
| `84` | 1 | `<>` (string) |
| `85` | 1 | `<` (string) |
| `86` | 1 | `<=` (string) |
| `87` | 1 | `>` (string) |
| `88` | 1 | `>=` (string) |
| `89` | 1 | vector `*` integer |
| `8A` | 1 | vector `*` real |
| `8B` | 1 | integer `*` vector |
| `8C` | 1 | real `*` vector |
| `8D` | 1 | vector `/` integer |
| `8E` | 1 | vector `/` real |
| `91` | 1 | vector `+` |
| `92` | 1 | vector `-` |
| `93` | 1 | cross product `#` |
| `94` | 1 | dot product `@` |
| `95` | 1 | vector `=` |
| `96` | 1 | vector `<>` |
| `97` | 1 | vector negation |
| `98` | 1 | PATH header: `pth.field` |
| `99` | 1 | PATH node: `pth[i]` |
| `9A` | 1 | position: vector |
| `9B` | 1 | constant `*` (`ERROR[*]`) |
| `9C` | 1 | constant 0 / `FALSE` |
| `9D` | 1 | constant 1 / `TRUE` |
| `9E` | 6 | `FOR ... TO` |
| `9F` | 6 | `FOR ... DOWNTO` |
| `A0` | 6 | `FOR` on a parameter |
| `A1` | 6 | `FOR ... DOWNTO` on a parameter |
| `A2` | 6 | write string parameter |
| `A3` | 1 | `CANCEL FILE` |
| `A4` | 3 | read a `CONFIG` field: `A4 bb ww` (see [CONFIG fields](#config-fields)) |
| `A5` | 3 | write a `CONFIG` field: `A5 bb ww` |
| `AA` | 3 | call routine: `AA nnnn` |
| `AB` | 3 | routine as condition action: `AB nnnn` |
| `AC` | 1 | `p1 >=< p2` |
| `AD` | 1 | predefined files |
| `AF` | 3 | `GET_VAR`: `AF tttt` |
| `B0` | 3 | `SET_VAR`: `B0 tttt` |
| `B1` | 1 | read `BYTE` through address |
| `B2` | 1 | write `BYTE` through address |
| `B3` | 1 | read `SHORT` through address |
| `B4` | 1 | write `SHORT` through address |
| `B5` | 1 | `OR` of conditions |

The remaining data tables (I/O port codes, predefined files, built-in function
numbers, position field offsets) are generated by `tests/outils/derive_tables.py`
into `pc2kl/karel_tables.json`, with a report of how each entry was observed.

### Functions returning an array

A function may return an array: the return type is declared `ARRAY OF t` or
`ARRAY[*,*] OF t` (the translator rejects a size, e.g. `ARRAY[6] OF t`), and the routine
table stores the type code without dimensions. The result is assigned with
`value, 22 <destination address>, 1E nn`, where `nn` is the number of dimensions
(`tests/src/langage/t_arrfunc.kl`, `t_arrfunc3.kl`).

### CONFIG fields

A `CONFIG` is a 32-bit word; its fields are bit fields. The address of the `CONFIG`
(a variable, or `pos.config_data` = `32 0020` for an `XYZWPR`/`XYZWPREXT`, `32 0038`
for a `POSITION`) is followed by `A4 bb ww` to read the field or, after the value,
`A5 bb ww` to write it (`bb` = first bit, `ww` = width):

| `bb ww` | Field | Type |
|---|---|---|
| `00 08` | `CFG_TURN_NO1` | INTEGER |
| `08 08` | `CFG_TURN_NO2` | INTEGER |
| `10 08` | `CFG_TURN_NO3` | INTEGER |
| `18 01` | `CFG_FLIP` | BOOLEAN |
| `19 01` | `CFG_LEFT` | BOOLEAN |
| `1A 01` | `CFG_UP` | BOOLEAN |
| `1B 01` | `CFG_FRONT` | BOOLEAN |

Not in the original corpus: first seen in `.pc` files sent by a user (format 0x29), where
the bit/field pairing is unambiguous (`F`/`N` tied to bit 24, `U`/`D` to 26, `T`/`B` to 27,
`L`/`R` to 25, and debug strings naming each field). To be confirmed with
`tests/src/langage/t_config.kl`.

### First field of a PATH in format 0x22

Format 0x22 does not emit the field instruction `32 0000` for a field at offset 0:
`pth[1].j1 = …` (first field of a node) and `pth.hs = …` (first field of the header)
compile without it, so the decoder restores the first field from the declared type.

## Motion clauses and multi-group moves

`WITH $SPEED = 500, $MOTYPE = m MOVE TO p` pushes, for each clause, the value then the
group number (1 unless `$GROUP[g].` is written), followed by `02 ii`. The clause ids
were read from one test program per system variable (`tests/src/langage/w*.kl`); the
translator itself rejects the variables that are not allowed in a `WITH` clause. Ids
1 to 20 follow the order of the motion fields of `$GROUP` and did not change between
V6.40 and V10.13. The value type is read from the `.pc` type table (structure `UPR_T`).

Values of enumerated system types (`MOTYPE_E`, `TERMTYPE_E`, `ORIENT_E`) are printed by
name. The names were taken from the public system variable reference and each value
was confirmed by compiling `w_enum.kl`.

The destination of a multi-group move is a `PATH` node: `22 pth`, index, `1C`, `0C`.

`05 gggg` was found only in a `.pc` sent by a user (a multi-group program compiled
with `%SYSTEM` and `%INVISIBLE`), after the `WITH` clauses. Neither a ROBOGUIDE
`robot.ini` nor any of the directives listed above makes `ktrans` produce it; in
particular, recompiling that program with `%SYSTEM` and `%INVISIBLE` does not. It is
skipped with a warning; the recompiled program is otherwise identical.

## %INCLUDE and CONST

Neither the name of an included file nor the names of constants are stored: constants
are replaced by their value and line markers keep the numbering of the main file. Line
markers of a routine that comes from an included file refer to lines of that file.
