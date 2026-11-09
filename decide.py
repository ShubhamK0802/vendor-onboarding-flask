import json

from checks import (
    check_completeness, check_country, check_formats, check_documents,
    check_identity, check_name_match, check_verification, check_duplicates, check_attempts,
)
from config import ALREADY_REGISTERED, FIX, NEEDS_REVIEW, NO_RETRY_CODES, RED, REJECT_ON_ITS_OWN, REVIEW, RULE_VERSION


def build_vendor_message(status, sub_status, fixes, reject_reasons=(), contradictions=(), can_retry=True):
    if status == "Approved":
        return "You are already registered with us. No new application is needed." if sub_status == ALREADY_REGISTERED else "Your application is approved."
    if status == "Pending" and sub_status == NEEDS_REVIEW:
        return "Your application is under review. We will reach back to you if anything is needed."
    parts = []
    if reject_reasons:
        parts.append("Your application is rejected because " + "; ".join(reject_reasons) + ".")
    if contradictions:  # name the details that disagree, in the same plain words the vendor sees everywhere else
        lead = "Some of the details you entered also do not agree with each other:" if reject_reasons else "Your application is rejected because some of the details you entered do not agree with each other:"
        parts.append(lead + "\n" + "\n".join(f"{i}. {item}" for i, item in enumerate(contradictions, 1)))
    if not parts and fixes:  # nothing hard-stopped it: the vendor simply got some details wrong or missed some
        problems = "this problem" if len(fixes) == 1 else "these problems"
        parts.append(f"Your application is rejected. We found {problems}:\n" + "\n".join(f"{i}. {fix}" for i, fix in enumerate(fixes, 1)))
    if not parts:
        parts.append("Your application is rejected.")
    parts.append("This application is now closed." + (" Please correct the details and submit a new application." if can_retry else ""))
    return "\n".join(parts)


def decide(stage_results):
    findings = []
    for result in stage_results:
        findings += result["findings"]
    levels = [finding["level"] for finding in findings]
    red_flags = levels.count(RED)
    reject_reasons = list(dict.fromkeys(REJECT_ON_ITS_OWN[f["code"]] for f in findings if f["code"] in REJECT_ON_ITS_OWN))

    if not findings:
        status, sub_status = "Approved", None
    elif all(f["code"] == "DUPLICATE_APPLICATION" for f in findings):  # an exact repeat of an onboarded vendor: nothing to decide, nothing new to create
        status, sub_status = "Approved", ALREADY_REGISTERED
    elif reject_reasons or red_flags >= 2:
        status, sub_status = "Rejected", None
    elif REVIEW in levels:
        status, sub_status = "Pending", NEEDS_REVIEW
    else:  # wrong or missing input: rejected and closed; the vendor files a new application, which is checked from scratch
        status, sub_status = "Rejected", None

    contradictions = [f["message"] for f in findings if f["level"] == RED] if status == "Rejected" and red_flags >= 2 else []
    can_retry = not any(f["code"] in NO_RETRY_CODES for f in findings)
    fixes = [f["message"] for f in findings if f["level"] in (FIX, RED)]
    reviewer_notes = [f["message"] for f in findings if f["level"] >= REVIEW]
    return {
        "status": status,
        "sub_status": sub_status,
        "findings": findings,
        "vendor_message": build_vendor_message(status, sub_status, fixes, reject_reasons, contradictions, can_retry),
        "reviewer_notes": reviewer_notes,
    }


def iter_stages(submission, existing_vendors, history=()):
    yield check_completeness(submission)
    yield check_country(submission)
    yield check_formats(submission)
    yield check_documents(submission)
    yield check_identity(submission)
    yield check_name_match(submission)
    yield check_verification(submission)
    yield check_duplicates(submission, existing_vendors)
    attempts = check_attempts(submission, history, existing_vendors)
    if attempts["status"] != "skipped":  # shown only when there is an earlier attempt to compare with
        yield attempts


def build_decision(stages):
    decision = decide(stages)
    decision["stages"] = stages
    decision["rule_version"] = RULE_VERSION
    return decision


def run_pipeline(submission, existing_vendors, history=()):
    return build_decision(list(iter_stages(submission, existing_vendors, history)))

def parse_submission(text):
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        return None, f"The file is not valid JSON ({error.msg}, line {error.lineno}, column {error.colno})"
    if not isinstance(data, dict):
        return None, "The file must contain a single JSON object"
    return data, None
