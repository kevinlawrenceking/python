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
page_width, page_height = letter

for filename in files:
    path = os.path.join(input_dir, filename)
    try:
        img = Image.open(path)
        img_width, img_height = img.size
        
        # Calculate scaling to fit letter size while maintaining aspect ratio
        scale_x = page_width / img_width
        scale_y = page_height / img_height
        scale = min(scale_x, scale_y)
        
        # Calculate centered position
        scaled_width = img_width * scale
        scaled_height = img_height * scale
        x = (page_width - scaled_width) / 2
        y = (page_height - scaled_height) / 2
        
        # Create new page with letter size
        c.setPageSize(letter)
        c.drawImage(ImageReader(img), x, y, width=scaled_width, height=scaled_height)
        c.showPage()
        
    except Exception as e:
        print(f"Error processing {filename}: {e}")
        continue

c.save()
print(f"PDF saved to: {output_pdf}")

# === Cleanup ===
for filename in files:
    try:
        os.remove(os.path.join(input_dir, filename))
    except Exception as e:
        print(f"Error deleting {filename}: {e}")
print("PNGs deleted.")
