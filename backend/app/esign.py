"""E-signature: each approval is a SHA-256 hash chained to the previous one, and is rendered as a
stamped approval-trail page appended to the PDF (plus a footer on every page)."""
import hashlib
import io
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def file_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sign_hash(prev_hash: str, file_hash: str, approver_id: int, acted_at, decision: str, comment: str) -> str:
    raw = f"{prev_hash}|{file_hash}|{approver_id}|{acted_at.isoformat()}|{decision}|{comment}"
    return hashlib.sha256(raw.encode()).hexdigest()


def verify_chain(steps, version_hashes: dict[int, str]) -> bool:
    prev = ""
    for s in steps:
        if s.status != "approved":
            continue
        if s.prev_hash != prev:
            return False
        if sign_hash(prev, version_hashes.get(s.version, ""), s.approver_id, s.acted_at, "approved", s.comment) != s.signature_hash:
            return False
        prev = s.signature_hash
    return True


def _footer(width, height, text):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))
    c.setFont("Helvetica", 6.5)
    c.setFillColor(colors.HexColor("#2e7d32"))
    c.drawString(24, 12, text)
    c.save()
    buf.seek(0)
    return PdfReader(buf).pages[0]


def build_signed_pdf(original: bytes, sheet, approved_steps, final: bool, stamped: bool) -> bytes:
    reader = PdfReader(io.BytesIO(original))
    writer = PdfWriter()
    tag = f"{sheet.ref} | v{sheet.version} | {len(approved_steps)} e-signature(s) | " + (
        "FINAL - approved by Dean Student Welfare" if final else "IN PROGRESS - not final")
    for p in reader.pages:
        page = writer.add_page(p)
        page.merge_page(_footer(float(p.mediabox.width), float(p.mediabox.height), tag))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=40, bottomMargin=40)
    ss = getSampleStyleSheet()
    small = ss["BodyText"].clone("small")
    small.fontSize, small.leading = 8, 10
    story = [
        Paragraph(f"Approval Trail - {sheet.ref}", ss["Title"]),
        Paragraph(f"<b>{sheet.title}</b><br/>{sheet.club.name} | Event date: {sheet.event_date} | Venue: {sheet.venue or '-'}", ss["BodyText"]),
        Spacer(1, 10),
    ]
    rows = [["#", "Signed by", "Designation", "Date / time (UTC)", "Version", "Remarks", "Signature ID"]]
    for i, s in enumerate(approved_steps, 1):
        rows.append([
            str(i), Paragraph(f"{s.approver.name}<br/>{s.approver.email}", small), Paragraph(s.approver.designation or "-", small),
            s.acted_at.strftime("%Y-%m-%d %H:%M"), f"v{s.version}", Paragraph(s.comment or "-", small), s.signature_hash[:16],
        ])
    if len(rows) == 1:
        rows.append(["-", "No signatures yet", "", "", "", "", ""])
    t = Table(rows, colWidths=[18, 110, 100, 72, 34, 110, 90], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2e7d32")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5), ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("FONTNAME", (-1, 1), (-1, -1), "Courier"),
    ]))
    story += [t, Spacer(1, 14)]
    status = "FINAL - approved. Print, stamp and issue at the DSW office." if final else "Approval in progress."
    if stamped:
        status = "FINAL - printed and stamped by the DSW office."
    story.append(Paragraph(f"<b>Status:</b> {status}", ss["BodyText"]))
    story.append(Paragraph("Each Signature ID is a SHA-256 hash chained to the previous signature and the document hash; "
                           "any later change to the file or the trail breaks verification in the portal.", small))
    doc.build(story)
    buf.seek(0)
    for p in PdfReader(buf).pages:
        writer.add_page(p)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
