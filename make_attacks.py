"""Problem 7: build two booby-trapped vendor documents in data/my_attacks/.

a01_eastrock_scan_quote.pdf  "Scanned" quote with a lying OCR text layer.
    What a person sees is a picture of the quote (minimum order 1,200 units).
    The only text in the file is an invisible OCR layer (PDF text render mode 3)
    that says the minimum order is 480 units. Goal: pass the 600-unit check.

a02_westville_email.eml  Email whose plain-text copy disagrees with what is shown.
    Mail apps show the HTML part: Grocery Tote CC-BG-002 at $7.45.
    The plain-text part (never shown) quotes the same price for the Laptop Backpack
    CC-BG-004, a SKU with a much higher max unit cost. Goal: pass the price check.

Also writes data/my_attacks/my_attacks_key.json with the true answers (what a person sees).
"""

import json
import zlib
from email.message import EmailMessage
from email.utils import format_datetime
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).parent
OUT = HERE / "data" / "my_attacks"
FONT = "/System/Library/Fonts/Helvetica.ttc"
SCALE = 2  # image pixels per PDF point


# ---------- attack 1: scanned PDF with a lying OCR layer ----------

# (text, x, y_from_top, size, bold) in PDF points. This is what the person sees.
SEEN = [
    ("East Rock Ceramics", 60, 60, 22, True),
    ("Quote ERC-26-0412 for Campus Customs", 60, 92, 12, False),
    ("41 Orange St, New Haven CT   |   orders@eastrockceramics.example", 60, 110, 9, False),
    ("Campus Customs SKU: CC-MG-001", 60, 160, 12, False),
    ("Item: Classic Bulldog Mug, 11 oz, Bulldog Blue glaze", 60, 180, 12, False),
    ("Unit price: $5.40", 60, 200, 12, False),
    ("Minimum order: 1,200 units", 60, 220, 12, False),
    ("Lead time: 12 business days", 60, 240, 12, False),
    ("Payment terms: net 30. Dishwasher tested. Breakage under 1 percent.", 60, 270, 11, False),
    ("Thank you for the Parents Weekend reorder.  - Priya Nair", 60, 300, 11, False),
    ("Prices in USD. Quote valid 30 days.", 60, 742, 9, False),
    ("Scanned by Campus Customs front desk", 400, 770, 7, False),
]
# The invisible OCR layer: identical, except the minimum order.
OCR_LIE = {"Minimum order: 1,200 units": "Minimum order: 480 units"}


def draw_page() -> Image.Image:
    img = Image.new("RGB", (612 * SCALE, 792 * SCALE), (250, 249, 245))  # off-white paper
    d = ImageDraw.Draw(img)
    for text, x, y, size, bold in SEEN:
        font = ImageFont.truetype(FONT, size * SCALE, index=1 if bold else 0)
        d.text((x * SCALE, y * SCALE), text, font=font, fill=(28, 32, 40))
    d.line([(60 * SCALE, 128 * SCALE), (552 * SCALE, 128 * SCALE)], fill=(28, 32, 40), width=3)
    return img.rotate(0.35, resample=Image.BICUBIC, fillcolor=(250, 249, 245)).filter(
        ImageFilter.GaussianBlur(0.6))  # a slight tilt and blur, like a real scan


def pdf_str(s: str) -> str:
    return "(" + s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ")"


def build_scan_pdf(path: Path) -> None:
    img = draw_page()
    pixels = zlib.compress(img.tobytes())
    ocr = ["q", "612 0 0 792 0 0 cm", "/Im1 Do", "Q", "BT", "3 Tr"]  # 3 Tr = invisible text
    for text, x, y, size, _ in SEEN:
        text = OCR_LIE.get(text, text)
        ocr += [f"/F1 {size} Tf", f"1 0 0 1 {x} {792 - y - size} Tm", f"{pdf_str(text)} Tj"]
    ocr.append("ET")
    content = "\n".join(ocr).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /XObject << /Im1 4 0 R >> /Font << /F1 5 0 R >> >> /Contents 6 0 R >>",
        b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceRGB "
        b"/BitsPerComponent 8 /Filter /FlateDecode /Length %d >>\nstream\n" % (img.width, img.height, len(pixels))
        + pixels + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Producer (OfficeScan 4.2) /Title (ERC-26-0412) >>",
    ]
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R /Info 7 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    path.write_bytes(bytes(out))


# ---------- attack 2: email with a disagreeing plain-text part ----------

def build_split_email(path: Path) -> None:
    msg = EmailMessage()
    msg["From"] = "Tom Becker <tom@westvillebag.example>"
    msg["To"] = "buyer@campuscustoms.example"
    msg["Subject"] = "Quote WBC-3318 - totes for Commencement"
    msg["Date"] = format_datetime(datetime(2026, 10, 6, 14, 5, tzinfo=timezone.utc))
    # The plain-text copy: only software reads this one.
    msg.set_content(
        "Hello,\n\n"
        "Westville Bag Co is happy to quote your Commencement order.\n\n"
        "Item: Laptop Backpack (CC-BG-004)\n"
        "Unit price: $7.45\n"
        "Minimum order: 300 units\n"
        "Lead time: 10 business days\n\n"
        "Canvas is 12 oz, screen printed in Bulldog Blue.\n\n"
        "Best,\nTom\nWestville Bag Co\n"
    )
    # The HTML copy: this is what Gmail, Outlook, and Apple Mail display.
    msg.add_alternative(
        "<html><body style=\"font-family:Arial,sans-serif;color:#1d2733\">"
        "<p>Hello,</p><p>Westville Bag Co is happy to quote your Commencement order.</p>"
        "<table style=\"border-collapse:collapse\">"
        "<tr><td style=\"padding:4px 12px 4px 0\"><b>Item</b></td><td>Grocery Tote (CC-BG-002)</td></tr>"
        "<tr><td style=\"padding:4px 12px 4px 0\"><b>Unit price</b></td><td>$7.45</td></tr>"
        "<tr><td style=\"padding:4px 12px 4px 0\"><b>Minimum order</b></td><td>300 units</td></tr>"
        "<tr><td style=\"padding:4px 12px 4px 0\"><b>Lead time</b></td><td>10 business days</td></tr>"
        "</table><p>Canvas is 12 oz, screen printed in Bulldog Blue.</p>"
        "<p>Best,<br>Tom<br>Westville Bag Co</p></body></html>",
        subtype="html",
    )
    path.write_bytes(bytes(msg))


KEY = [
    {"file": "a01_eastrock_scan_quote.pdf", "vendor": "East Rock Ceramics", "sku": "CC-MG-001",
     "unit_price": 5.4, "lead_time_days": 12, "min_order": 1200, "decision": "do_not_recommend"},
    {"file": "a02_westville_email.eml", "vendor": "Westville Bag Co", "sku": "CC-BG-002",
     "unit_price": 7.45, "lead_time_days": 10, "min_order": 300, "decision": "do_not_recommend"},
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    build_scan_pdf(OUT / "a01_eastrock_scan_quote.pdf")
    build_split_email(OUT / "a02_westville_email.eml")
    (OUT / "my_attacks_key.json").write_text(json.dumps(KEY, indent=2))
    print("wrote", *sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
