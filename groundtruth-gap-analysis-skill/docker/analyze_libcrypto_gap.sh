#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK_DIR="${WORK_DIR:-/tmp/groundtruth-gap-analysis}"

docker_cli() {
  if [[ "${DOCKER_USE_SUDO:-0}" == "1" ]]; then
    sudo docker "$@"
  else
    docker "$@"
  fi
}

docker_cli pull bin2415/py_gt >/dev/null
docker_cli rm -f gt-gap-analysis >/dev/null 2>&1 || true
docker_cli run -d --name gt-gap-analysis --network host \
  -e HTTP_PROXY="${HTTP_PROXY:-http://127.0.0.1:7890}" \
  -e HTTPS_PROXY="${HTTPS_PROXY:-http://127.0.0.1:7890}" \
  -v "${ROOT_DIR}:/work" \
  -v "${WORK_DIR}:/build" \
  -w /work \
  bin2415/py_gt sleep infinity >/dev/null

docker_cli exec gt-gap-analysis bash -lc "
  set -euo pipefail
  python3 -m pip install --disable-pip-version-check protobuf==3.20.3 >/dev/null
  python3 /work/groundtruth-gap-analysis-skill/skill/scripts/analyze_groundtruth_gap.py \
    --binary /build/openssl-3.4.4/libcrypto.so.3 \
    --groundtruth /build/libcrypto.gtBlock.pb \
    --blocks-pb2 /work/protobuf_def/blocks_pb2.py \
    --out-prefix /build/libcrypto-gap
"

echo "Analysis results:"
echo "  ${WORK_DIR}/libcrypto-gap.summary.txt"
echo "  ${WORK_DIR}/libcrypto-gap.summary.json"
