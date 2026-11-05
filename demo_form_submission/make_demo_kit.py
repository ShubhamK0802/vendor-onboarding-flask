"""Builds the form-submission kit for ONE clean vendor: vendor_submission.json, four sample PDFs and a how-to (stdlib only).

Run:  python make_demo_kit.py        (from any folder)

Every PDF is marked SAMPLE across the page and in the footer. They are fictional demo documents, not official records,
and their layout is invented on purpose. The app stores them for the reviewer but does not read their contents.
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from samples import CASES  # noqa: E402

VENDOR = next(case[1] for case in CASES if case[0] == "27_approved_form_demo_vendor")
COMPANY, GSTIN, PAN, ACCOUNT, IFSC = VENDOR["company_name"], VENDOR["tax_id"], VENDOR["pan"], VENDOR["bank_account_number"], VENDOR["bank_code"]
ADDRESS = VENDOR["address"]


# ---------------------------------------------------------------- a tiny PDF writer (one A4 page, Helvetica)

def esc(s):
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def text(x, y, size, s, bold=False, gray=0):
    return f"BT /{'F2' if bold else 'F1'} {size} Tf {gray} g {x} {y} Td ({esc(s)}) Tj ET"


def rect(x, y, w, h, width=1):
    return f"{width} w {x} {y} {w} {h} re S"


def line(x1, y1, x2, y2, width=0.5):
    return f"{width} w {x1} {y1} m {x2} {y2} l S"


def watermark(word="SAMPLE"):
    return f"q 0.9 g 0.7071 0.7071 -0.7071 0.7071 110 250 cm BT /F2 120 Tf 0 0 Td ({word}) Tj ET Q"


def footer():
    return [text(50, 36, 8, "SAMPLE DOCUMENT FOR DEMONSTRATION ONLY - FICTIONAL DATA - NOT AN OFFICIAL RECORD", gray=0.35)]


def write_pdf(name, commands):
    content = "\n".join(commands).encode("latin-1")
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
               b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream"]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1) + b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    with open(os.path.join(HERE, name), "wb") as handle:
        handle.write(out)
    return len(out)


def fields(rows, top=640, left=60, gap=30):
    out = []
    for number, (label, value) in enumerate(rows):
        y = top - number * gap
        out += [text(left, y, 9, label.upper(), gray=0.4), text(left + 190, y, 12, value, bold=True), line(left, y - 8, 535, y - 8, 0.3)]
    return out


# ---------------------------------------------------------------- the four documents

def tax_document():
    return [watermark(), rect(40, 60, 515, 740, 1.5), text(150, 760, 18, "GST REGISTRATION CERTIFICATE", bold=True), text(180, 738, 10, "(sample layout, not an official form)", gray=0.4),
            *fields([("GSTIN", GSTIN), ("PAN", PAN), ("Legal name", COMPANY), ("Trade name", COMPANY), ("Constitution", "Private Limited Company"),
                     ("Principal place of business", ADDRESS), ("Date of registration", "01/04/2019"), ("Type of registration", "Regular"), ("Status", "Active")], top=690),
            text(360, 150, 10, "Proper Officer (sample)"), line(340, 165, 530, 165), *footer()]


def registration_certificate():
    return [watermark(), rect(40, 60, 515, 740, 1.5), rect(48, 68, 499, 724, 0.5), text(140, 740, 20, "CERTIFICATE OF INCORPORATION", bold=True),
            text(210, 716, 10, "(sample layout, not an official form)", gray=0.4),
            text(70, 650, 12, "This is to certify that"), text(70, 620, 18, COMPANY, bold=True),
            text(70, 590, 12, "is incorporated on 12 March 2018 and is a company limited by shares."),
            *fields([("Company identification no.", "U17110MH2018PTC123456"), ("PAN", PAN), ("Date of incorporation", "12/03/2018"), ("Registered office", ADDRESS)], top=520),
            text(360, 150, 10, "Registrar of Companies (sample)"), line(340, 165, 530, 165), *footer()]


def voided_cheque():
    return [watermark("VOID"), rect(50, 520, 495, 230, 1.5), text(70, 722, 16, "SAMPLE BANK OF INDIA", bold=True), text(70, 706, 9, "Industrial Estate Branch, Pune 411019", gray=0.4),
            text(400, 722, 10, "DATE  __ __ / __ __ / __ __ __ __"), text(70, 670, 11, "PAY"), line(100, 668, 530, 668), text(70, 640, 11, "RUPEES"), line(120, 638, 430, 638),
            rect(440, 620, 100, 36, 0.8), text(446, 633, 10, "Rs."), text(70, 590, 10, "A/C NO."), text(120, 590, 13, ACCOUNT, bold=True), text(300, 590, 10, "IFSC"), text(330, 590, 13, IFSC, bold=True),
            text(70, 560, 12, COMPANY, bold=True), text(380, 548, 9, "Authorised signatory"), line(360, 560, 530, 560),
            text(70, 532, 11, "C000123C  400002123C  000123  31", gray=0.2), text(50, 490, 10, "Cancelled cheque provided as proof of the bank account.", gray=0.4), *footer()]


def passbook_page():
    return [watermark(), rect(40, 60, 515, 740, 1.5), text(110, 760, 18, "SAMPLE BANK OF INDIA", bold=True), text(110, 738, 11, "Current account passbook, first page (sample)", gray=0.4),
            *fields([("Account holder", COMPANY), ("Account number", ACCOUNT), ("IFSC", IFSC), ("Branch", "Industrial Estate, Pune"), ("Account type", "Current"), ("Opened on", "15/05/2019")], top=690),
            text(60, 460, 10, "DATE", gray=0.4), text(140, 460, 10, "PARTICULARS", gray=0.4), text(400, 460, 10, "AMOUNT (Rs.)", gray=0.4), line(60, 452, 535, 452, 0.8),
            *[c for n, (d, p, a) in enumerate([("15/05/2019", "Account opening deposit", "1,00,000.00 CR"), ("20/05/2019", "Transfer from partner", "50,000.00 CR"),
                                                ("02/06/2019", "Cheque issued", "12,500.00 DR")]) for c in (text(60, 430 - n * 24, 10, d), text(140, 430 - n * 24, 10, p), text(400, 430 - n * 24, 10, a))], *footer()]


DOCUMENTS = {"tax_document": ("1_tax_document_gst_certificate.pdf", tax_document), "registration": ("2_registration_certificate.pdf", registration_certificate),
             "voided_cheque": ("3_voided_cheque.pdf", voided_cheque), "passbook": ("4_passbook_first_page.pdf", passbook_page)}
SLOT_NAMES = {"tax_document": "Tax document", "registration": "Registration document", "voided_cheque": "Voided cheque", "passbook": "Passbook page"}


def main():
    submission = copy.deepcopy(VENDOR)
    for slot, (file_name, draw) in DOCUMENTS.items():
        submission["documents"][slot] = {"filename": file_name, "file_type": "pdf", "size_bytes": write_pdf(file_name, draw()), "declared_type": slot}
    with open(os.path.join(HERE, "vendor_submission.json"), "w", encoding="utf-8") as handle:
        json.dump(submission, handle, indent=2)
    rows = "\n".join(f"| {label} | `{VENDOR[key]}` |" for key, label in [("company_name", "Company name"), ("country", "Country"), ("website", "Website"),
                                                                       ("email", "Email"), ("mobile", "Mobile number"), ("address", "Address"), ("tax_id", "Tax ID (GSTIN)"), ("pan", "PAN"),
                                                                       ("bank_account_name", "Bank account holder name"), ("bank_account_number", "Bank account number"), ("bank_code", "Bank code (IFSC)")])
    uploads = "\n".join(f"| {SLOT_NAMES[slot]} | `{name}` |" for slot, (name, _) in DOCUMENTS.items())
    with open(os.path.join(HERE, "README.md"), "w", encoding="utf-8") as handle:
        handle.write(f"""# Form-submission kit: {COMPANY}

