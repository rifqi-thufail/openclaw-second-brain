# Finance Daily Bot

Daily 08:00 GMT+8 briefing: US + ASEAN equities, equity research PDF, delivered via Telegram bot.

## Pipeline (run_daily.sh)

1. `fetch_news.py` - 12 RSS feeds (CNBC, WSJ, FT, MarketWatch, Yahoo, Straits Times, Inquirer, VnExpress, Edge SG, CNBC ID)
2. `fetch_markets.py` - 8 indices via yfinance (S&P, Nasdaq, Dow, Nikkei, HSI, STI, KLCI, JCI)
3. `fetch_indonesia.py` - ID 10Y govt bond yield (Trading Economics) + 5Y CDS (World Government Bonds via headless chromium)
4. `charts.py` - JPM/GS style charts, analogous palette, SPY (amber) + JCI (red) highlighted
5. `report.py` - 2-page equity research PDF: exec summary, market snapshot, Indonesia Focus (JCI/yield/CDS), numbered citations, references
6. `send_telegram.py` - message + 2 charts + PDF to bot

## Config

- `feeds.json` - RSS feed list
- `.env` - TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (gitignored)
- `analysis.md` - written by the agent each run, parsed by report.py

## Data gaps

- TH/PH/VN indices: tickers delisted on Yahoo
- CDS peers (MY/TH/PH/VN/SG): not in WGB map data
- Source URLs in analysis.md are illustrative in sample; live runs use real article links
