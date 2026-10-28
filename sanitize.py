"""Code defense layer: turn a vendor document into only what a human would see.

Runs before any model sees the document. Hidden text is removed and reported
in the audit trail, but never passed to the model.

  HTML  drops <script>, <style>, comments, and elements hidden by inline style or by
        a <style> rule (display:none, visibility:hidden, opacity:0, tiny or zero font,
        white text, pushed off screen, clipped, collapsed to zero size)
  PDF   walks the page's drawing commands and keeps only text that is on the page,
        at least 4pt, not white, and actually painted (render mode 3 and 7 are invisible).
        A page that is mostly one big image is a scan: its text layer is untrusted, so
        it is dropped and the page image is handed to the model to read instead.
  EML   reads the HTML part (what mail apps show) through the HTML cleaner, and checks
        that the plain-text part states the same SKUs, prices, and quantities.
        If the two copies disagree, the email is flagged for human review.
  All   strips zero-width, bidi-control, and Unicode "tag" characters
"""

import email
import io
import re
from dataclasses import dataclass, field
from email import policy
from pathlib import Path

from bs4 import BeautifulSoup, Comment
from pypdf import PdfReader
from pypdf.generic import ContentStream

MIN_FONT_PX = 6     # HTML
MIN_FONT_PT = 4     # PDF
SCAN_COVERAGE = 0.5  # an image covering half the page or more makes it a scanned page
INVISIBLE_CHARS = re.compile("[​-‏⁠-⁤﻿­‪-‮\U000e0000-\U000e007f]")
HIDING_STYLE = re.compile(
    r"display\s*:\s*none|visibility\s*:\s*hidden|opacity\s*:\s*0(\.0*)?\s*(;|$|!)"
    r"|color\s*:\s*(#fff\b|#ffffff\b|white\b|rgba?\(\s*255\s*,\s*255\s*,\s*255)"
    r"|(left|top|right|text-indent|margin-left)\s*:\s*-\s*\d{3,}"
    r"|clip(-path)?\s*:\s*(rect\(\s*0|inset\(\s*(50|100)%)"
    r"|(^|;)\s*(max-)?(height|width)\s*:\s*0(px)?\s*(;|$)"
    r"|transform\s*:\s*scale\(\s*0",
    re.IGNORECASE,
)
FONT_SIZE = re.compile(r"font-size\s*:\s*([\d.]+)\s*(px|pt|em|rem)?", re.IGNORECASE)
CSS_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
# Facts compared between the two copies of an email.
FACTS = re.compile(r"CC-[A-Z]{2}-\d{3}|\$\s?[\d,]+(?:\.\d+)?|\b\d[\d,]*\s*(?:units?|pcs|pieces|days?)\b",
                   re.IGNORECASE)


@dataclass
class CleanDoc:
    text: str
    removed: list[str] = field(default_factory=list)  # what was taken out, for the audit trail
    images: list[bytes] = field(default_factory=list)  # PNG page images the model should read
    flags: list[str] = field(default_factory=list)     # problems that need a human (design layer)


