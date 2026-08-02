#!/usr/bin/env python3
"""Build 2-page equity research style PDF. Reads analysis.md + market data + charts."""
import json, os, re, datetime, glob
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                Image, HRFlowable, PageBreak, KeepTogether)

BASE = os.path.dirname(os.path.abspath(__file__))
NAVY, GRAY, RED, DARK = "#1f4e79", "#666666", "#a6192e", "#1a1a1a"
MARGIN = 16 * mm

def styles():
    return {
        "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=16, textColor=DARK, spaceAfter=2),
        "sub": ParagraphStyle("sub", fontName="Helvetica", fontSize=8.5, textColor=GRAY, spaceAfter=8),
        "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=11, textColor=NAVY, spaceBefore=7, spaceAfter=3),
        "story": ParagraphStyle("story", fontName="Helvetica-Bold", fontSize=9, textColor=DARK, spaceBefore=4),
        "body": ParagraphStyle("body", fontName="Helvetica", fontSize=8.4, leading=11, textColor=DARK),
        "bullet": ParagraphStyle("bullet", fontName="Helvetica", fontSize=8.4, leading=11, textColor=DARK, leftIndent=8, bulletIndent=0),
        "small": ParagraphStyle("small", fontName="Helvetica", fontSize=7, leading=8.5, textColor=GRAY),
    }

def parse_analysis(path):
    """Parse analysis.md into {exec:[bullets], stories:[{title, lines}], sections:{name:[lines]}, sources:[str]}"""
    out = {"exec": [], "stories": [], "sections": {}, "sources": []}
    cur = None
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
                out["stories"].append({"title": line[3:].strip(), "lines": []})
                cur = ("story", out["stories"][-1]["lines"])
            elif line.startswith("- ") and cur and cur[0] in ("exec", "sec", "sources", "story"):
                cur[1].append(line[2:].strip())
            elif line.strip() and cur and cur[0] in ("sec", "story"):
                cur[1].append(line.strip())
    return out

def build(market_file, analysis_file, pdf_path):
    with open(market_file) as f:
        md = json.load(f)
    a = parse_analysis(analysis_file)
    st = styles()
    doc = SimpleDocTemplate(pdf_path, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=14 * mm, bottomMargin=14 * mm,
                            title="Claw Research Daily Briefing", author="Claw Research")
    el = []
    # Header
    el.append(Paragraph("CLAW RESEARCH", st["title"]))
    el.append(Paragraph(f"Daily Market Briefing &nbsp;|&nbsp; {md['date']} &nbsp;|&nbsp; US + ASEAN Equities &nbsp;|&nbsp; For information only", st["sub"]))
    el.append(HRFlowable(width="100%", thickness=1.2, color=colors.HexColor(NAVY)))
    # Executive summary
    el.append(Paragraph("Executive Summary", st["h2"]))
    for b in a["exec"]:
        el.append(Paragraph(f"&bull; {b}", st["bullet"]))
    # Market table
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
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    el.append(t)
    # Charts
    chg = os.path.join(BASE, "output", "charts", "change.png")
    trd = os.path.join(BASE, "output", "charts", "trend.png")
    if os.path.exists(chg):
        el.append(Spacer(1, 4))
        el.append(Image(chg, width=178 * mm, height=70 * mm))
    # Page 2
    el.append(PageBreak())
    if os.path.exists(trd):
        el.append(Image(trd, width=178 * mm, height=60 * mm))
    el.append(Spacer(1, 3))
    # Top stories
    el.append(Paragraph("Top Stories &amp; Actionable Insights", st["h2"]))
    for s in a["stories"]:
        el.append(Paragraph(s["title"], st["story"]))
        for ln in s["lines"]:
            if ln.lower().startswith("insight"):
                el.append(Paragraph(f'<font color="{NAVY}"><b>{ln}</b></font>', st["body"]))
            elif ln.lower().startswith("action"):
                el.append(Paragraph(f'<font color="{RED}"><b>{ln}</b></font>', st["body"]))
            else:
                el.append(Paragraph(ln, st["body"]))
    for name, lines in a["sections"].items():
        el.append(Paragraph(name, st["h2"]))
        for ln in lines:
            el.append(Paragraph(f"&bull; {ln}", st["bullet"]))
    # Sources
    el.append(Paragraph("Sources", st["h2"]))
    for s in a["sources"]:
        el.append(Paragraph(f"&bull; {s}", st["small"]))
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
