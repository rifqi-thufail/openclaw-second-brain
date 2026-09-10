#!/usr/bin/env python3
"""Send daily briefing to Telegram bot. Auto-discovers chat from getUpdates if not set."""
import json, os, re, sys, datetime, requests

BASE = os.path.dirname(os.path.abspath(__file__))

def load_env():
    env = {}
    with open(os.path.join(BASE, ".env")) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env

def api(env, method, **kw):
    url = f"https://api.telegram.org/bot{env['TELEGRAM_BOT_TOKEN']}/{method}"
    return requests.post(url, **kw, timeout=30)

def resolve_chats(env):
    """Return a list of chat ids to deliver to.
    TELEGRAM_CHAT_ID may hold one id or a comma-separated list.
    Falls back to getUpdates discovery when unset."""
    ids = []
    raw = (env.get("TELEGRAM_CHAT_IDS") or env.get("TELEGRAM_CHAT_ID") or "").strip()
    if raw:
        ids = [x.strip() for x in raw.split(",") if x.strip()]
    if not ids:
        r = api(env, "getUpdates", data={"limit": 10, "timeout": 0}).json()
        for u in r.get("result", []):
            m = u.get("message") or u.get("edited_message") or {}
            c = m.get("chat") or {}
            if c.get("type") in ("private", "group", "supergroup"):
                ids.append(str(c["id"]))
    return ids


def resolve_chat(env):
    chats = resolve_chats(env)
    return chats[0] if chats else None

def summary_text():
    """Build short text summary from analysis.md exec bullets + top stories."""
    with open(os.path.join(BASE, "analysis.md")) as f:
        txt = f.read()
    lines = [l[2:].strip() for l in txt.splitlines() if l.startswith("- ")]
    return "\n".join(lines[:8]) or "No summary."

def main():
    env = load_env()
    chats = resolve_chats(env)
    if not chats:
        print("ERROR: no chat found. User must press Start on the bot first.")
        sys.exit(2)
    date = datetime.date.today().isoformat()
    txt = (f"<b>Claw Research | Daily Briefing {date}</b>\n"
           f"US + ASEAN Equities\n\n" + summary_text())
    for chat in chats:
        r = api(env, "sendMessage", data={"chat_id": chat, "text": txt, "parse_mode": "HTML"})
        print(f"msg[{chat}]:", r.status_code)
        for f in ("change.png", "trend.png", "weekly_change.png", "weekly_trend.png", "rupiah.png"):
            p = os.path.join(BASE, "output", "charts", f)
            if os.path.exists(p):
                with open(p, "rb") as fh:
                    r = api(env, "sendPhoto", data={"chat_id": chat}, files={"photo": (f, fh)})
                print(f"{f}[{chat}]:", r.status_code)
        pdf = os.path.join(BASE, "output", f"briefing_{date}.pdf")
        if os.path.exists(pdf):
            with open(pdf, "rb") as fh:
                r = api(env, "sendDocument", data={"chat_id": chat, "caption": f"Equity research brief {date}"},
                        files={"document": (os.path.basename(pdf), fh)})
            print(f"pdf[{chat}]:", r.status_code)

if __name__ == "__main__":
    main()
