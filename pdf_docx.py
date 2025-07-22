import fitz  # PyMuPDF
import sys
import os
from collections import defaultdict
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth

def rect_overlap(rect1, rect2):
    return not (
        rect1.x1 < rect2.x0 or rect1.x0 > rect2.x1 or
        rect1.y1 < rect2.y0 or rect1.y0 > rect2.y1
    )

def extract_highlighted_text_layout_aware(doc):
    results = defaultdict(list)
    for page_number in range(len(doc)):
        page = doc[page_number]
        wordlist = page.get_text("words")
        highlight_rects = []
        for annot in page.annots():
            if annot.type[0] != 8:
                continue
            quads = [annot.vertices[i:i+4] for i in range(0, len(annot.vertices), 4)]
            for quad in quads:
                r = fitz.Quad(quad).rect
                highlight_rects.append(r)
        if not highlight_rects:
            continue
        matched_words = []
        for w in wordlist:
            word_rect = fitz.Rect(w[:4])
            if any(rect_overlap(word_rect, h) for h in highlight_rects):
                matched_words.append(w)
        matched_words.sort(key=lambda w: (round(w[1], 1), w[0]))
        lines = []
        current_line_y = None
        current_line = []
        for w in matched_words:
            y = round(w[1], 1)
            if current_line_y is None or abs(y - current_line_y) <= 2:
                current_line.append(w[4])
                current_line_y = y
            else:
                lines.append(" ".join(current_line))
                current_line = [w[4]]
                current_line_y = y
        if current_line:
            lines.append(" ".join(current_line))
        clean_text = "\n".join(line.strip() for line in lines if line.strip())
        if clean_text:
            results[page_number + 1].append(clean_text)
    return results

def split_text(text, max_width, font, font_size):
    words = text.split()
    lines = []
    line = ""
    for word in words:
        test_line = f"{line} {word}".strip()
        if stringWidth(test_line, font, font_size) <= max_width:
            line = test_line
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines

def write_to_pdf(highlight_dict, output_path):
    c = canvas.Canvas(output_path, pagesize=LETTER)
    width, height = LETTER
    margin_left = 0.5 * inch
    margin_top = 0.5 * inch
    max_width = width - 1 * inch
    y = height - margin_top
    font = "Helvetica"
    font_bold = "Helvetica-Bold"
    font_size = 10.5
    line_height = 13

    for page, blocks in sorted(highlight_dict.items()):
        c.setFont(font_bold, 12)
        c.drawString(margin_left, y, f"Page {page}")
        y -= line_height
        c.setFont(font, font_size)
        for block in blocks:
            for paragraph in block.strip().split("\n"):
                lines = split_text(paragraph.strip(), max_width, font, font_size)
                for line in lines:
                    if y < margin_top + line_height:
                        c.showPage()
                        y = height - margin_top
                        c.setFont(font, font_size)
                    c.drawString(margin_left, y, line)
                    y -= line_height
                y -= line_height  # extra space between paragraphs
        y -= line_height * 2  # extra space after each page
        if y < margin_top + line_height:
            c.showPage()
            y = height - margin_top
    c.save()

def main():
    # Ensure two arguments are provided: input and output
    if len(sys.argv) < 3:
        print("Usage: pdf.py input.pdf output.pdf")
        return

    INPUT_PDF = sys.argv[1]
    OUTPUT_PDF = sys.argv[2]

    if not os.path.isfile(INPUT_PDF):
        print(f"File not found: {INPUT_PDF}")
        return

    doc = fitz.open(INPUT_PDF)
    highlights = extract_highlighted_text_layout_aware(doc)
    doc.close()
    if not highlights:
        print("No highlighted text found.")
        return
    write_to_pdf(highlights, OUTPUT_PDF)
    print(f"Formatted highlights saved to {OUTPUT_PDF}")

if __name__ == "__main__":
    main()