def _short(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= 160 else text[:157] + "..."


def _hidden_by_style(style: str) -> str | None:
    if m := HIDING_STYLE.search(style):
        return m.group(0).strip(" ;")
    if m := FONT_SIZE.search(style):
        size, unit = float(m.group(1)), (m.group(2) or "px").lower()
        px = size * {"px": 1, "pt": 4 / 3, "em": 16, "rem": 16}[unit]
        if px < MIN_FONT_PX:
            return m.group(0)
    return None


def _stylesheet_hidden(soup: BeautifulSoup) -> list[tuple[str, str]]:
    """(selector, why) for <style> rules that hide what they match."""
    rules = []
    for style in soup.find_all("style"):
        css = re.sub(r"/\*.*?\*/", "", style.get_text(), flags=re.S)
        for selectors, body in CSS_RULE.findall(css):
            why = _hidden_by_style(body)
            if why:
                rules += [(s.strip(), why) for s in selectors.split(",") if s.strip()]
    return rules


def clean_html(markup: str) -> tuple[str, list[str]]:
    removed = []
    soup = BeautifulSoup(markup, "html.parser")
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        if c.strip():
            removed.append(f"HTML comment: {_short(c)}")
        c.extract()
    for selector, why in _stylesheet_hidden(soup):
        try:
            matches = soup.select(selector)
        except Exception:
            continue
        for tag in matches:
            if tag.name in ("html", "body"):
                continue
            text = tag.get_text(" ", strip=True)
            if text:
                removed.append(f"hidden by stylesheet rule '{selector}' ({why}): {_short(text)}")
            tag.decompose()
    for tag in soup(["script", "style", "noscript", "template", "head"]):
        tag.decompose()
    for tag in soup.find_all(True):
        if tag.decomposed:
            continue
        why = None
        if tag.has_attr("hidden") or tag.get("aria-hidden") == "true":
            why = "hidden attribute"
        elif tag.has_attr("style"):
            why = _hidden_by_style(tag["style"])
        if why:
            text = tag.get_text(" ", strip=True)
            if text:
                removed.append(f"hidden <{tag.name}> ({why}): {_short(text)}")
            tag.decompose()
    return soup.get_text("\n", strip=True), removed


def _mul(m, n):
    a, b, c, d, e, f = m
    a2, b2, c2, d2, e2, f2 = n
    return (a * a2 + b * c2, a * b2 + b * d2, c * a2 + d * c2, c * b2 + d * d2,
            e * a2 + f * c2 + e2, e * b2 + f * d2 + f2)


def _page_png(page) -> bytes | None:
    """The largest image on the page, as PNG bytes."""
    best = None
    for img in page.images:
        pil = img.image
        if best is None or pil.width * pil.height > best.width * best.height:
            best = pil
    if best is None:
        return None
    buf = io.BytesIO()
    best.convert("RGB").save(buf, "PNG")
    return buf.getvalue()


def clean_pdf(path: Path) -> CleanDoc:
    """Keep only painted, visible text. Tracks graphics state (q/Q, cm, rg/g/k),
    font size (Tf), render mode (Tr) and position (Tm/Td/TD/T*) through each page."""
    reader = PdfReader(path)
    doc = CleanDoc(text="")
    kept_all = []
    for n, page in enumerate(reader.pages, 1):
        x0, y0, x1, y1 = (float(v) for v in page.mediabox)
        page_area = (x1 - x0) * (y1 - y0)
        ctm, fill_white, render = (1, 0, 0, 1, 0, 0), False, 0
        size, x, y, leading, line_x = 12.0, 0.0, 0.0, 0.0, 0.0
        stack, kept, removed, image_cover = [], [], [], 0.0
        for operands, op in ContentStream(page.get_contents(), reader).operations:
            op = op.decode() if isinstance(op, bytes) else op
            if op == "q":
                stack.append((ctm, fill_white))
            elif op == "Q" and stack:
                ctm, fill_white = stack.pop()
            elif op == "cm":
                ctm = _mul(tuple(float(v) for v in operands), ctm)
            elif op == "Do":
                # Area this XObject (usually an image) covers on the page.
                image_cover = max(image_cover, abs(ctm[0] * ctm[3] - ctm[1] * ctm[2]) / page_area)
            elif op == "rg":
                fill_white = all(float(v) >= 0.95 for v in operands)
            elif op == "g":
                fill_white = float(operands[0]) >= 0.95
            elif op == "k":
                fill_white = all(float(v) <= 0.05 for v in operands)
            elif op == "Tr":
                render = int(operands[0])
            elif op == "Tf":
                size = float(operands[1])
            elif op == "TL":
                leading = float(operands[0])
            elif op == "BT":
                x = y = line_x = 0.0
            elif op == "Tm":
                x = line_x = float(operands[4])
                y = float(operands[5])
            elif op in ("Td", "TD"):
                line_x += float(operands[0])
                x = line_x
                y += float(operands[1])
                if op == "TD":
                    leading = -float(operands[1])
            elif op == "T*":
                x = line_x
                y -= leading
            elif op in ("Tj", "TJ", "'", '"'):
                arg = operands[-1]
                text = "".join(a for a in arg if isinstance(a, str)) if op == "TJ" else str(arg)
                if not text.strip():
                    continue
                problems = []
                if render in (3, 7):
                    problems.append(f"invisible text, render mode {render}")
                if fill_white:
                    problems.append("white text")
                if size < MIN_FONT_PT:
                    problems.append(f"{size:g}pt font")
                px, py = ctm[0] * x + ctm[2] * y + ctm[4], ctm[1] * x + ctm[3] * y + ctm[5]
                if not (x0 <= px <= x1 and y0 <= py <= y1):
                    problems.append(f"off the page at ({px:g}, {py:g})")
                if problems:
                    removed.append(f"PDF text ({', '.join(problems)}): {_short(text)}")
                else:
                    kept.append(text)
        if image_cover >= SCAN_COVERAGE and (png := _page_png(page)):
            # A scanned page: what a person sees is the picture. Any text layer on top of it
            # (OCR or otherwise) is not what they read, so the model reads the picture instead.
            doc.images.append(png)
            if kept:
                removed.append(f"page {n} text layer over the scan ({len(kept)} lines) not trusted")
            kept = [f"[Page {n} is a scanned image. Read it from the attached page image.]"]
            doc.removed.append(f"page {n} is a scanned image ({image_cover:.0%} of the page); "
                               "page image sent to the model")
        doc.removed += removed
        kept_all += kept
    doc.text = "\n".join(kept_all)
    return doc


def _facts(text: str) -> set[str]:
    return {re.sub(r"[\s,]", "", m).lower().rstrip("s") for m in FACTS.findall(text)}


def clean_eml(path: Path) -> CleanDoc:
    msg = email.message_from_bytes(path.read_bytes(), policy=policy.default)
    headers = "\n".join(f"{h}: {msg[h]}" for h in ("From", "To", "Subject", "Date") if msg[h])
    doc = CleanDoc(text="")
    plain = msg.get_body(preferencelist=("plain",))
    html = msg.get_body(preferencelist=("html",))
    if html is not None:
        # Mail apps display the HTML part, so that is what the buyer reads.
        body, doc.removed = clean_html(html.get_content())
        if plain is not None:
            seen, unseen = _facts(body), _facts(plain.get_content())
            if seen != unseen:
                only_plain = sorted(unseen - seen)
                only_html = sorted(seen - unseen)
                doc.flags.append(
                    f"email copies disagree: the hidden plain-text copy says {only_plain or 'nothing extra'}, "
                    f"the displayed copy says {only_html or 'nothing extra'}"
                )
                doc.removed.append(f"plain-text part ignored; differs from displayed HTML ({only_plain})")
            else:
                doc.removed.append("plain-text part matches displayed HTML")
    elif plain is not None:
        body = plain.get_content()
    else:
        body = ""
    for part in msg.iter_attachments():
        doc.removed.append(f"attachment not read: {part.get_filename()}")
    doc.text = f"{headers}\n\n{body}"
    return doc


def clean_document(path: Path) -> CleanDoc:
    """Return what a person would see: visible text, page images, and what was removed."""
    suffix = path.suffix.lower()
    if suffix in (".html", ".htm"):
        text, removed = clean_html(path.read_text(encoding="utf-8", errors="replace"))
        doc = CleanDoc(text, removed)
    elif suffix == ".pdf":
        doc = clean_pdf(path)
    elif suffix == ".eml":
        doc = clean_eml(path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")
    n = len(INVISIBLE_CHARS.findall(doc.text))
    if n:
        doc.removed.append(f"{n} invisible Unicode characters")
        doc.text = INVISIBLE_CHARS.sub("", doc.text)
    return doc
