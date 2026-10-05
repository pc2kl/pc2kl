# The KAREL `.pc` format (as observed)

Everything below was established by compiling the test programs in `tests/src`
(written from the KAREL reference manual) with a licensed translator and
comparing each source line with the bytes it produced. It describes observed
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

1. `u16` format id, observed: 0x22 (V6.40/V6.43), 0x24 (V7.20), 0x25 (V7.30), 0x26 (V7.40–V7.70),
   0x27 (V8.10–V8.33), 0x28 (V8.36), 0x29 (V9.10–V9.40), 0x2A (V10.10/V10.13)
2. `u16` p-code size
3. program name, `%COMMENT` text (NUL-terminated)
4. attributes (`%STACKSIZE`, `%PRIORITY`, `%LOCKGROUP`, …): 20 bytes (19 in format 0x22)
5. p-code
6. padding up to `FF`
7. labels: `u16` count + `u32` offsets
8. modules: `u16` count + NUL-terminated names
9. user types: `u16` count + (`u16` length + record)
10. variables: `u16` count + (attribute, name, storage flag, type)
11. used-variable map, routine table (name, module, offset, return type, parameter types)
12. 3 trailing bytes: a `u16` whose meaning is not known, then `0A`. It depends on the
    source and not only on the p-code: `t_misc.kl`, which has two `USING ... ENDUSING`
    blocks, gives 20 more than its decompiled source (identical p-code, `USING` leaves
    no trace); probably a size estimate made by the translator

Storage flag of a variable: `00` normal, `FD` `IN CMOS`, `02` `IN SHADOW`, `FA` every
variable of a program compiled with `%UNINITVARS` (V7.20 and later; V6.40/V6.43 store `00`).

A function may return an array: the return type is declared `ARRAY OF t` or
`ARRAY[*,*] OF t` (the translator rejects a size, e.g. `ARRAY[6] OF t`), and the routine
table stores the type code without dimensions. The result is assigned with
`value, 22 <destination address>, 1E nn`, where `nn` is the number of dimensions
(`tests/src/langage/t_arrfunc.kl`, `t_arrfunc3.kl`).

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
type code, including the three codes that follow a `PATH`. The same format does not
emit the field instruction `32 0000` for a field at offset 0: `pth[1].j1 = …` (first
field of a node) and `pth.hs = …` (first field of the header) compile without it, so
the decoder restores the first field from the declared type.

Size of an array (used to number local variables): arrays are nested, each level
has a 4-byte header, so `ARRAY[d1,d2,...] OF t` = 4 + d1 x size(`ARRAY[d2,...] OF t`)
(observed: `ARRAY[2,3] OF INTEGER` = 36 bytes, `ARRAY[2,2,2] OF INTEGER` = 60).
`STRING[n]` = n + 2 bytes rounded up to an even number.

## P-code

A stack machine. Each source line starts with a line marker
`3E llll oooo` (line number, byte offset of the line in the source). Instruction
lengths, established from the test corpus and checked on every compiled program
(all programs split exactly, with every routine offset, label and line marker on an
instruction boundary):

