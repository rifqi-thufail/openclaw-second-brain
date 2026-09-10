#!/usr/bin/env python3
"""Send memecoin signals to the memetracker Telegram bot.

Token resolution order:
1. MEMECOIN_BOT_TOKEN env (injected by gateway secret store)
2. .env file in project root (gitignored)
Never prints the token.
"""
import json, os, sys, urllib.request, urllib.parse, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(BASE, "state")


def load_env():
    env = {}
    p = os.path.join(BASE, ".env")
    if os.path.exists(p):
        for line in open(p):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def token():
    t = os.environ.get("MEMECOIN_BOT_TOKEN") or load_env().get("TELEGRAM_BOT_TOKEN")
    if not t:
        print("no bot token (set MEMECOIN_BOT_TOKEN or .env TELEGRAM_BOT_TOKEN)", file=sys.stderr)
        sys.exit(2)
    return t


def api(tok, method, payload=None, files=None):
    url = f"https://api.telegram.org/bot{tok}/{method}"
    if files is None:
        data = urllib.parse.urlencode(payload or {}).encode()
        req = urllib.request.Request(url, data=data)
    else:
        boundary = "----clawmeme" + str(int(datetime.datetime.utcnow().timestamp()))
        body = b""
        for k, v in (payload or {}).items():
            body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
        for k, (fn, content) in files.items():
            body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{fn}\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode()
            body += content + b"\r\n"
        body += f"--{boundary}--\r\n".encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, json.loads(r.read().decode())
    except Exception as e:
        return None, str(e)


def resolve_chat(tok, preferred=None):
    if preferred:
        return preferred
    _, res = api(tok, "getUpdates", {"timeout": 0})
    if isinstance(res, dict):
        for u in res.get("result", []):
            msg = u.get("message") or u.get("channel_post") or {}
            if msg.get("chat", {}).get("id"):
                return msg["chat"]["id"]
    return None


def build_message(payload):
    d = payload["date"]
    sigs = payload["signals"]
    head = [f"*Memecoin scan {d}*", f"candidates passing score >= {payload['threshold']}: {len(sigs)}"]
    if not sigs:
        head.append("_no setups passed the filter — no trade_")
        return "\n".join(head)
    for r in sigs[:6]:
        head += ["", f"*{r['symbol']}* — score {r['score']}/10",
                 f"liq ${r['liquidity_usd']:,.0f} | vol24h ${r['vol_24h']:,.0f} | pullback {r['pullback_pct']}% | B/S {r['buy_sell_ratio']}",
                 f"entry {r['plan']['entry']} | SL {r['plan']['stop']} | TP1 {r['plan']['tp1']} | TP2 {r['plan']['tp2']} | TSL runner",
                 r["url"]]
    head += ["", "_paper/signal only — no real funds_"]
    return "\n".join(head)


def main():
    chat = None
    if len(sys.argv) > 1:
        chat = sys.argv[1]
    env = load_env()
    chat = chat or env.get("TELEGRAM_CHAT_ID")
    payload_path = os.path.join(STATE, "signals.json")
    if not os.path.exists(payload_path):
        print("no signals.json yet — run scanner.py first", file=sys.stderr)
        sys.exit(2)
    with open(payload_path) as f:
        payload = json.load(f)
    tok = token()
    chat = resolve_chat(tok, chat)
    if not chat:
        print("no chat id resolved (DM the bot once, or set TELEGRAM_CHAT_ID)", file=sys.stderr)
        sys.exit(3)
    msg = build_message(payload)
    status, res = api(tok, "sendMessage", {"chat_id": chat, "text": msg, "parse_mode": "Markdown",
                                            "disable_web_page_preview": "true"})
    print("telegram sendMessage:", status, (res.get("ok") if isinstance(res, dict) else res))


if __name__ == "__main__":
    main()
