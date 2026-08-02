#!/usr/bin/env python3
"""Build 2-page equity research style PDF. Reads analysis.md + market data + idn data + charts.
Includes: Indonesia Focus section (JCI, 10Y yield, CDS), numbered citations with references list."""
import json, os, re, datetime, glob
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                Image, HRFlowable, PageBreak)

BASE = os.path.dirname(os.path.abspath(__file__))
NAVY, GRAY, RED, DARK = "#1f4e79", "#666666", "#a6192e", "#1a1a1a"
MARGIN = 16 * mm

def styles():
    return {
        "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=15, textColor=DARK, spaceAfter=2),
        "sub": ParagraphStyle("sub", fontName="Helvetica", fontSize=8, textColor=GRAY, spaceAfter=6),
        "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=10.5, textColor=NAVY, spaceBefore=5, spaceAfter=2),
        "story": ParagraphStyle("story", fontName="Helvetica-Bold", fontSize=8.6, textColor=DARK, spaceBefore=3),
        "body": ParagraphStyle("body", fontName="Helvetica", fontSize=7.9, leading=10, textColor=DARK),
        "bullet": ParagraphStyle("bullet", fontName="Helvetica", fontSize=7.9, leading=10, textColor=DARK, leftIndent=8, bulletIndent=0),
        "small": ParagraphStyle("small", fontName="Helvetica", fontSize=6.6, leading=8, textColor=GRAY),
        "ref": ParagraphStyle("ref", fontName="Helvetica", fontSize=6.6, leading=8, textColor=GRAY, leftIndent=10),
    }

def parse_analysis(path):
    """Parse analysis.md into {exec:[bullets], stories:[{title, lines, sources}], sections:{name:[lines]}, sources:[str]}"""
    out = {"exec": [], "stories": [], "sections": {}, "sources": []}
    cur = None
    refs = []
    with open(path) as f:
        for raw in f:
            line = raw.rstrip()
            if line.startswith("# Executive Summary"):
                cur = ("exec", out["exec"])
            elif line.startswith("# Top Stories"):
                cur = ("stories", None)
            elif line.startswith("# Sources"):
                cur = ("sources", out["sources"])
            elif line.startswith("# "):
                name = line[2:].strip()
                out["sections"].setdefault(name, [])
                cur = ("sec", out["sections"][name])
            elif line.startswith("## "):
                out["stories"].append({"title": line[3:].strip(), "lines": [], "sources": []})
                cur = ("story", out["stories"][-1])
            elif line.startswith("- ") and cur and cur[0] in ("exec", "sec", "sources", "story"):
                cur[1].append(line[2:].strip())
            elif line.strip().lower().startswith("source:") and cur and cur[0] == "story":
                url = line.split(":", 1)[1].strip()
                if url and url not in refs:
                    refs.append(url)
                cur[1]["sources"].append(url)
            elif line.strip() and cur and cur[0] in ("sec", "story"):
                target = cur[1]["lines"] if cur[0] == "story" else cur[1]
                target.append(line.strip())
    # build global ref list with numbers
    out["refs"] = refs
    return out

def idn_block(market_file):
    """Indonesia data: JCI from markets, 10Y yield + CDS from idn json."""
    out = {"jci": None, "yield": None, "cds": None}
    date = datetime.date.today().isoformat()
    with open(market_file) as f:
        md = json.load(f)
    if "^JKSE" in md["markets"]:
        v = md["markets"]["^JKSE"]
        out["jci"] = (v["close"], v["chg_pct"])
    idn_path = os.path.join(BASE, "data", f"idn_{date}.json")
    if os.path.exists(idn_path):
        with open(idn_path) as f:
            d = json.load(f)
        out["yield"] = d.get("yield_10y")
        out["cds"] = (d.get("cds") or {}).get("id_cds")
    return out

