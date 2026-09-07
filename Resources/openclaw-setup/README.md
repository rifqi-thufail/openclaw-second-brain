# OpenClaw Setup & Recovery

This folder documents the full OpenClaw + verbose-agent + finance setup so a fresh
install can restore all settings and data from this repo. Daily snapshots live in
`Archives/openclaw-config/<date>/` (secrets redacted) and `Archives/chat-history/<date>/`.

## What gets backed up daily (cron, 22:30 Asia/Kuala_Lumpur)

Runs `scripts/archive_daily.sh`, which:
1. Snapshots the full OpenClaw config (`openclaw.json`) into `Archives/openclaw-config/<date>/`, with secrets redacted (`token`, `secret`, `apikey`, `password` keys and bot-token patterns are scrubbed).
2. Copies each agent's durable persona/rules markdown (`AGENTS.md`, `SOUL.md`, `IDENTITY.md`, `TOOLS.md`, `USER.md`, `HEARTBEAT.md`) from `workspace/` and `workspace-verbose/` into `Archives/openclaw-config/<date>/agent-<name>/`.
3. Exports recent chat transcripts (main + cron + verbose + heartbeat sessions, ~last 50h) from each agent's SQLite store into `Archives/chat-history/<date>/agent__session.md`.
4. `git add -A && git commit && git push origin master`.

Redaction is enforced at write time, so secrets never enter git. The `.env` files
holding real tokens are gitignored and never pushed.

## Fresh install: restore steps

On a new host (user `ratrocious`):

1. Clone this repo to your home:
   `git clone https://github.com/rifqi-thufail/openclaw-second-brain.git ~/.openclaw/workspace`
2. Restore agent personas (copy back the snapshots):
   - `cp ~/.openclaw/workspace/SOUL.md AGENTS.md IDENTITY.md TOOLS.md USER.md HEARTBEAT.md` to the respective new-agent workspace
   - Verbose workspace files are under `Archives/openclaw-config/*/agent-verbose/`
3. Restore config: take the newest `Archives/openclaw-config/<date>/openclaw.json` as a starting template. IMPORTANT: re-add your real channel tokens (telegram bot tokens, etc.) via the gateway or `openclaw` config wizard, since git holds only redacted copies. Recreate `.env` under `Projects/finance-daily/` the same way.
4. Re-authorize GitHub for push (`gh auth login`), then `gh auth setup-git`.
5. Set git author: `git config user.name "Claw"`, `git config user.email "rifqi-thufail@users.noreply.github.com"`.
6. Reinstall cron jobs:
   - Finance daily briefing (see below).
   - Second brain daily archive (see below).

Restore is deliberately git-first so nothing is lost across migrations.

## Finance daily briefing (OpenClaw automation, not the machine cron)

The finance pipeline is NOT run by machine cron on this host. It runs as the OpenClaw
automation job `finance-daily-briefing` (schedule `0 8 * * *` Asia/Kuala_Lumpur), which calls the
agent prompt: cd into `Projects/finance-daily`, run fetch steps + charts, write `analysis.md`,
then `report.py` + `send_telegram.py`. Pipeline order (see `run_daily.sh`):
`fetch_news.py -> fetch_markets.py -> fetch_indonesia.py -> charts.py -> report.py -> send_telegram.py`.

Charts emitted (all in the daily Telegram deliverable):
- `change.png`, `trend.png` (daily, US + ASEAN)
- `weekly_change.png`, `weekly_trend.png` (Indonesia focus, JCI-ASEAN weekly comparison + trend)

Venv python: `Projects/finance-daily/.venv/bin/python` (includes playwright chromium for the ID 5Y CDS fetch).

Data gap notes (verified 2026-09-07):
- Indonesia JCI (`^JKSE`) + peers SG `^STI`, MY `^KLSE`, TH `^SET.BK`, PH `PSEI.PS` resolve via yfinance.
- Vietnam (VNINDEX / ^VNINDEX) is delisted on Yahoo: skips cleanly, never fabricated.
- CDS peer values (SG/MY/TH/PH/VN) are frequently empty from worldgovernmentbonds; ID 10Y + ID 5Y CDS fetch reliably.

## Automation jobs to recreate on a fresh install

```bash
# Daily archive + push (runs archive_daily.sh), 22:30 KL
# schedule: 30 22 * * * Asia/Kuala_Lumpur ; sessionTarget isolated ; delivery none
# message: run `bash ~/.openclaw/workspace/scripts/archive_daily.sh`, reply ARCHIVE_OK/ARCHIVE_FAILED

# Finance daily briefing
# schedule: 0 8 * * * Asia/Kuala_Lumpur (see Projects/finance-daily cron prompt above)
```
