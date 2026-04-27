# GroudTruth

This repository is now a minimal Docker-based reproduction package for:

1. building `openssl-3.4.4` with the SOK image `bin2415/x86_gt:0.1`
2. extracting `libcrypto.so.3` groundtruth with `bin2415/py_gt`
3. analyzing `.text` instruction addresses that appear in `objdump` but not in `gtBlock.pb`

## Repository Layout

```text
.
|-- ccr
|-- extract_gt
|-- protobuf_def
|-- groundtruth-gap-analysis-skill
|-- requirements.txt
`-- README.md
```

The retained directories are the minimum needed by the current workflow:

- `extract_gt/`
  Groundtruth extraction entrypoint used by the Docker reproduction scripts.
- `ccr/`
  Python modules imported by `extract_gt/extractBB.py`.
- `protobuf_def/`
  Generated protobuf definitions used by both extraction and gap analysis.
- `groundtruth-gap-analysis-skill/`
  The Docker reproduction scripts, reusable skill, and the validated `libcrypto.so.3` analysis artifacts.

## Quick Start

Run from the repository root:

```bash
DOCKER_USE_SUDO=1 bash groundtruth-gap-analysis-skill/docker/build_libcrypto_groundtruth.sh
DOCKER_USE_SUDO=1 bash groundtruth-gap-analysis-skill/docker/analyze_libcrypto_gap.sh
```

If your user can access Docker directly, omit `DOCKER_USE_SUDO=1`.

Artifacts are written to:

```text
/tmp/groundtruth-gap-analysis/
```

Important outputs:

- `/tmp/groundtruth-gap-analysis/openssl-3.4.4/libcrypto.so.3`
- `/tmp/groundtruth-gap-analysis/libcrypto.gtBlock.pb`
- `/tmp/groundtruth-gap-analysis/libcrypto-gap.summary.txt`
- `/tmp/groundtruth-gap-analysis/libcrypto-gap.summary.json`

## Verification

```bash
test -f /tmp/groundtruth-gap-analysis/libcrypto.gtBlock.pb
test -f /tmp/groundtruth-gap-analysis/libcrypto-gap.summary.txt
sed -n '1,40p' /tmp/groundtruth-gap-analysis/libcrypto-gap.summary.txt
```

Expected key values for the validated sample:

- `unseen_instruction_count = 36614`
- `unseen_ratio_over_groundtruth = 0.054590481927`
- `instruction_category_counts.outside_gt_coverage = 35261`
- `instruction_category_counts.padding = 1353`

## Analysis Rule

The corrected gap-analysis rule is:

1. Disassemble `.text` with `objdump -d -j .text`.
2. Count only lines that have a real mnemonic.
3. Ignore `objdump` continuation lines for long instructions.
4. Compare real instruction start addresses against `bb.instructions[*].va` from `gtBlock.pb`.
5. Merge unseen instruction addresses into contiguous ranges.
6. Classify unseen ranges as:
   - `padding`
   - `outside_gt_coverage`

Example of a false instruction address that must be ignored:

```asm
cf00a: 48 83 3d ee fe 46 00    cmpq   ...
cf011: 00

d00c1: c7 84 24 40 01 00 00    movl   ...
d00c8: 00 00 00 00
```

`cf011` and `d00c8` are continuation bytes from the previous instruction, not new instruction starts.

## More Detail

See:

- `groundtruth-gap-analysis-skill/README.md`
- `groundtruth-gap-analysis-skill/skill/SKILL.md`
