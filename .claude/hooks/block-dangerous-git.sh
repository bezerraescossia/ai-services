#!/bin/bash

INPUT=$(cat)
COMMAND=$(python3 -c 'import json, sys; print(json.load(sys.stdin).get("tool_input", {}).get("command", ""))' <<< "$INPUT")

DANGEROUS_PATTERNS=(
  "push --force"
  "push -f"
  "reset --hard"
  "clean -fd"
  "clean -f"
  "branch -D"
  "checkout \."
  "restore \."
)

for pattern in "${DANGEROUS_PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -qE "$pattern"; then
    echo "BLOCKED: '$COMMAND' matches dangerous pattern '$pattern'. The user has prevented you from doing this." >&2
    exit 2
  fi
done

exit 0
