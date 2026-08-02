#!/usr/bin/env python3
"""Fetch Indonesia-specific data: 10Y govt bond yield (TE), 5Y CDS (WGB via headless chromium).
Output: data/idn_<date>.json"""
import json, os, re, datetime, subprocess, sys, tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}

CDS_SCRIPT = r'''
import asyncio, json, re, sys
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        pg = await b.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0")
        data = []
        async def on_resp(r):
            if "cds/v1/main" in r.url and r.status == 200:
                try:
                    data.append(await r.text())
                except Exception:
                    pass
        pg.on("response", on_resp)
        try:
            await pg.goto("https://www.worldgovernmentbonds.com/sovereign-cds/", timeout=45000)
            await pg.wait_for_timeout(8000)
        except Exception as e:
            print(json.dumps({"error": str(e)}))
            await b.close()
            return
        result = {}
        for txt in data:
            # response is JSON-escaped: \"code\": \"ID\"
            for code, key in [("ID","id_cds"),("MY","my_cds"),("TH","th_cds"),("PH","ph_cds"),("VN","vn_cds"),("SG","sg_cds")]:
                idx = txt.find(f'\\"code\\": \\"{code}\\"')
                if idx < 0:
                    idx = txt.find(f'\"code\": \"{code}\"')
                if idx >= 0:
                    m = re.search(r'\\"value\\":\s*([0-9.]+)', txt[idx:idx+150])
                    if m:
                        result[key] = float(m.group(1))
        print(json.dumps(result))
        await b.close()

asyncio.run(main())
'''

def fetch_yield():
    """ID 10Y govt bond yield from Trading Economics (server-rendered)."""
    import requests
    try:
        r = requests.get("https://tradingeconomics.com/indonesia/government-bond-yield", headers=UA, timeout=20)
        m = re.search(r"10 Year Government Bond Yield[^0-9]*([0-9]+\.[0-9]{2})%", r.text)
        if m:
            return float(m.group(1))
        m = re.search(r"([0-9]+\.[0-9]{2})%", r.text)
        if m:
            return float(m.group(1))
    except Exception as e:
        print(f"yield fetch error: {e}")
    return None

def fetch_cds():
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(CDS_SCRIPT)
        tmp = f.name
    try:
        out = subprocess.run([sys.executable, tmp], capture_output=True, text=True, timeout=150, cwd=BASE)
        if out.stdout.strip():
            return json.loads(out.stdout.strip().splitlines()[-1])
        print("cds stderr:", out.stderr[-400:] if out.stderr else "none")
    except Exception as e:
        print(f"cds error: {e}")
    finally:
        os.unlink(tmp)
    return {}

def main():
    result = {"date": datetime.date.today().isoformat(), "yield_10y": None, "cds": {}}
    y = fetch_yield()
    if y:
        result["yield_10y"] = y
        print(f"ID 10Y yield: {y}%")
    cds = fetch_cds()
    result["cds"] = cds
    if cds.get("id_cds"):
        print(f"ID 5Y CDS: {cds['id_cds']} bps | MY {cds.get('my_cds')} TH {cds.get('th_cds')} PH {cds.get('ph_cds')} VN {cds.get('vn_cds')} SG {cds.get('sg_cds')}")
    else:
        print("CDS fetch failed")
    os.makedirs(os.path.join(BASE, "data"), exist_ok=True)
    path = os.path.join(BASE, "data", f"idn_{result['date']}.json")
    with open(path, "w") as f:
        json.dump(result, f, indent=1)
    print(f"idn data -> {path}")

if __name__ == "__main__":
    main()