A clean fictional vendor, to fill in the **Vendor form** on the Onboard vendor page. All the data and all four PDFs are made up, and every PDF is
marked SAMPLE. Expected result: **Approved**.

## 1. Type these into the form
| Field | Value |
|---|---|
{rows}

## 2. Upload these PDFs from this folder
| Slot | File |
|---|---|
{uploads}

(The voided cheque and the passbook page are alternatives; uploading both is fine.)

## 3. Or skip the typing
On the **JSON file** tab, upload `vendor_submission.json`. It carries the same values and describes the four documents (the JSON route does not upload the PDFs themselves).

## Make it interesting: change one thing and submit again
| Change | What you should see |
|---|---|
| Bank account holder: `Horizon Textile Private Limited` (one letter off) | Rejected, with what to correct. Fix it and submit a new application: it is approved. (A 4th try for the same company goes to a reviewer, even if perfect.) |
| Bank account number: replace a 0 with the letter `O` | Rejected outright: look-alike characters |
| Leave the tax ID empty and upload no cheque | Rejected with a numbered list of what to correct |
| Submit the exact same form a second time | Approved: already registered (nothing new is created, and the vendor sees no vendor ID) |

A reviewer can open the submission and download these PDFs from **View submission**. The app stores them but does not read them.

Rebuild everything with `python make_demo_kit.py`.
""")
    print("kit written:", ", ".join(name for name, _ in DOCUMENTS.values()), "+ vendor_submission.json + README.md")


if __name__ == "__main__":
    main()
