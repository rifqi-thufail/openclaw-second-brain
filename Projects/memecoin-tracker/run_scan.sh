#!/usr/bin/env bash
# Memecoin tracker scan -> score -> signal -> Telegram. SIGNAL/PAPER ONLY.
set -euo pipefail
cd "$(dirname "$0")"
PY=python3
$PY scripts/scanner.py
$PY scripts/paper_engine.py --summary 2>/dev/null || true
$PY scripts/send_telegram.py
echo "MEMETRACKER_OK"
