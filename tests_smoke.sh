#!/usr/bin/env bash
# Smoke tests for forgeflow. Runs against a throwaway fixture directory.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FORGE="$ROOT/forge.py"
PY="${PYTHON:-python3}"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

fail() { echo "FAIL: $*" >&2; exit 1; }

cat > pipeline.yaml <<'YAML'
steps:
  - name: first step
    run: echo alpha
  - name: second step
    run: echo beta
YAML

# --version
version="$("$PY" "$FORGE" --version)"
[ "$version" = "0.1.0" ] || fail "version was '$version'"

# dry run: prints WOULD-RUN, executes nothing, records nothing
dry="$("$PY" "$FORGE" run pipeline.yaml --dry)"
echo "$dry"
[ "$dry" = "$(printf 'WOULD-RUN first step\nWOULD-RUN second step')" ] \
  || fail "unexpected dry output"
[ ! -f runs.json ] || fail "dry run should not write runs.json"

# real run: STEP-OK per step plus command output
real="$("$PY" "$FORGE" run pipeline.yaml)"
echo "$real"
echo "$real" | grep -q "STEP-OK first step" || fail "missing STEP-OK first step"
echo "$real" | grep -q "STEP-OK second step" || fail "missing STEP-OK second step"
[ -f runs.json ] || fail "real run should write runs.json"

# runs list
listed="$("$PY" "$FORGE" runs list)"
echo "$listed"
echo "$listed" | grep -q "pipeline.yaml" || fail "runs list missing pipeline"

# runs show existing id -> 0
"$PY" "$FORGE" runs show 1 >/dev/null || fail "runs show 1 should succeed"

# runs show bad id -> exit 2
set +e
"$PY" "$FORGE" runs show 424242 >/dev/null 2>&1
code=$?
set -e
[ "$code" -eq 2 ] || fail "bad id exit was $code, expected 2"

echo "ALL SMOKE TESTS PASSED"
