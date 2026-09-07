#!/usr/bin/env bash
# Daily second-brain archive: config snapshot + chat history transcripts, then git sync.
# Multi-agent aware. Secrets redacted for git. Runs from anywhere.
set -euo pipefail

OPENCLAW_HOME="${OPENCLAW_HOME:-$HOME/.openclaw}"
WS="${WS:-$OPENCLAW_HOME/workspace}"
AGENTS_DIR="${AGENTS_DIR:-$OPENCLAW_HOME/agents}"
CONFIG_FILE="${CONFIG_FILE:-$OPENCLAW_HOME/openclaw.json}"
CREDS_DIR="${CREDS_DIR:-$OPENCLAW_HOME/credentials}"
SECOND_BRAIN="${SECOND_BRAIN:-/home/ratrocious/.openclaw/workspace}"   # git repo root
DATE=$(date +%Y-%m-%d)
CONF_DIR="$SECOND_BRAIN/Archives/openclaw-config/$DATE"
CHAT_DIR="$SECOND_BRAIN/Archives/chat-history/$DATE"
mkdir -p "$CONF_DIR" "$CHAT_DIR"

# ---- 1. Config snapshot (secrets redacted for git) --------------------------
python3 - "$CONF_DIR" "$CONFIG_FILE" "$CREDS_DIR" "$OPENCLAW_HOME" <<'PY'
import json, os, sys, re, shutil
out, cfg_file, creds_dir, oc_home = sys.argv[1:5]
TOKEN_RE = re.compile(r'\b\d{8,10}:[A-Za-z0-9_-]{35}\b')
SECRET_KEYS = ("token","secret","apikey","password","clientsecret","privatekey")

def redact(o):
    if isinstance(o, dict):
        return {k: ("***REDACTED***" if any(t in k.lower() for t in SECRET_KEYS) else redact(v))
                for k, v in o.items()}
    if isinstance(o, list):
        return [redact(i) for i in o]
    if isinstance(o, str):
        return TOKEN_RE.sub("***REDACTED***", o)
    return o

cfg = json.load(open(cfg_file))
json.dump(redact(cfg), open(os.path.join(out, "openclaw.json"), "w"), indent=2)

# snapshot the two agent workspaces' persona/memory-less markdown (rules/id so a
# fresh install can restore behaviour). Persona set is durable config, not secrets.
for agent, src in (("main", os.path.join(oc_home, "workspace")),
                   ("verbose", os.path.join(oc_home, "workspace-verbose"))):
    md_dest = os.path.join(out, f"agent-{agent}")
    os.makedirs(md_dest, exist_ok=True)
    for f in ("AGENTS.md","SOUL.md","IDENTITY.md","TOOLS.md","USER.md","HEARTBEAT.md"):
        p = os.path.join(src, f)
        if os.path.isfile(p):
            shutil.copy(p, os.path.join(md_dest, f))

# any allowFrom gate files (authorization is config, never secrets)
if os.path.isdir(creds_dir):
    for f in os.listdir(creds_dir):
        if "allowFrom" in f:
            shutil.copy(os.path.join(creds_dir, f), os.path.join(out, f))
PY

# ---- 2. Chat history transcripts (all agents, sessions touched in last 26h) -
python3 - "$CHAT_DIR" "$AGENTS_DIR" <<'PY'
import json, os, sys, datetime, re
out, agents_dir = sys.argv[1], sys.argv[2]
TOKEN_RE = re.compile(r'\b\d{8,10}:[A-Za-z0-9_-]{35}\b')
cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=26)
count = 0
if not os.path.isdir(agents_dir):
    print("no agents dir:", agents_dir); sys.exit(0)
for agent in os.listdir(agents_dir):
    sess_dir = os.path.join(agents_dir, agent, "sessions")
    if not os.path.isdir(sess_dir):
        continue
    for fn in os.listdir(sess_dir):
        if not (fn.endswith(".jsonl") or fn.endswith(".jsonl.zst")) or fn.endswith(".lock"):
            continue
        p = os.path.join(sess_dir, fn)
        try:
            mtime = os.path.getmtime(p)
        except OSError:
            continue
        if datetime.datetime.fromtimestamp(mtime, datetime.timezone.utc) < cutoff:
            continue
        md = []
        # decompress .zst transcripts inline if present
        import gzip
        opener = open
        try:
            if fn.endswith(".zst"):
                import zstandard as zstd
                def opener(fn):
                    dctx = zstd.ZstdDecompressor()
                    raw = open(fn, "rb").read()
                    return dctx.decompress(raw, max_output_size=128*1024*1024)
        except ImportError:
            continue
        try:
            lines = opener(p)
            if isinstance(lines, bytes):
                lines = lines.decode("utf-8", "replace").splitlines()
        except Exception:
            continue
        for line in lines:
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
            ts = str(rec.get("timestamp", ""))[:19]
            md.append(f"### {role} @ {ts}\n\n{content}\n")
        if md:
            name = f"{agent}__{fn.rsplit('.',2)[0] if fn.endswith('.zst') else fn.replace('.jsonl','')}.md"
            with open(os.path.join(out, name), "w") as f:
                f.write("\n\n".join(md))
            count += 1
print(f"transcripts: {count}")
PY

# ---- 3. Git sync -------------------------------------------------------------
cd "$SECOND_BRAIN"
git add -A
git commit -m "Daily archive $DATE" --quiet || true
if git push --quiet origin master 2>&1; then
  echo "pusmt ok: archived $DATE"
else
  echo "push FAILED for $DATE (auth or network)"
fi
