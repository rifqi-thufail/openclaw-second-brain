#!/usr/bin/env python3
"""Fetch index data via yfinance. Output: data/markets_<date>.json"""
import yfinance as yf, json, os, datetime, warnings
warnings.filterwarnings("ignore")

BASE = os.path.dirname(os.path.abspath(__file__))
TICKERS = {
    "^GSPC": "S&P 500", "^IXIC": "Nasdaq Composite", "^DJI": "Dow Jones",
    "^N225": "Nikkei 225", "^HSI": "Hang Seng",
    "^STI": "STI (Singapore)", "^KLSE": "KLCI (Malaysia)", "^JKSE": "JCI (Indonesia)",
    "^SET.BK": "SET (Thailand)", "PSEI.PS": "PSEi (Philippines)", "VNINDEX": "VN-Index (Vietnam)",
}

def main():
    data = yf.download(list(TICKERS), period="10d", interval="1d", progress=False,
                       auto_adjust=False, group_by="ticker", threads=True)
    markets, series = {}, {}
    for sym, name in TICKERS.items():
        try:
            df = data[sym]["Close"].dropna()
            if len(df) < 2:
                print(f"skip {name}: insufficient data")
                continue
            last = float(df.iloc[-1]); prev = float(df.iloc[-2])
            markets[sym] = {"name": name, "close": round(last, 2),
                            "prev": round(prev, 2),
                            "chg_pct": round((last / prev - 1) * 100, 2),
                            "date": str(df.index[-1].date())}
            s = df.tail(5)
            base = float(s.iloc[0])
            series[sym] = {"name": name, "days": [str(d.date()) for d in s.index],
                           "norm": [round(float(v) / base * 100, 1) for v in s]}
        except Exception as ex:
            print(f"skip {name}: {ex}")
    date = datetime.date.today().isoformat()
    os.makedirs(os.path.join(BASE, "data"), exist_ok=True)
    path = os.path.join(BASE, "data", f"markets_{date}.json")
    with open(path, "w") as f:
        json.dump({"date": date, "markets": markets, "series": series}, f, indent=1)
    print(f"{len(markets)} indices -> {path}")

if __name__ == "__main__":
    main()
