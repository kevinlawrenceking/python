import os
import re
from PIL import Image
Image.MAX_IMAGE_PIXELS = None  # disables limit (use with caution if PDFs are trusted)
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader

# === CONFIG ===
case_number = os.environ.get("COURT_CASE_NUMBER", "Unfiled")
base_dir = os.path.dirname(os.path.abspath(__file__))
input_dir = os.path.join(base_dir, "temp_pages")
output_dir = os.path.join("U:\\docketwatch\\docs\\cases", case_number)
os.makedirs(output_dir, exist_ok=True)
output_pdf = os.path.join(output_dir, f"E{case_number}.pdf")

# Ensure output folder exists
os.makedirs(output_dir, exist_ok=True)

# === Collect and sort all page images ===
files = [f for f in os.listdir(input_dir) if f.startswith(f"{case_number}_page_") and f.endswith(".png")]

files.sort(key=lambda f: int(re.search(r"page_(\d+)", f).group(1)))

if not files:
    print("No images found.")
    exit()

print(f"Creating PDF: {output_pdf}")
c = canvas.Canvas(output_pdf, pagesize=letter)

for filename in files:
    path = os.path.join(input_dir, filename)
    img = Image.open(path)
    width, height = img.size

    # Convert pixel dimensions to points (1 pt = 1/72 inch)
    c.setPageSize((width, height))
    c.drawImage(ImageReader(img), 0, 0, width=width, height=height)
    c.showPage()

c.save()
print(f"PDF saved to: {output_pdf}")

# === Cleanup ===
for filename in files:
    os.remove(os.path.join(input_dir, filename))
print("PNGs deleted.")
