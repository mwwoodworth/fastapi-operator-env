#!/usr/bin/env bash
set -euo pipefail

if [ ! -f openapi.json ]; then
  echo "openapi.json not found. Run: curl http://localhost:10000/openapi.json -o openapi.json" >&2
  exit 1
fi

npx openapi-typescript-codegen \
  --input openapi.json \
  --output sdk \
  --useOptions \
  --exportSchemas
