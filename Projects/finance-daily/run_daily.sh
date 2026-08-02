#!/usr/bin/env bash
# Daily finance pipeline: fetch -> markets -> charts -> PDF -> Telegram
set -euo pipefail
cd "$(dirname "$0")"
python3 fetch_news.py
python3 fetch_markets.py
python3 fetch_indonesia.py
python3 charts.py
# analysis.md must exist (written by the agent before this step in cron)
python3 report.py
python3 send_telegram.py