def build(market_file, analysis_file, pdf_path):
    with open(market_file) as f:
        md = json.load(f)
    a = parse_analysis(analysis_file)
    idn = idn_block(market_file)
    st = styles()
    doc = SimpleDocTemplate(pdf_path, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=12 * mm, bottomMargin=11 * mm,
                            title="Claw Research Daily Briefing", author="Claw Research")
    el = []
    el.append(Paragraph("CLAW RESEARCH", st["title"]))
    el.append(Paragraph(f"Daily Market Briefing &nbsp;|&nbsp; {md['date']} &nbsp;|&nbsp; US + ASEAN Equities &nbsp;|&nbsp; For information only", st["sub"]))
    el.append(HRFlowable(width="100%", thickness=1.2, color=colors.HexColor(NAVY)))
    el.append(Paragraph("Executive Summary", st["h2"]))
    for b in a["exec"]:
        el.append(Paragraph(f"&bull; {b}", st["bullet"]))
    el.append(Paragraph("Market Snapshot", st["h2"]))
    rows = [["Index", "Close", "Chg %"]]
    for sym, v in sorted(md["markets"].items(), key=lambda kv: kv[1]["chg_pct"], reverse=True):
        c = RED if v["chg_pct"] < 0 else DARK
        rows.append([v["name"], f"{v['close']:,.2f}", Paragraph(f'<font color="{c}">{v["chg_pct"]:+.2f}%</font>', st["body"])])
    t = Table(rows, colWidths=[70 * mm, 30 * mm, 25 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f5f8")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    el.append(t)
    chg = os.path.join(BASE, "output", "charts", "change.png")
    if os.path.exists(chg):
        el.append(Spacer(1, 3))
        el.append(Image(chg, width=178 * mm, height=62 * mm))
    el.append(PageBreak())
    trd = os.path.join(BASE, "output", "charts", "trend.png")
    if os.path.exists(trd):
        el.append(Image(trd, width=178 * mm, height=38 * mm))
    el.append(Spacer(1, 2))
    el.append(Paragraph("Top Stories &amp; Actionable Insights", st["h2"]))
    ref_map = {u: i + 1 for i, u in enumerate(a["refs"])}
    for s in a["stories"]:
        cites = "".join(f'<sup>[{ref_map[u]}]</sup>' for u in s["sources"] if u in ref_map)
        el.append(Paragraph(s["title"] + " " + cites, st["story"]))
        for ln in s["lines"]:
            if ln.lower().startswith("insight"):
                el.append(Paragraph(f'<font color="{NAVY}"><b>{ln}</b></font>', st["body"]))
            elif ln.lower().startswith("action"):
                el.append(Paragraph(f'<font color="{RED}"><b>{ln}</b></font>', st["body"]))
            else:
                el.append(Paragraph(ln, st["body"]))
    for name, lines in a["sections"].items():
        if name == "Indonesia Focus":
            continue  # rendered below with data table
        el.append(Paragraph(name, st["h2"]))
        for ln in lines:
            el.append(Paragraph(f"&bull; {ln}", st["bullet"]))
    # Indonesia Focus (bullets from analysis + data-driven table)
    if "Indonesia Focus" in a["sections"] or idn["jci"] or idn["yield"] or idn["cds"]:
        el.append(Paragraph("Indonesia Focus", st["h2"]))
        for ln in a["sections"].get("Indonesia Focus", []):
            el.append(Paragraph(f"&bull; {ln}", st["bullet"]))
        irows = [["Indicator", "Value"]]
        if idn["jci"]:
            close, chg = idn["jci"]
            c = RED if chg < 0 else DARK
            irows.append(["JCI (Jakarta Composite)", Paragraph(f'{close:,.2f} (<font color="{c}">{chg:+.2f}%</font>)', st["body"])])
        if idn["yield"]:
            irows.append(["10Y Govt Bond Yield", f"{idn['yield']:.2f}%"])
        if idn["cds"]:
            irows.append(["5Y CDS (bps)", f"{idn['cds']:.2f}"])
        if len(irows) > 1:
            it = Table(irows, colWidths=[70 * mm, 55 * mm])
            it.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("TEXTCOLOR", (0, 0), (-1, 0), NAVY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f5f8")]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
                ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            el.append(it)
    # References (numbered citations)
    if a["refs"]:
        el.append(Paragraph("References", st["h2"]))
        for i, u in enumerate(a["refs"], 1):
            el.append(Paragraph(f"[{i}] {u}", st["ref"]))
    el.append(Spacer(1, 8))
    el.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#bbbbbb")))
    el.append(Paragraph("Disclaimer: This briefing is generated automatically for information purposes only and does not constitute investment advice. Verify all data before acting.", st["small"]))
    doc.build(el)
    print(f"PDF -> {pdf_path}")

if __name__ == "__main__":
    date = datetime.date.today().isoformat()
    build(os.path.join(BASE, "data", f"markets_{date}.json"),
          os.path.join(BASE, "analysis.md"),
          os.path.join(BASE, "output", f"briefing_{date}.pdf"))
