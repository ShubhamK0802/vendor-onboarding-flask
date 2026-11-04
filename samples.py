import copy
import json
import os

from checks import gstin_check_char
from config import VENDORS_ON_FILE

with open("sample_inputs/01_clean_india.json") as handle:
    INDIA = json.load(handle)

US = {
    "company_name": "Brightwave Supplies LLC",
    "entity_type": "company",
    "country": "US",
    "email": "ap@brightwave.example",
    "mobile": "2125550143",
    "address": "250 Hudson Street, New York, NY 10013",
    "tax_id": "12-3456789",
    "bank_account_name": "Brightwave Supplies LLC",
    "bank_account_number": "4400123987",
    "bank_code": "021000021",
    "website": "https://www.brightwave.example",
    "documents": {
        "tax_document": {"filename": "brightwave_w9.pdf", "file_type": "pdf", "size_bytes": 150000, "declared_type": "tax_document"},
        "registration": {"filename": "brightwave_articles.pdf", "file_type": "pdf", "size_bytes": 210000, "declared_type": "registration"},
        "voided_cheque": {"filename": "brightwave_cheque.pdf", "file_type": "pdf", "size_bytes": 90000, "declared_type": "voided_cheque"},
        "passbook": None,
    },
}

ORION = VENDORS_ON_FILE[0]

APEX = {
    "company_key": "ABCCA1234D",
    "company_name": "Apex Global Private Limited",
    "bank_account_number": "50100234567891",
    "mobile": "9876501234",
    "email": "accounts@apexglobal.example",
}

SEED = [ORION]

def fresh(d, name, pan, account, mobile=None, email=None, us=False):
    """Give a sample its own company, so samples never collide with each other (only 10 and 13 reuse Apex on purpose)."""
    slug = name.split()[0].lower()
    d.update(company_name=name, bank_account_name=name, bank_account_number=account, mobile=mobile or "98" + account[-8:], email=email or f"ap@{slug}.example")
    if us:
        d["tax_id"] = pan
    else:
        d.update(pan=pan, tax_id="27" + pan + "1Z" + gstin_check_char("27" + pan + "1Z"))
    return d


def short_tax_id(d):
    d["tax_id"] = d["tax_id"][:13]


CASES = [
    ("01_clean_india", INDIA, lambda d: None, SEED, "Approved", None),
    ("02_clean_us", US, lambda d: None, SEED, "Approved", None),
    ("03_short_tax_id", INDIA, lambda d: (fresh(d, "Kestrel Fabrics Private Limited", "KESCF2345K", "71000123456701"), short_tax_id(d)), SEED, "Pending", "Resubmission required"),
    ("04_wrong_document_slot", INDIA, lambda d: (fresh(d, "Delta Pumps Private Limited", "DELCP3456L", "72000123456702"), d["documents"]["registration"].update(declared_type="tax_document")), SEED, "Pending", "Resubmission required"),
    ("05_suffix_spelling", INDIA, lambda d: (fresh(d, "Sundara Textiles Private Limited", "SUNCT4567M", "73000123456703"), d.update(bank_account_name="Sundara Textiles Pvt. Ltd.")), SEED, "Approved", None),
    ("06_near_miss_name", INDIA, lambda d: (fresh(d, "Lumina Global Private Limited", "LUMCG5678N", "74000123456704"), d.update(bank_account_name="Lumina Globe Private Limited")), SEED, "Pending", "In review"),
    ("07_shared_bank_account", INDIA, lambda d: fresh(d, "Harbor Freight Private Limited", "HARCF6789P", "60200345678912"), SEED, "Pending", "In review"),
    ("08_unsupported_country", INDIA, lambda d: (fresh(d, "Atlas Metals Private Limited", "ATLCM7890Q", "75000123456705"), d.update(country="BR")), SEED, "Pending", "In review"),
    ("09_missing_doc_and_holder_mismatch", INDIA, lambda d: (fresh(d, "Birch Papers Private Limited", "BIRCP8901R", "76000123456706"), d["documents"].update(voided_cheque=None), d.update(bank_account_name="Zenith Traders")), SEED, "Rejected", None),
    ("10_existing_vendor_resubmits", INDIA, lambda d: d.update(address="14 MG Road, Bengaluru, Karnataka 560001"), SEED + [APEX], "Pending", "In review"),
    ("12_identity_fields_contradict", INDIA, lambda d: (fresh(d, "Cobalt Tools Private Limited", "COBCT9012S", "77000123456707"), d.update(pan="ZZZZZ9999Z")), SEED, "Rejected", None),
    ("13_company_id_new_name", INDIA, lambda d: d.update(company_name="Apex Holdings", bank_account_name="Apex Holdings"), SEED + [APEX], "Pending", "In review"),
    ("14_us_vendor_indian_tax_id", US, lambda d: (fresh(d, "Redwood Supply LLC", "29ABCCA1234D1Z6", "4400555111", mobile="3105550188", us=True)), SEED, "Pending", "In review"),
    ("15_shared_contact", INDIA, lambda d: fresh(d, "Quill Stationers Private Limited", "QUICS0123T", "78000123456708", mobile="9000011111"), SEED, "Pending", "In review"),
]


def write_samples():
    os.makedirs("sample_inputs", exist_ok=True)
    for name, base, edit, history, status, sub_status in CASES:
        data = copy.deepcopy(base)
        edit(data)
        with open(f"sample_inputs/{name}.json", "w") as handle:
            json.dump(data, handle, indent=2)
    with open("sample_inputs/11_malformed.json", "w") as handle:
        handle.write('{"company_name": "Apex Global",')


if __name__ == "__main__":
    write_samples()
    print("sample files written")