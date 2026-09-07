#!/usr/bin/env python3
"""Extract readable chat transcripts from each OpenClaw agent's SQLite store
into a per-day markdown folder, mirroring the legacy jsonl format. Secrets/ids
redacted. Reads transcript_events (live) + session_windows (session metadata)
from agents/<agent>/agent/openclaw-agent.sqlite."""
import json, os, sys, datetime, re, sqlite3, glob

out = sys.argv[1]                      # chat-history dir for this date
agents_root = sys.argv[2]              # /home/ratrocious/.openclaw/agents
cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=50)
TOKEN_RE = re.compile(r'\b\d{8,10}:[A-Za-z0-9_-]{35}\b')
SKIP_ROLES = {"toolResult"}            # keep output tight; include user+assistant

def redact(s):
    return TOKEN_RE.sub("***REDACTED***", s)

def window_key(db, session_id):
    """Map session_id -> readable session key + agent label."""
    try:
        con = sqlite3.connect("file:" + db + "?mode=ro", uri=True)
        r = con.execute("select session_key, display_name, started_at from session_windows "
                        "where session_id=? order by created_at desc limit 1",
                        (session_id,)).fetchone()
        con.close()
        if r:
            return r[0] or session_id, r[1] or "", r[2]
    except Exception:
        pass
    return session_id, "", None

count, written = 0, 0
for db in glob.glob(os.path.join(agents_root, "*", "agent", "openclaw-agent.sqlite")):
    agent = os.path.basename(os.path.dirname(os.path.dirname(db)))
    con = sqlite3.connect("file:" + db + "?mode=ro", uri=True)
    try:
        # group transcript events by session
        sessions = {}
        for sid, seq, ej in con.execute(
                "select session_id, seq, event_json from transcript_events "
                "where created_at >= ? order by seq asc", (int(cutoff.timestamp() * 1000),)):
            try:
                e = json.loads(ej)
            except Exception:
                continue
            if e.get("type") != "message":
                continue
            m = e.get("message", {})
            role = m.get("role", "?")
            if role in SKIP_ROLES:
                continue
            content = m.get("content", "")
            text = ""
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                parts = [c.get("text", "") for c in content
                         if isinstance(c, dict) and c.get("type") == "text"]
                text = " ".join(parts)
            if not text.strip():
                continue
            ts = str(e.get("timestamp", ""))[:19]
            sessions.setdefault(sid, []).append(f"### {role} @ {ts}\n\n{redact(text)}")
        for sid, lines in sessions.items():
            key, disp, st = window_key(db, sid)
            safe = re.sub(r'[^A-Za-z0-9._-]+', '_', str(key))[:70] or sid[:20]
            with open(os.path.join(out, f"{agent}__{safe}.md"), "w") as f:
                f.write(f"# {agent} | {key} | {disp}\n\n" + "\n\n".join(lines))
            written += 1
            count += len(lines)
    except Exception as ex:
        print("warn", db, ex)
    finally:
        con.close()

print(f"chat export: {written} session files, {count} message lines -> {out}")