| Opcode | Length | Observed in (analyst notes, French) |
|---|---|---|
| `3F` | 2 + n | string literal `3f nn …` |
| `2B` | variable | local structured variables, list of type codes ended by `0000` |
| `01` | 3 | MOVE TO p1 : 01 gggg (masque de groupes) |
| `02` | 2 | clause WITH : valeur, groupe, 02 ii |
| `03` | 1 | WAIT FOR ... : début |
| `04` | 1 | fin de condition |
| `05` | 3 | masque de groupes après WITH : 05 gggg (hors corpus, voir plus bas) |
| `06` | 1 | MOVE TO : destination |
| `07` | 1 | MOVE ... VIA |
| `08` | 1 | MOVE ALONG |
| `09` | 1 | NOWAIT |
| `0A` | 2 | MOVE NEAR/AWAY/RELATIVE/ABOUT/AXIS : 0a kk |
| `0B` | 1 | fin de mouvement |
| `0C` | 1 | MOVE TO pth[i] (noeud de PATH) |
| `0D` | 1 | ENABLE CONDITION |
| `0E` | 1 | DISABLE CONDITION |
| `0F` | 2 | PULSE : 0f pp |
| `10` | 1 | PAUSE |
| `11` | 1 | DELAY |
| `12` | 2 | WAIT FOR i > 5 : 12 cc (type de comparaison) |
| `13` | 2 | condition/action : 13 aa |
| `14` | 1 | fin WAIT |
| `17` | 6 | paramètre : 17 ff xxxxxxxx |
| `18` | 1 | CONDITION : début |
| `19` | 2 | x = DIN[3] : 19 pp |
| `1A` | 2 | DOUT[1] = TRUE : 1a pp |
| `1B` | 2 | WAIT FOR DIN[1] : 1b pp |
| `1C` | 6 | MOVE TO p1 : 1c 01 xxxxxxxx |
| `1D` | 1 | ARRAY_LEN |
| `1E` | 2 | affectation d'un tableau renvoyé par une fonction : 1e nn (nombre de dimensions) |
| `1F` | 2 | PULSE ... NOWAIT : 1f pp |
| `20` | 5 | ENDFOR (TO) |
| `21` | 6 | lecture variable : 21 ss xxxxxxxx |
| `22` | 6 | adresse variable |
| `23` | 6 | écriture variable |
| `24` | 3 | BYNAME : 24 tttt |
| `25` | 2 | WITH $SCAN_TIME |
| `26` | 2 | fin d'appel avec BYNAME : 26 nn |
| `27` | 1 | préparation d'appel |
| `28` | 1 | DISCONNECT TIMER |
| `29` | 1 | échange des deux opérandes (r = i * r) |
| `2A` | 2 | argument STRING : 2a 01 |
| `2C` | 4 | ENDFOR : 2c 00 00 01 |
| `2D` | 6 | lecture paramètre |
| `2E` | 5 | constante 32 bits |
| `2F` | 6 | adresse paramètre (FOR n) |
| `30` | 3 | copie de structure : 30 nnnn |
| `31` | 3 | appel routine externe : 31 nnnn |
| `32` | 3 | champ : 32 oooo |
| `33` | 1 | indexation |
| `34` | 1 | lecture via adresse |
| `35` | 1 | écriture via adresse |
| `36` | 3 | lecture position/vecteur : 36 tt tt |
| `37` | 3 | WRITE élément : 37 tttt |
| `38` | 3 | READ élément : 38 tttt |
| `39` | 1 | CLOSE FILE |
| `3A` | 1 | ABORT |
| `3B` | 1 | CANCEL |
| `3C` | 1 | PURGE CONDITION |
| `3D` | 1 | OPEN FILE |
| `3E` | 5 | marqueur de ligne : 3e llll oooo |
| `40` | 5 | SELECT : 40 xxxxxxxx |
| `41` | 5 | CASE : 41 xxxxxxxx |
| `42` | 1 | fin des CASE |
| `43` | 1 | ELSE de SELECT |
| `44` | 1 | SELECT sans ELSE |
| `45` | 5 | ENDFOR (DOWNTO) |
| `46` | 1 | AND |
| `47` | 1 | OR |
| `48` | 1 | i = NOT j (entier) |
| `49` | 8 | lecture position/vecteur |
| `4A` | 7 | écriture position/vecteur |
| `4B` | 8 | lecture position locale |
| `4C` | 7 | écriture position locale |
| `4D` | 1 | SIGNAL EVENT |
| `4E` | 1 | RESUME |
| `4F` | 1 | STOP |
| `50` | 1 | ABS entier |
| `51` | 1 | négation entière |
| `52` | 1 | + |
| `53` | 1 | - |
| `54` | 1 | * |
| `55` | 1 | DIV |
| `56` | 1 | MOD |
| `57` | 1 | = |
| `58` | 1 | <> entier |
| `59` | 1 | < |
| `5A` | 1 | <= |
| `5B` | 1 | > |
| `5C` | 1 | >= entier |
| `5D` | 2 | écriture vecteur via adresse : 5d tt |
| `5E` | 1 | lecture chaîne via adresse |
| `5F` | 1 | NOT |
| `60` | 1 | p1 : p2 |
| `61` | 1 | écriture chaîne via adresse |
| `62` | 1 | CONNECT TIMER |
| `63` | 3 | UNINIT : 63 tttt |
| `64` | 1 | entier -> réel |
| `65` | 1 | HOLD |
| `66` | 1 | UNHOLD |
| `67` | 1 | ABS réel |
| `68` | 1 | négation réelle |
| `69` | 1 | + réel |
| `6A` | 1 | - réel |
| `6B` | 1 | * réel |
| `6C` | 1 | / réel |
| `6D` | 1 | = réel |
| `6E` | 1 | <> réel |
| `6F` | 1 | < réel |
| `70` | 1 | <= réel |
| `71` | 1 | > réel |
| `72` | 1 | >= réel |
| `73` | 6 | lecture chaîne |
| `74` | 6 | lecture chaîne locale |
| `75` | 6 | écriture chaîne |
| `76` | 2 | fonction intégrée : 76 nn |
| `79` | 5 | saut si faux : 79 label |
| `7A` | 5 | saut : 7a label |
| `7B` | 1 | début de routine |
| `7D` | 1 | + chaîne |
| `7E` | 5 | conversion de position : 7e 01 tt gg tt |
| `7F` | 4 | RETURN / fin : 7f np rrrr |
| `81` | 1 | CONDITION |
| `82` | 2 | fin de clauses de mouvement : 82 03 |
| `83` | 1 | = chaîne |
| `84` | 1 | <> chaîne |
| `85` | 1 | < chaîne |
| `86` | 1 | <= chaîne |
| `87` | 1 | > chaîne |
| `88` | 1 | >= chaîne |
| `89` | 1 | vecteur * entier |
| `8A` | 1 | vecteur * réel |
| `8B` | 1 | entier * vecteur |
| `8C` | 1 | réel * vecteur |
| `8D` | 1 | vecteur / entier |
| `8E` | 1 | vecteur / réel |
| `91` | 1 | vecteur + |
| `92` | 1 | vecteur - |
| `93` | 1 | produit vectoriel # |
| `94` | 1 | produit scalaire @ |
| `95` | 1 | vecteur = |
| `96` | 1 | vecteur <> |
| `97` | 1 | vecteur négation |
| `98` | 1 | en-tête de PATH : pth.champ |
| `99` | 1 | noeud de PATH : pth[i] |
| `9A` | 1 | position : vecteur |
| `9B` | 1 | constante * (ERROR[*]) |
| `9C` | 1 | constante 0 / FALSE |
| `9D` | 1 | constante 1 / TRUE |
| `9E` | 6 | FOR ... TO |
| `9F` | 6 | FOR ... DOWNTO |
| `A0` | 6 | FOR paramètre |
| `A1` | 6 | FOR paramètre DOWNTO |
| `A2` | 6 | écriture chaîne paramètre |
| `A3` | 1 | CANCEL FILE |
| `AA` | 3 | appel routine : aa nnnn |
| `AB` | 3 | action routine : ab nnnn |
| `AC` | 1 | p1 >=< p2 |
| `AD` | 1 | fichiers prédéfinis |
| `AF` | 3 | GET_VAR : af tttt |
| `B0` | 3 | SET_VAR : b0 tttt |
| `B1` | 1 | lecture BYTE via adresse |
| `B2` | 1 | écriture BYTE via adresse |
| `B3` | 1 | lecture SHORT via adresse |
| `B4` | 1 | écriture SHORT via adresse |
| `B5` | 1 | OR de conditions |

The remaining data tables (I/O port codes, predefined files, built-in function
numbers, position field offsets) are generated by `tests/outils/derive_tables.py`
into `pc2kl/karel_tables.json`, with a report of how each entry was observed.

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

`05 gggg` was found only in a `.pc` sent by a user (a multi-group program with an
unknown header attribute, byte 1 = 1), after the `WITH` clauses. No directive tested
(`%SYSTEM`, `%DEFGROUP`, `%DELAY`, `%CRTDEVICE`, `%CMOSVARS`, `%SHADOWVARS`,
`%UNINITVARS`, `%TPMOTION`, `%LOCKGROUP`) nor a ROBOGUIDE `robot.ini` makes `ktrans`
produce it. It is skipped with a warning; the recompiled program is otherwise identical.

## %INCLUDE and CONST

Neither the name of an included file nor the names of constants are stored: constants
are replaced by their value and line markers keep the numbering of the main file. Line
markers of a routine that comes from an included file refer to lines of that file.
