import json

from checks import (
    check_completeness, check_country, check_formats, check_documents,
    check_identity, check_name_match, check_duplicates,
)
from config import FIX, RED, REVIEW, RULE_VERSION


def build_vendor_message(status, sub_status, fixes):
    if status == "Approved":
        return "Your vendor application is approved."
    if status == "Rejected":
        return "We are unable to approve this application. Please contact our support team."
    if sub_status == "In review":
        message = "Your application is under review by our team. We will contact you if we need anything."
    else:
        message = "We need a few changes before we can approve your application."
    if fixes:
        message += " Please fix: " + "; ".join(fixes) + "."
    return message


def decide(stage_results):
    findings = []
    for result in stage_results:
        findings += result["findings"]
    levels = [finding["level"] for finding in findings]
    red_flags = levels.count(RED)
    missing_doc = any(f["code"] in ("MISSING_DOCUMENT", "MISSING_BANK_PROOF") for f in findings)

    if not findings:
        status, sub_status = "Approved", None
    elif red_flags >= 2 or (red_flags >= 1 and missing_doc):
        status, sub_status = "Rejected", None
    elif red_flags == 1 or REVIEW in levels:
        status, sub_status = "Pending", "In review"
    else:
        status, sub_status = "Pending", "Resubmission required"

    fixes = [f["message"] for f in findings if f["level"] == FIX]
    reviewer_notes = [f["message"] for f in findings if f["level"] >= REVIEW]
    return {
        "status": status,
        "sub_status": sub_status,
        "findings": findings,
        "vendor_message": build_vendor_message(status, sub_status, fixes),
        "reviewer_notes": reviewer_notes,
    }


def iter_stages(submission, existing_vendors):
    yield check_completeness(submission)
    yield check_country(submission)
    yield check_formats(submission)
    yield check_documents(submission)
    yield check_identity(submission)
    yield check_name_match(submission)
    yield check_duplicates(submission, existing_vendors)


def build_decision(stages):
    decision = decide(stages)
    decision["stages"] = stages
    decision["rule_version"] = RULE_VERSION
    return decision


def run_pipeline(submission, existing_vendors):
    return build_decision(list(iter_stages(submission, existing_vendors)))

def parse_submission(text):
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        return None, f"The file is not valid JSON ({error.msg}, line {error.lineno}, column {error.colno})"
    if not isinstance(data, dict):
        return None, "The file must contain a single JSON object"
    return data, None