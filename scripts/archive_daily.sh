#!/usr/bin/env bash
# Daily second-brain archive: config snapshot + chat history transcripts, then git sync.
set -euo pipefail

WS=/root/.openclaw/workspace
DATE=$(date +%Y-%m-%d)
CONF_DIR="$WS/Archives/openclaw-config/$DATE"
CHAT_DIR="$WS/Archives/chat-history/$DATE"
mkdir -p "$CONF_DIR" "$CHAT_DIR"

# 1. Config snapshot (secrets redacted for git)
python3 - "$CONF_DIR" <<'PY'
import json, os, sys, re, shutil
out = sys.argv[1]
TOKEN_RE = re.compile(r'\b\d{8,10}:[A-Za-z0-9_-]{35}\b')

def redact(o):
    if isinstance(o, dict):
        return {k: ("***REDACTED***" if any(t in k.lower() for t in ("token", "secret", "apikey", "password")) else redact(v)) for k, v in o.items()}
    if isinstance(o, list):
        return [redact(i) for i in o]
    if isinstance(o, str):
        return TOKEN_RE.sub("***REDACTED***", o)
    return o

cfg = json.load(open("/root/.openclaw/openclaw.json"))
json.dump(redact(cfg), open(os.path.join(out, "openclaw.json"), "w"), indent=2)
for f in os.listdir("/root/.openclaw/credentials"):
    if "allowFrom" in f:
        shutil.copy(os.path.join("/root/.openclaw/credentials", f), os.path.join(out, f))
PY

# 2. Chat history transcripts (sessions modified in the last 26h)
python3 - "$CHAT_DIR" <<'PY'
import json, os, sys, datetime, re
out = sys.argv[1]
TOKEN_RE = re.compile(r'\b\d{8,10}:[A-Za-z0-9_-]{35}\b')
agents_dir = "/root/.openclaw/agents"
cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=26)
count = 0
for agent in os.listdir(agents_dir):
    sess_dir = os.path.join(agents_dir, agent, "sessions")
    if not os.path.isdir(sess_dir):
        continue
    for fn in os.listdir(sess_dir):
        if not fn.endswith(".jsonl") or fn.endswith(".lock"):
            continue
        p = os.path.join(sess_dir, fn)
        if datetime.datetime.fromtimestamp(os.path.getmtime(p), datetime.timezone.utc) < cutoff:
            continue
        md = []
        with open(p) as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("type") != "message":
                    continue
                m = rec.get("message", {})
                role = m.get("role", "?")
                content = m.get("content", "")
                if isinstance(content, list):
                    parts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
                    content = " ".join(parts)
                content = TOKEN_RE.sub("***REDACTED***", str(content))
                ts = rec.get("timestamp", "")[:16]
                md.append(f"### {role} @ {ts}\n\n{content}\n")
        if md:
            name = f"{agent}__{fn.replace('.jsonl', '.md')}"
            with open(os.path.join(out, name), "w") as f:
                f.write("\n\n".join(md))
            count += 1
print(f"transcripts: {count}")
PY

# 3. Git sync
cd "$WS"
git add -A
git commit -m "Daily archive $DATE" --quiet || true
git push --quiet origin master 2>&1 || echo "push failed"
echo "archived $DATE"
