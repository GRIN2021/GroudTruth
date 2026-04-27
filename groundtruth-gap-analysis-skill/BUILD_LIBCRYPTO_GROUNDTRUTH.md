## How `openssl-3.4.4` Becomes `libcrypto` Groundtruth

This document records the exact workflow used in this repository to build `openssl-3.4.4`, extract `libcrypto.so.3` groundtruth, and analyze the gap against `objdump`.

### 1. Pull Docker Images

The workflow uses the upstream images from the original project README:

```bash
docker pull bin2415/x86_gt:0.1
docker pull bin2415/py_gt
```

`bin2415/x86_gt:0.1` contains the modified SOK x86 toolchain.

`bin2415/py_gt` is used to run the Python groundtruth extraction scripts.

### 2. Download OpenSSL 3.4.4

The source tarball is fetched from the official OpenSSL release page:

```bash
curl -L --fail \
  -o openssl-3.4.4.tar.gz \
  https://github.com/openssl/openssl/releases/download/openssl-3.4.4/openssl-3.4.4.tar.gz
```

### 3. Build `libcrypto.so.3` Inside `x86_gt`

Inside the `bin2415/x86_gt:0.1` container:

```bash
tar -xf openssl-3.4.4.tar.gz
cd openssl-3.4.4
source /gt_x86/gcc64.rc
export CFLAGS="-O2 $CFLAGS"
export CXXFLAGS="-O2 $CXXFLAGS"
./Configure linux-x86_64 shared
make -j$(nproc) build_sw
```

Important points:

- `source /gt_x86/gcc64.rc` switches the build to the modified SOK gcc/binutils/glibc toolchain
- the final link step writes ShuffleInfo into the `.rand` section of generated binaries and libraries
- the target artifact for this workflow is:

```text
openssl-3.4.4/libcrypto.so.3
```

### 4. Dump the `.rand` Section

Inside the `bin2415/py_gt` container:

```bash
cd /build/openssl-3.4.4
objcopy --dump-section .rand=libcrypto.so.3.gt.gz libcrypto.so.3
gzip -d -f libcrypto.so.3.gt.gz
```

This produces:

```text
libcrypto.so.3.gt
```

### 5. Convert `.rand` Metadata Into `gtBlock.pb`

Still inside `bin2415/py_gt`:

```bash
python3 /work/extract_gt/extractBB.py \
  -b libcrypto.so.3 \
  -m libcrypto.so.3.gt \
  -o /build/libcrypto.gtBlock.pb
```

This generates the final groundtruth protobuf:

```text
libcrypto.gtBlock.pb
```

### 6. Generate the `.text` Disassembly

The disassembly used for comparison is:

```bash
objdump -d -j .text libcrypto.so.3 > libcrypto.text.objdump.txt
```

### 7. Compare `objdump` Against Groundtruth

The comparison is performed by:

```bash
python3 groundtruth-gap-analysis-skill/skill/scripts/analyze_groundtruth_gap.py \
  --binary /path/to/libcrypto.so.3 \
  --groundtruth /path/to/libcrypto.gtBlock.pb \
  --blocks-pb2 /path/to/protobuf_def/blocks_pb2.py \
  --out-prefix /tmp/libcrypto-gap
```

The corrected comparison rule is:

1. only count `objdump` lines that have a real mnemonic
2. ignore long-instruction continuation lines
3. compare real instruction start addresses against `bb.instructions[*].va`
4. merge unseen addresses into contiguous ranges
5. classify unseen ranges into `padding` and `outside_gt_coverage`

### 8. Final Artifacts Committed In This Repository

Committed artifacts are under:

```text
groundtruth-gap-analysis-skill/results/libcrypto-artifacts/
```

Files:

- `libcrypto.so.3`
- `libcrypto.gtBlock.pb`
- `libcrypto.text.objdump.txt`

The validated summary files remain under:

```text
groundtruth-gap-analysis-skill/results/
```
