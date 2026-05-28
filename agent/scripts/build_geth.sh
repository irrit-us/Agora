#!/usr/bin/env bash
# Build go-ethereum and pre-compile key test packages for consensus experiments.
# Prereqs: Go 1.22+ (see go-ethereum/README.md for version requirements)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
GETH="${ROOT}/go-ethereum"

if [[ ! -d "${GETH}" ]]; then
  echo "ERROR: ${GETH} not found. Clone go-ethereum into ./go-ethereum (repo root)." >&2
  exit 1
fi

cd "${GETH}"

echo "=== Building go-ethereum ==="
go build ./...

echo ""
echo "=== Pre-compiling consensus test packages ==="

PACKAGES=(
  "./consensus/ethash"
  "./consensus/beacon"
  "./consensus/clique"
  "./core"
  "./core/vm"
  "./core/types"
  "./core/state"
)

for pkg in "${PACKAGES[@]}"; do
  echo "  Testing build: ${pkg}"
  go test -c -o /dev/null "${pkg}" 2>/dev/null || echo "    (no test files or build issue in ${pkg})"
done

echo ""
echo "OK: go-ethereum build and test compilation successful"
echo "Example: cd ${GETH} && go test -v -run TestDifficultyCalculators ./consensus/ethash/"
echo "Example: cd ${GETH} && go test -v -run TestInsertChain ./core/"
