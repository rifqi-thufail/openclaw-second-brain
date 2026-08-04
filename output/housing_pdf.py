#!/usr/bin/env python3
"""Generate a tabular PDF of budget accommodation listings (KL / JB / Penang)."""
import json, sys
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle)
from reportlab.lib.enums import TA_CENTER

DATA = sys.argv[1] if len(sys.argv) > 1 else "output/housing_data.json"
OUT = sys.argv[2] if len(sys.argv) > 2 else "output/housing_listings.pdf"

with open(DATA) as f:
    regions = json.load(f)

doc = SimpleDocTemplate(
    OUT, pagesize=landscape(A4),
    leftMargin=12*mm, rightMargin=12*mm, topMargin=14*mm, bottomMargin=14*mm,
    title="Budget Accommodation Near Public Transport",
    author="Claw")

title_st = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=15,
                          alignment=TA_CENTER, spaceAfter=2)
sub_st = ParagraphStyle("s", fontName="Helvetica", fontSize=8.5,
                        alignment=TA_CENTER, textColor=colors.grey,
                        spaceAfter=10)
hdr_st = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=8.5,
                        textColor=colors.white)
cell_st = ParagraphStyle("c", fontName="Helvetica", fontSize=8, leading=10)
reg_st = ParagraphStyle("r", fontName="Helvetica-Bold", fontSize=11,
                        textColor=colors.HexColor("#1a3a5c"), spaceBefore=6,
                        spaceAfter=4)

story = [Paragraph("Budget Accommodation Near Public Transport", title_st),
         Paragraph("KL / Johor Bahru / Penang | monthly rent under RM800 | "
                   "max 15-min walk to transit | prices from live listings Aug 2026 - "
                   "verify before booking. Some rooms have gender restrictions.",
                   sub_st)]

headers = ["#", "Name", "Area / Neighbourhood", "Type", "Price (MYR)",
           "Nearest Transport (walk)", "Landlord / Contact", "Source / URL"]
col_w = [7*mm, 34*mm, 34*mm, 26*mm, 24*mm, 42*mm, 32*mm, 62*mm]

for reg in regions:
    story.append(Paragraph(f"{reg['region']} ({len(reg['items'])} listings)", reg_st))
    rows = [[Paragraph(h, hdr_st) for h in headers]]
    for i, it in enumerate(reg["items"], 1):
        rows.append([
            Paragraph(str(i), cell_st),
            Paragraph(it.get("name", "-"), cell_st),
            Paragraph(it.get("area", "-"), cell_st),
            Paragraph(it.get("type", "-"), cell_st),
            Paragraph(it.get("price", "-"), cell_st),
            Paragraph(it.get("transport", "-"), cell_st),
            Paragraph(it.get("contact", "-"), cell_st),
            Paragraph(it.get("source", "-"), cell_st),
        ])
    t = Table(rows, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#eef3f8")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b9c6d2")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t)
    story.append(Spacer(1, 8))

doc.build(story)
print("PDF written:", OUT)
