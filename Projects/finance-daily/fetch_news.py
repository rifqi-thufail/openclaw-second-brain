#!/usr/bin/env python3
"""Fetch business news from RSS feeds. Output: data/news_<date>.json"""
import feedparser, requests, json, os, re, datetime, html

BASE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}

def clean(s):
    s = html.unescape(s or "")
    return re.sub(r"\s+", " ", s).strip()

def main():
    with open(os.path.join(BASE, "feeds.json")) as f:
        feeds = json.load(f)
    out, seen = [], set()
    for name, url in feeds.items():
        try:
            r = requests.get(url, headers=UA, timeout=15)
            d = feedparser.parse(r.content)
            for e in d.entries[:12]:
                title = clean(e.get("title"))
                link = (e.get("link") or "").strip()
                if not title or not link or link in seen:
                    continue
                seen.add(link)
                out.append({
                    "source": name,
                    "title": title,
                    "link": link,
                    "published": clean(e.get("published")),
                    "summary": clean(e.get("summary"))[:300],
                })
        except Exception as ex:
            print(f"skip {name}: {ex}")
    date = datetime.date.today().isoformat()
    os.makedirs(os.path.join(BASE, "data"), exist_ok=True)
    path = os.path.join(BASE, "data", f"news_{date}.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=1)
    print(f"{len(out)} stories -> {path}")

if __name__ == "__main__":
    main()
