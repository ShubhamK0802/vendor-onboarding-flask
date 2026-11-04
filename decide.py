import json

from checks import (
    check_completeness, check_country, check_formats, check_documents,
    check_identity, check_name_match, check_verification, check_duplicates,
)
from config import ESCALATE_TO_REVIEW, FIX, NEEDS_REVIEW, RED, REJECT_ON_ITS_OWN, REVIEW, RULE_VERSION, VENDOR_TO_FIX


def build_vendor_message(status, sub_status, fixes, reject_reasons=()):
    if status == "Approved":
        return "Your application is approved."
    if status == "Rejected":
        if reject_reasons:
            return "Your application is rejected because " + "; ".join(reject_reasons) + ". If this was a mistake, submit a new application."
        return "Your application is rejected."
    head = "Your application is under review. We will reach back to you if anything is needed." if sub_status == NEEDS_REVIEW else ""
    if not fixes:
        return head
    todo = f"Please fix: {fixes[0]}" if len(fixes) == 1 else "Please fix:\n" + "\n".join(f"{i}. {fix}" for i, fix in enumerate(fixes, 1))
    return f"{head}\n{todo}" if head else todo


def decide(stage_results, previous=()):
    """previous: (code, message) pairs from the run this one replaces. A finding the vendor was already asked to fix and still has is unresolved."""
    findings = []
    for result in stage_results:
        findings += result["findings"]
    levels = [finding["level"] for finding in findings]
    red_flags = levels.count(RED)
    unresolved = [f for f in findings if f["level"] in (FIX, RED) and (f["code"], f["message"]) in set(previous)]
    escalated = [f for f in unresolved if f["code"] in ESCALATE_TO_REVIEW]
    stuck = [f for f in unresolved if f["code"] not in ESCALATE_TO_REVIEW]
    reject_reasons = [REJECT_ON_ITS_OWN[f["code"]] for f in findings if f["code"] in REJECT_ON_ITS_OWN]
    if stuck:
        reject_reasons.append("these were not fixed after your resubmission: " + "; ".join(f["message"] for f in stuck))

    if not findings:
        status, sub_status = "Approved", None
    elif reject_reasons or red_flags >= 2:  # a lone contradiction is a typo the vendor can fix; two at once are not
        status, sub_status = "Rejected", None
    elif REVIEW in levels or escalated:
        status, sub_status = "Pending", NEEDS_REVIEW
    else:
        status, sub_status = "Pending", VENDOR_TO_FIX

    if status == "Rejected" and red_flags >= 2:
        reject_reasons.append("the details you gave contradict each other")
    fixes = [f["message"] for f in findings if f["level"] in (FIX, RED)]
    reviewer_notes = [f["message"] for f in findings if f["level"] >= REVIEW or f in escalated]
    if escalated:
        reviewer_notes.append("The vendor was asked to fix this and sent it again, so a person should read their explanation or letter.")
    return {
        "status": status,
        "sub_status": sub_status,
        "findings": findings,
        "vendor_message": build_vendor_message(status, sub_status, fixes, reject_reasons),
        "reviewer_notes": reviewer_notes,
    }


def iter_stages(submission, existing_vendors):
    yield check_completeness(submission)
    yield check_country(submission)
    yield check_formats(submission)
    yield check_documents(submission)
    yield check_identity(submission)
    yield check_name_match(submission)
    yield check_verification(submission)
    yield check_duplicates(submission, existing_vendors)


def build_decision(stages, previous=()):
    decision = decide(stages, previous)
    decision["stages"] = stages
    decision["rule_version"] = RULE_VERSION
    return decision


def run_pipeline(submission, existing_vendors, previous=()):
    return build_decision(list(iter_stages(submission, existing_vendors)), previous)

def parse_submission(text):
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        return None, f"The file is not valid JSON ({error.msg}, line {error.lineno}, column {error.colno})"
    if not isinstance(data, dict):
        return None, "The file must contain a single JSON object"
    return data, None