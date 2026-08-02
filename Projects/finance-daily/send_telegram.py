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

def resolve_chat(env):
    if env.get("TELEGRAM_CHAT_ID"):
        return env["TELEGRAM_CHAT_ID"]
    r = api(env, "getUpdates", data={"limit": 10, "timeout": 0}).json()
    for u in r.get("result", []):
        m = u.get("message") or u.get("edited_message") or {}
        c = m.get("chat") or {}
        if c.get("type") in ("private", "group", "supergroup"):
            return str(c["id"])
    return None

def summary_text():
    """Build short text summary from analysis.md exec bullets + top stories."""
    with open(os.path.join(BASE, "analysis.md")) as f:
        txt = f.read()
    lines = [l[2:].strip() for l in txt.splitlines() if l.startswith("- ")]
    return "\n".join(lines[:8]) or "No summary."

def main():
    env = load_env()
    chat = resolve_chat(env)
    if not chat:
        print("ERROR: no chat found. User must press Start on the bot first.")
        sys.exit(2)
    date = datetime.date.today().isoformat()
    # 1) text summary
    txt = (f"<b>Claw Research | Daily Briefing {date}</b>\n"
           f"US + ASEAN Equities\n\n" + summary_text())
    r = api(env, "sendMessage", data={"chat_id": chat, "text": txt, "parse_mode": "HTML"})
    print("msg:", r.status_code)
    # 2) charts as photos
    for f in ("change.png", "trend.png"):
        p = os.path.join(BASE, "output", "charts", f)
        if os.path.exists(p):
            with open(p, "rb") as fh:
                r = api(env, "sendPhoto", data={"chat_id": chat}, files={"photo": (f, fh)})
            print(f"{f}:", r.status_code)
    # 3) PDF
    pdf = os.path.join(BASE, "output", f"briefing_{date}.pdf")
    if os.path.exists(pdf):
        with open(pdf, "rb") as fh:
            r = api(env, "sendDocument", data={"chat_id": chat, "caption": f"Equity research brief {date}"},
                    files={"document": (os.path.basename(pdf), fh)})
        print("pdf:", r.status_code)

if __name__ == "__main__":
    main()
