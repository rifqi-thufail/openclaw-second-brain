# Memecoin Tracker

Solana memecoin scanner and paper-trading assistant. **SIGNAL + PAPER ONLY. No wallet,
no keys, no real funds.**

Own Telegram bot: `@ratrociousmemetracker_bot`.
Own agent: `memetracker` (workspace `~/.openclaw/workspace-memetracker`).

## Mechanism (Rifqi's spec)

```
SCANNER -> pullback 15-40% -> volume/flow confirm -> SCORE -> >=7/10 ? ENTRY : SKIP
ENTRY -> SL / TP1 (1.5R) / TP2 (2.5R) -> TSL runner
```

Filters: liquidity > $15k, volume expanding (not a one-candle spike), prior runner with a
15-40% pullback, structure intact, buy flow returning, no dev/top-wallet distribution, no
extreme holder concentration.

Risk per trade: $1-2. Daily guard: target +$5-10, max loss -$5, then stop for the day.
Anti-overtrade: max 5 trades/day. Review expectancy only after 30-50 trades.

## Scripts

- `scripts/scanner.py` — DexScreener public API (no key). Writes `state/signals.json`,
  `data/scan_<date>.json`, `output/signals-<date>.md`.
- `scripts/paper_engine.py` — risk rules + paper trade log (`state/paper_<date>.json`).
- `scripts/send_telegram.py` — sends signals to the bot. Token from `MEMECOIN_BOT_TOKEN`
  env or project `.env` (gitignored).
- `run_scan.sh` — scan -> summary -> send. Prints `MEMETRACKER_OK`.

## Run manually

```bash
cd ~/.openclaw/workspace/Projects/memecoin-tracker
./run_scan.sh
```

## Notes / limits

- Holder concentration and dev-wallet distribution are NOT exposed by the public
  DexScreener API. The scorecard uses honest proxies (e.g. no sharp 5m dump) and marks
  the holder check as pass-by-default until a richer data source is added.
- Pullback depth is inferred from windowed % changes (DexScreener has no free OHLC
  history), so treat it as an estimate.
- This is not financial advice.
