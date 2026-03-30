#!/bin/bash
set -Eeuo pipefail

echo "==> Installing dependencies..."
cd /app && npm install
