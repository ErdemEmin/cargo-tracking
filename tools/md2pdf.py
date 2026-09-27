"""RAPOR.md -> PDF (reportlab + markdown).

Markdown'ı basit bir blok ayrıştırıcıyla gezip reportlab Platypus
akışına çevirir. Desteklenenler: başlıklar, paragraf, madde işaretli
listeler, kod blokları, tablolar, yatay çizgi.
"""
import re
import sys
from pathlib import Path

import markdown as md_module  # noqa: F401  (opsiyonel; HTML dönüşümü için)
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, Image, PageTemplate,
                                Paragraph, Preformatted, Spacer, Table, TableStyle)

BASE = Path(__file__).resolve().parent.parent  # proje kökü
SRC = BASE / "RAPOR.md"
OUT = BASE / "Kargo_Takip_Sistemi_Raporu.pdf"

# --- Unicode font kaydı: Helvetica Türkçe ı/ş/ğ karakterlerini desteklemez ---
_FONTS = {
    "Body": ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    "Mono": ("C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/consolab.ttf"),
}
F_REG, F_BOLD, F_MONO = "ArBody", "ArBody-Bold", "ArMono"
for _name, (_reg, _bold) in _FONTS.items():
    if Path(_reg).exists():
        pdfmetrics.registerFont(TTFont(F_REG, _reg))
        if Path(_bold).exists():
            pdfmetrics.registerFont(TTFont(F_BOLD, _bold))
        break
if Path(_FONTS["Mono"][0]).exists():
    pdfmetrics.registerFont(TTFont(F_MONO, _FONTS["Mono"][0]))
else:
    F_MONO = "Courier"
pdfmetrics.registerFontFamily(F_REG, normal=F_REG, bold=F_BOLD,
                              italic=F_REG, boldItalic=F_BOLD)

ACCENT = colors.HexColor("#1f6feb")
CODE_BG = colors.HexColor("#f4f6f8")
BORDER = colors.HexColor("#d0d7de")

ss = getSampleStyleSheet()
STYLES = {
    "h1": ParagraphStyle("h1", parent=ss["Heading1"], fontSize=17, leading=22,
                          textColor=colors.HexColor("#0b2545"), spaceBefore=16,
                          spaceAfter=10, fontName=F_BOLD),
    "h2": ParagraphStyle("h2", parent=ss["Heading2"], fontSize=13.5, leading=17,
                          textColor=ACCENT, spaceBefore=14, spaceAfter=7,
                          fontName=F_BOLD),
    "h3": ParagraphStyle("h3", parent=ss["Heading3"], fontSize=11, leading=14.5,
                          textColor=colors.HexColor("#243b53"), spaceBefore=11,
                          spaceAfter=5, fontName=F_BOLD),
    "body": ParagraphStyle("body", parent=ss["BodyText"], fontSize=9.3, leading=13.6,
                           alignment=4, spaceAfter=6, fontName=F_REG),
    "code": ParagraphStyle("code", parent=ss["Code"], fontSize=7.4, leading=10.2,
                           backColor=CODE_BG, borderPadding=6, leftIndent=6,
                           fontName=F_MONO),
    "li": ParagraphStyle("li", parent=ss["BodyText"], fontSize=9.3, leading=13.6,
                         leftIndent=13, bulletIndent=3, spaceAfter=3, fontName=F_REG),
    "cell": ParagraphStyle("cell", parent=ss["BodyText"], fontSize=8.1, leading=10.8,
                           spaceAfter=0, fontName=F_REG),
    "cellh": ParagraphStyle("cellh", parent=ss["BodyText"], fontSize=8.1, leading=10.8,
                            fontName=F_BOLD, textColor=colors.white,
                            spaceAfter=0),
}


def inline(text):
    """Markdown inline -> reportlab markup.

    Sıra önemli: once metnin kendisini escape et, SONRA bicimlendirme
    etiketlerini ekle. Aksi halde uretilen <b>/<font> etiketleri de
    escape edilip ekranda ham metin olarak gorunur.
    """
    # 1) Gercek metni escape et (bu noktada henuz etiket yok)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # 2) Kod parcalari -> monospace
    text = re.sub(
        r"`([^`]+)`",
        lambda m: f'<font face="{F_MONO}" size="8.2">{m.group(1)}</font>',
        text,
    )
    # 3) Kalin metin
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    return text


