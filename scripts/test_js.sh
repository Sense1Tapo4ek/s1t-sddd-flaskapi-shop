#!/usr/bin/env bash
# Run vanilla-JS unit tests via Node's built-in node:test runner.
# Files live under tests/static/js/ and follow the *.test.js convention.

set -euo pipefail
cd "$(dirname "$0")/.."

mapfile -t files < <(find tests/static/js -name '*.test.js' -print | sort)
if [[ ${#files[@]} -eq 0 ]]; then
  echo "no JS test files found"
  exit 0
fi

exec node --test "${files[@]}"
