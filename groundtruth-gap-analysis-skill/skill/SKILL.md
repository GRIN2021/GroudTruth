---
name: analyzing-groundtruth-gaps
description: Use when comparing objdump .text instruction addresses against SOK-generated groundtruth protobufs, especially to quantify addresses missing from groundtruth and distinguish real gaps from objdump long-instruction continuation lines, padding, and alignment bytes.
---

# Analyzing Groundtruth Gaps

## Overview

Use this skill to compare a Linux ELF binary's `objdump -d -j .text` output against a SOK `gtBlock.pb` file.

The critical rule is: **only count real objdump instruction lines with mnemonics**. Do not treat objdump continuation lines for long instructions as separate instruction addresses.

## When to Use

Use this when you need to:
- count `.text` instruction addresses not present in groundtruth
- merge missing addresses into contiguous ranges
- classify missing ranges into `padding` vs `outside_gt_coverage`
- explain why missing addresses appear, especially in hand-written assembly or linker/CRT stubs

Do not use this for Windows/PDB workflows.

## Inputs

You need:
- ELF binary path, for example `libcrypto.so.3`
- matching groundtruth protobuf path, for example `libcrypto.gtBlock.pb`
- access to `objdump`
- Python with the generated `blocks_pb2.py` available

## Workflow

1. Read the protobuf and collect:
- groundtruth instruction addresses from `bb.instructions[*].va`
- covered ranges from `[bb.va, bb.va + bb.size - bb.padding)`
- padding ranges from `[bb.va + bb.size - bb.padding, bb.va + bb.size)` when `bb.padding > 0`

2. Run:
```bash
objdump -d -j .text <binary>
```

3. Parse only lines that have both:
- an instruction address
- machine-code bytes
- a non-empty mnemonic/assembly field

4. Compute unseen instruction addresses:
- `objdump_real_instruction_addresses - gt_instruction_addresses`

5. Merge unseen addresses into contiguous ranges using instruction size.

6. Classify each unseen address/range:
- `padding`: falls inside a groundtruth padding range
- `outside_gt_coverage`: falls outside every groundtruth covered range

If you see an `inside_gt_coverage_but_not_gt_inst` bucket, first verify your parser is not accidentally counting objdump continuation lines.

## Root-Cause Heuristics

Typical causes for unseen addresses:
- `.align`, `nop`, linker fill, or function-separator bytes in `.text`
- hand-written assembly that emits raw bytes with directives such as `.byte`, `.long`, `.quad`
- linker/CRT helper code such as `crtstuff.c` symbols
- bytes after an unconditional jump or return that objdump still decodes linearly

Typical non-causes:
- long instruction continuation lines such as:
```asm
cf00a: 48 83 3d ee fe 46 00    cmpq ...
cf011: 00
```
`cf011` is not a new instruction.

Another example:
```asm
d00c1: c7 84 24 40 01 00 00    movl ...
d00c8: 00 00 00 00
```
`d00c8` is continuation bytes, not a real instruction start.

## Script

Run the bundled script:
```bash
python3 scripts/analyze_groundtruth_gap.py \
  --binary /path/to/binary \
  --groundtruth /path/to/gtBlock.pb \
  --blocks-pb2 /path/to/blocks_pb2.py \
  --out-prefix /tmp/analysis
```

Outputs:
- `<out-prefix>.summary.txt`
- `<out-prefix>.summary.json`

## Interpretation

Prioritize these numbers:
- `unseen_instruction_count`
- `unseen_ratio_over_groundtruth`
- `instruction_category_counts`
- `range_category_counts`

If `padding` dominates, the issue is mostly alignment/fill bytes.
If `outside_gt_coverage` dominates, inspect nearby symbols and assembly source for raw-byte directives, linker stubs, cold fragments, and alignment islands.
