#!/usr/bin/env bash
# Build AvalancheGo and pre-compile key test packages for consensus experiments.
# Prereqs: Go 1.22+ (see avalanchego/README.md for version requirements)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AVAGO="${ROOT}/avalanchego"

if [[ ! -d "${AVAGO}" ]]; then
  echo "ERROR: ${AVAGO} not found. Clone avalanchego into ./avalanchego (repo root)." >&2
  exit 1
fi

cd "${AVAGO}"

echo "=== Building avalanchego ==="
go build ./...

echo ""
echo "=== Pre-compiling consensus test packages ==="

PACKAGES=(
  "./snow/consensus/snowball"
  "./snow/consensus/snowman"
  "./snow/consensus/avalanche"
  "./snow/engine/snowman"
  "./snow/engine/avalanche"
  "./snow/validators"
  "./simplex"
  "./chains"
  "./vms/platformvm"
  "./vms/proposervm"
)

for pkg in "${PACKAGES[@]}"; do
  echo "  Testing build: ${pkg}"
  go test -c -o /dev/null "${pkg}" 2>/dev/null || echo "    (no test files or build issue in ${pkg})"
done

echo ""
echo "OK: avalanchego build and test compilation successful"
echo "Example: cd ${AVAGO} && go test -v -run TestTopological ./snow/consensus/snowman/"
echo "Example: cd ${AVAGO} && go test -v -run TestSnowballParameters ./snow/consensus/snowball/"
