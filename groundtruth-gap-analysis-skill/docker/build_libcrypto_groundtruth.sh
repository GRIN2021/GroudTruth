#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK_DIR="${WORK_DIR:-/tmp/groundtruth-gap-analysis}"
OPENSSL_VER="${OPENSSL_VER:-3.4.4}"
OPENSSL_TARBALL="openssl-${OPENSSL_VER}.tar.gz"
OPENSSL_URL="https://github.com/openssl/openssl/releases/download/openssl-${OPENSSL_VER}/${OPENSSL_TARBALL}"

docker_cli() {
  if [[ "${DOCKER_USE_SUDO:-0}" == "1" ]]; then
    sudo docker "$@"
  else
    docker "$@"
  fi
}

mkdir -p "${WORK_DIR}"
cd "${WORK_DIR}"

echo "[1/6] Pull Docker images"
docker_cli pull bin2415/x86_gt:0.1
docker_cli pull bin2415/py_gt

echo "[2/6] Download OpenSSL"
if [[ ! -f "${OPENSSL_TARBALL}" ]]; then
  curl -L --fail --output "${OPENSSL_TARBALL}" "${OPENSSL_URL}"
fi

echo "[3/6] Build OpenSSL in x86_gt"
docker_cli rm -f gt-libcrypto-build >/dev/null 2>&1 || true
docker_cli run -d --name gt-libcrypto-build \
  -v "${WORK_DIR}:/build" \
  -w /build \
  bin2415/x86_gt:0.1 \
  sleep infinity >/dev/null

docker_cli exec gt-libcrypto-build bash -lc "
  set -euo pipefail
  rm -rf openssl-${OPENSSL_VER}
  tar -xf ${OPENSSL_TARBALL}
  cd openssl-${OPENSSL_VER}
  source /gt_x86/gcc64.rc
  export CFLAGS=\"-O2 \$CFLAGS\"
  export CXXFLAGS=\"-O2 \$CXXFLAGS\"
  ./Configure linux-x86_64 shared
  make -j\$(nproc) build_sw
"

echo "[4/6] Prepare py_gt container"
docker_cli rm -f gt-libcrypto-py >/dev/null 2>&1 || true
docker_cli run -d --name gt-libcrypto-py --network host \
  -e HTTP_PROXY="${HTTP_PROXY:-http://127.0.0.1:7890}" \
  -e HTTPS_PROXY="${HTTPS_PROXY:-http://127.0.0.1:7890}" \
  -v "${ROOT_DIR}:/work" \
  -v "${WORK_DIR}:/build" \
  -w /work/extract_gt \
  bin2415/py_gt sleep infinity >/dev/null

echo "[5/6] Install Python dependencies in py_gt"
docker_cli exec gt-libcrypto-py bash -lc "
  set -euo pipefail
  python3 -m pip install protobuf==3.20.3 capstone pyelftools sqlalchemy
"

echo "[6/6] Extract libcrypto groundtruth"
docker_cli exec gt-libcrypto-py bash -lc "
  set -euo pipefail
  cd /build/openssl-${OPENSSL_VER}
  rm -f libcrypto.so.3.gt libcrypto.so.3.gt.gz /build/libcrypto.gtBlock.pb
  objcopy --dump-section .rand=libcrypto.so.3.gt.gz libcrypto.so.3
  gzip -d -f libcrypto.so.3.gt.gz
  python3 /work/extract_gt/extractBB.py -b libcrypto.so.3 -m libcrypto.so.3.gt -o /build/libcrypto.gtBlock.pb
"

echo "Artifacts ready under ${WORK_DIR}"
