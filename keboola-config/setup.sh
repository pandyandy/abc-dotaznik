#!/bin/bash
set -Eeuo pipefail
cd /app && uv sync &
cd /app && npm install && npm run build &
wait
