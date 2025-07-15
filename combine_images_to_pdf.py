import os
import re
from PIL import Image
Image.MAX_IMAGE_PIXELS = None  # disables limit (use with caution if PDFs are trusted)
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader

# === CONFIG ===
case_number = os.environ.get("COURT_CASE_NUMBER", "Unfiled")
file_name = os.environ.get("FILE_NAME", "")
base_dir = os.path.dirname(os.path.abspath(__file__))
input_dir = os.path.join(base_dir, "temp_pages")
output_dir = os.path.join("U:\\docketwatch\\docs\\cases", case_number)
os.makedirs(output_dir, exist_ok=True)
output_pdf = os.path.join(output_dir, f"E{case_number}.pdf")

# Ensure output folder exists
os.makedirs(output_dir, exist_ok=True)

print(f"Looking for images in: {input_dir}")
print(f"Case number: {case_number}")
print(f"File name: {file_name}")

# === Collect and sort all page images ===
if not os.path.exists(input_dir):
    
    print(f"Input directory does not exist: {input_dir}")
    exit(1)

# Look for files with the correct pattern using FILE_NAME
files = [f for f in os.listdir(input_dir) if f.startswith(f"{file_name}_page_") and f.endswith(".png")]

print(f"Found {len(files)} image files:")
for f in files:
    print(f"  - {f}")

files.sort(key=lambda f: int(re.search(r"page_(\d+)", f).group(1)))

if not files:
    print("No images found.")
    print(f"Available files in {input_dir}:")
    for f in os.listdir(input_dir):
        print(f"  - {f}")
    exit(1)

print(f"Creating PDF: {output_pdf}")
c = canvas.Canvas(output_pdf, pagesize=letter)
page_width, page_height = letter

pages_processed = 0
for filename in files:
    path = os.path.join(input_dir, filename)
    try:
        print(f"Processing: {filename}")
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
        pages_processed += 1
        
    except Exception as e:
        print(f"Error processing {filename}: {e}")
        continue

if pages_processed == 0:
    print("No pages were processed successfully. PDF not created.")
    exit(1)

c.save()
print(f"PDF saved to: {output_pdf}")
print(f"Pages processed: {pages_processed}")

# Verify PDF was created
if os.path.exists(output_pdf):
    file_size = os.path.getsize(output_pdf)
    print(f"PDF file size: {file_size} bytes")
    if file_size > 0:
        print("PDF creation successful!")
    else:
        print("PDF file is empty!")
else:
    print("PDF file was not created!")

# === Cleanup ===
for filename in files:
    try:
        os.remove(os.path.join(input_dir, filename))
    except Exception as e:
        print(f"Error deleting {filename}: {e}")
print("PNGs deleted.")
