# Form-submission kit: Horizon Textiles Private Limited

A clean fictional vendor, to fill in the **Vendor form** on the Onboard vendor page. All the data and all four PDFs are made up, and every PDF is
marked SAMPLE. Expected result: **Approved**.

## 1. Type these into the form
| Field | Value |
|---|---|
| Company name | `Horizon Textiles Private Limited` |
| Entity type | `company` |
| Country | `IN` |
| Website | `https://www.horizon.example` |
| Email | `accounts@horizontextiles.example` |
| Mobile number | `9822012345` |
| Address | `Plot 21, Industrial Estate, Pune, Maharashtra 411019` |
| Tax ID (GSTIN) | `27HORCH7421J1Z4` |
| PAN | `HORCH7421J` |
| Bank account holder name | `Horizon Textiles Private Limited` |
| Bank account number | `83000123456715` |
| Bank code (IFSC) | `ICIC0001234` |

## 2. Upload these PDFs from this folder
| Slot | File |
|---|---|
| Tax document | `1_tax_document_gst_certificate.pdf` |
| Registration document | `2_registration_certificate.pdf` |
| Voided cheque | `3_voided_cheque.pdf` |
| Passbook page | `4_passbook_first_page.pdf` |

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