def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def build_table(rows):
    ncol = len(rows[0])
    data = []
    for i, r in enumerate(rows):
        style = STYLES["cellh"] if i == 0 else STYLES["cell"]
        data.append([Paragraph(inline(c), style) for c in r])

    avail = A4[0] - 32 * mm
    # en geniş sütuna daha fazla pay ver
    widths = [1] * ncol
    longest = [max(len(r[c]) for r in rows) for c in range(ncol)]
    total = sum(longest) or 1
    widths = [max(avail * (l / total) * 1.6, avail * 0.09) for l in longest]
    scale = avail / sum(widths)
    widths = [w * scale for w in widths]

    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def convert():
    lines = SRC.read_text(encoding="utf-8").splitlines()
    story = []
    i = 0
    in_code = False
    code_buf = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # kod bloğu
        if stripped.startswith("```"):
            if in_code:
                story.append(Preformatted("\n".join(code_buf), STYLES["code"]))
                story.append(Spacer(1, 7))
                code_buf, in_code = [], False
            else:
                in_code = True
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue

        # tablo
        if stripped.startswith("|") and i + 1 < len(lines) \
                and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            rows = [split_row(stripped)]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            story.append(build_table(rows))
            story.append(Spacer(1, 9))
            continue

        # başlıklar
        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            lvl, text = len(m.group(1)), m.group(2)
            key = f"h{min(lvl, 3)}"
            if lvl == 1 and text.startswith("Ek:"):
                story.append(Paragraph(inline(text), STYLES["h2"]))
            else:
                story.append(Paragraph(inline(text), STYLES[key]))
            i += 1
            continue

        # yatay çizgi
        if re.match(r"^-{3,}$", stripped):
            story.append(Spacer(1, 5))
            i += 1
            continue

        # gorsel: ![alt](yol)
        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", stripped)
        if m:
            path = BASE / m.group(2)
            if path.exists():
                avail = A4[0] - 36 * mm
                img = Image(str(path))
                iw, ih = img.imageWidth, img.imageHeight
                w = min(avail, iw)
                img.drawWidth, img.drawHeight = w, ih * (w / iw)
                story.append(img)
                story.append(Spacer(1, 4))
                if m.group(1):
                    story.append(Paragraph(
                        f'<font size="8" color="#6b7785">{m.group(1)}</font>',
                        STYLES["body"]))
                story.append(Spacer(1, 9))
            else:
                story.append(Paragraph(
                    f'<font size="8" color="#999999">'
                    f'[gorsel bulunamadi: {m.group(2)}]</font>', STYLES["body"]))
            i += 1
            continue

        # madde işaretli liste
        m = re.match(r"^[-*]\s+(.*)$", stripped)
        if m:
            story.append(Paragraph(inline(m.group(1)), STYLES["li"],
                                   bulletText="•"))
            i += 1
            continue

        # numaralı liste
        m = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if m:
            story.append(Paragraph(inline(m.group(2)), STYLES["li"],
                                   bulletText=m.group(1) + "."))
            i += 1
            continue

        if not stripped:
            i += 1
            continue

        # paragraf (ardışık satırları birleştir)
        para = [stripped]
        i += 1
        while i < len(lines) and lines[i].strip() and \
                not re.match(r"^(#{1,4}\s|[-*]\s|\d+\.\s|\||```|-{3,}$)", lines[i].strip()):
            para.append(lines[i].strip())
            i += 1
        story.append(Paragraph(inline(" ".join(para)), STYLES["body"]))

    return story


def decorate(canvas, doc):
    canvas.saveState()
    canvas.setFont(F_REG, 7.5)
    canvas.setFillColor(colors.HexColor("#6b7785"))
    canvas.drawString(18 * mm, 12 * mm, "Kafka ve Grafana Tabanlı Kargo Takip Sistemi")
    canvas.drawRightString(A4[0] - 18 * mm, 12 * mm, f"Sayfa {doc.page}")
    canvas.setStrokeColor(BORDER)
    canvas.line(18 * mm, 15 * mm, A4[0] - 18 * mm, 15 * mm)
    canvas.restoreState()


def main():
    doc = BaseDocTemplate(
        str(OUT), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=20 * mm,
        title="Kafka ve Grafana Tabanlı Kargo Takip Sistemi",
        author="Erdem Emin",
        subject="Proje Raporu",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height,
                  id="main")
    doc.addPageTemplates([PageTemplate(id="all", frames=[frame],
                                       onPage=decorate)])
    doc.build(convert())
    print(f"PDF yazildi: {OUT}")


if __name__ == "__main__":
    sys.exit(main())
