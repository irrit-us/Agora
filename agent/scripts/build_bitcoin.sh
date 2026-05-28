#!/usr/bin/env bash
# Build Bitcoin Core binaries for consensus experiments.
#   - bitcoind          (needed by functional tests in test/functional/)
#   - bitcoin-cli       (needed by functional tests for RPC interaction)
#   - test_bitcoin      (C++ Boost unit tests in src/test/)
#
# Prereqs (macOS): see bitcoin/doc/build-osx.md — e.g. brew install cmake boost pkgconf libevent capnp
# Prereqs (Linux): see bitcoin/doc/build-unix.md
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BTC="${ROOT}/bitcoin"

if [[ ! -d "${BTC}" ]]; then
  echo "ERROR: ${BTC} not found. Clone Bitcoin Core into ./bitcoin (repo root)." >&2
  exit 1
fi

cd "${BTC}"

cmake -B build \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DENABLE_WALLET=ON \
  -DENABLE_IPC=OFF \
  -DBUILD_GUI=OFF \
  -DBUILD_BENCH=OFF

JOBS="${JOBS:-}"
if [[ -z "${JOBS}" ]]; then
  if command -v nproc >/dev/null 2>&1; then
    JOBS="$(nproc)"
  elif command -v sysctl >/dev/null 2>&1; then
    JOBS="$(sysctl -n hw.ncpu)"
  else
    JOBS=4
  fi
fi

cmake --build build -j"${JOBS}" --target bitcoind bitcoin-cli test_bitcoin

echo ""
echo "=== Build Results ==="

FAIL=0
for target in bitcoind bitcoin-cli test_bitcoin; do
  BIN="${BTC}/build/bin/${target}"
  if [[ -x "${BIN}" ]]; then
    echo "OK: ${BIN}"
  else
    echo "MISSING: ${BIN}" >&2
    FAIL=1
  fi
done

if [[ "${FAIL}" -ne 0 ]]; then
  echo "WARNING: some binaries were not found." >&2
  exit 1
fi

echo ""
echo "Unit tests:      ./build/bin/test_bitcoin --run_test=pow_tests/get_next_work"
echo "Functional test: python3 test/functional/feature_block.py"
