#!/bin/bash
set -Eeuo pipefail

echo "==> Installing dependencies..."
cd /app && npm ci

echo "==> Building React frontend..."
npm run build

echo "==> Setup complete."