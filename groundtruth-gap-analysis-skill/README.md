## Groundtruth Gap Analysis

This directory contains a minimal Docker-based reproduction package for:

1. building `openssl-3.4.4` with the SOK `bin2415/x86_gt:0.1` image
2. extracting `libcrypto.so.3` groundtruth with `bin2415/py_gt`
3. analyzing instruction addresses that appear in `objdump -d -j .text` but not in the generated `gtBlock.pb`

### Layout

- `docker/build_libcrypto_groundtruth.sh`
  Pulls the required images, builds OpenSSL with the SOK toolchain, and extracts `libcrypto.gtBlock.pb`.
- `docker/analyze_libcrypto_gap.sh`
  Runs the corrected gap-analysis script inside Docker.
- `BUILD_LIBCRYPTO_GROUNDTRUTH.md`
  Step-by-step explanation of how `openssl-3.4.4` is built into `libcrypto.so.3` groundtruth.
- `skill/SKILL.md`
  The reusable skill instructions.
- `skill/scripts/analyze_groundtruth_gap.py`
  The executable analysis script.
- `results/libcrypto_objdump_unseen_ranges_analysis_v2.txt`
  Human-readable final summary for this session.
- `results/libcrypto_objdump_unseen_ranges_analysis_v2.json`
  Full structured result for this session.
- `results/libcrypto-artifacts/`
  Committed build outputs and disassembly:
  - `libcrypto.so.3`
  - `libcrypto.gtBlock.pb`
  - `libcrypto.text.objdump.txt`

### Docker Reproduction

Run from the repository root:

```bash
DOCKER_USE_SUDO=1 bash groundtruth-gap-analysis-skill/docker/build_libcrypto_groundtruth.sh
DOCKER_USE_SUDO=1 bash groundtruth-gap-analysis-skill/docker/analyze_libcrypto_gap.sh
```

If your user can access Docker directly, omit `DOCKER_USE_SUDO=1`.

The scripts write artifacts under:

```text
/tmp/groundtruth-gap-analysis/
```

Important outputs:

- `/tmp/groundtruth-gap-analysis/openssl-3.4.4/libcrypto.so.3`
- `/tmp/groundtruth-gap-analysis/libcrypto.gtBlock.pb`
- `/tmp/groundtruth-gap-analysis/libcrypto-gap.summary.txt`
- `/tmp/groundtruth-gap-analysis/libcrypto-gap.summary.json`

### Test / Verification

After the Docker scripts finish, verify with:

```bash
test -f /tmp/groundtruth-gap-analysis/libcrypto.gtBlock.pb
test -f /tmp/groundtruth-gap-analysis/libcrypto-gap.summary.txt
sed -n '1,40p' /tmp/groundtruth-gap-analysis/libcrypto-gap.summary.txt
```

The expected result for this session is:

- `unseen_instruction_count = 36614`
- `unseen_ratio_over_groundtruth = 0.054590481927`
- `instruction_category_counts.outside_gt_coverage = 35261`
- `instruction_category_counts.padding = 1353`

### Analysis Rule

The corrected rule is:

1. Disassemble `.text` with `objdump -d -j .text`.
2. Count only lines that have a real mnemonic.
3. Ignore `objdump` continuation lines for long instructions.
4. Compare real instruction start addresses against `bb.instructions[*].va` from `gtBlock.pb`.
5. Merge unseen instruction addresses into contiguous ranges.
6. Classify unseen ranges as:
   - `padding`
   - `outside_gt_coverage`

### Important Correction

An earlier attempt incorrectly counted `objdump` continuation lines as new instructions. Typical false examples were addresses like:

```asm
cf00a: 48 83 3d ee fe 46 00    cmpq   ...
cf011: 00

d00c1: c7 84 24 40 01 00 00    movl   ...
d00c8: 00 00 00 00
```

`cf011` and `d00c8` are continuation bytes from the previous instruction and must not be counted as new instruction addresses.

### Main Root Causes

Most unseen addresses came from:

- alignment and fill bytes in `.text`
- linker or CRT helper stubs
- hand-written assembly emitting raw bytes or alignment directives such as `.align`, `.byte`, `.long`
- bytes after unconditional control-flow transfers that `objdump` still decodes linearly
