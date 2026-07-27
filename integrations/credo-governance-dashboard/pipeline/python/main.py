"""
Executive AI Governance Dashboard — data pipeline

Pulls the full AI system registry from Credo AI, computes portfolio-level
KPIs, and writes a JSON snapshot that any dashboard tool can consume.

Run on a schedule (cron, Airflow, etc.) or on demand.
Output: dashboard_data.json (or S3 path if configured)
"""

import json
import os
import statistics
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

load_dotenv()

CREDO_BASE_URL = os.environ["CREDO_BASE_URL"]   # https://<tenant>.credo.ai/api/v1/integration
CREDO_API_KEY  = os.environ["CREDO_API_KEY"]
CREDO_TENANT   = os.environ["CREDO_TENANT"]
OUTPUT_PATH    = os.getenv("OUTPUT_PATH", "dashboard_data.json")

# Questionnaire question IDs — configure to match your tenant's intake form
Q_LIFECYCLE_FIELD     = os.getenv("Q_LIFECYCLE_FIELD", "Business Type")          # custom field name
Q_VENDOR_INTERNAL     = os.getenv("Q_VENDOR_INTERNAL_QUESTION_ID", "")           # e.g. "Is this AI solution internally developed or vendor-based?"
Q_DATA_CLASSIFICATION = os.getenv("Q_DATA_CLASSIFICATION_QUESTION_ID", "")       # input/output data classification
Q_DATA_TRANSFER       = os.getenv("Q_DATA_TRANSFER_QUESTION_ID", "")             # data transfer outside org
CONFIDENTIAL_VALUES   = {"Confidential", "Restricted"}                           # values that count as confidential


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def get_token() -> str:
    resp = httpx.post(
        f"{CREDO_BASE_URL}/auth/token",
        headers={"X-API-Key": CREDO_API_KEY, "X-Tenant": CREDO_TENANT},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# Data fetching
# NOTE: Verify these endpoint paths with your Credo AI integration engineer
#       before deploying. Endpoint availability depends on Integration Service version.
# ---------------------------------------------------------------------------

def get_use_cases(token: str) -> list[dict]:
    """Returns all use cases in the registry."""
    headers = {"Authorization": f"Bearer {token}", "X-Tenant": CREDO_TENANT}
    results, page = [], 1
    while True:
        resp = httpx.get(
            f"{CREDO_BASE_URL}/use_cases",
            headers=headers,
            params={"page": page, "per_page": 100},
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        if not data:
            break
        results.extend(data)
        page += 1
    return results


def get_questionnaire_answers(use_case_id: str, token: str) -> dict:
    """Returns a {question_id: answer} map for a use case's intake questionnaire."""
    headers = {"Authorization": f"Bearer {token}", "X-Tenant": CREDO_TENANT}
    resp = httpx.get(
        f"{CREDO_BASE_URL}/use_cases/{use_case_id}/questionnaire_answers",
        headers=headers,
    )
    if resp.status_code == 404:
        return {}
    resp.raise_for_status()
    answers = resp.json().get("data", [])
    return {a["question_id"]: a["answer"] for a in answers}


def get_reviews(use_case_id: str, token: str) -> list[dict]:
    """Returns all reviews for a use case."""
    headers = {"Authorization": f"Bearer {token}", "X-Tenant": CREDO_TENANT}
    resp = httpx.get(
        f"{CREDO_BASE_URL}/use_cases/{use_case_id}/reviews",
        headers=headers,
    )
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    return resp.json().get("data", [])


# ---------------------------------------------------------------------------
# KPI computation
# ---------------------------------------------------------------------------

def approval_status(reviews: list[dict]) -> str:
    """
    Maps review state to one of three display statuses:
      - Awaiting Submission   → no reviews exist or all are in draft
      - Active Review         → at least one review is open/in-progress
      - Reviews Approved      → all reviews are approved/completed
    """
    if not reviews:
        return "Awaiting Submission"
    statuses = {r.get("status", "") for r in reviews}
    if "approved" in statuses and len(statuses) == 1:
        return "Reviews Approved"
    if any(s in statuses for s in ("open", "in_progress", "active")):
        return "Active Review"
    return "Awaiting Submission"


def time_to_approval_days(use_case: dict, reviews: list[dict]) -> float | None:
    """Days from use case creation to final review approval. None if not yet approved."""
    approved = [r for r in reviews if r.get("status") == "approved"]
    if not approved:
        return None
    created_at = use_case.get("attributes", {}).get("created_at")
    last_approval = max(r.get("updated_at", "") for r in approved)
    if not created_at or not last_approval:
        return None
    try:
        t_created  = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        t_approved = datetime.fromisoformat(last_approval.replace("Z", "+00:00"))
        return (t_approved - t_created).total_seconds() / 86400
    except Exception:
        return None


def is_vendor(answers: dict) -> bool:
    if not Q_VENDOR_INTERNAL:
        return False
    answer = answers.get(Q_VENDOR_INTERNAL, "")
    return "vendor" in answer.lower()


def risk_drivers(answers: dict, vendor: bool) -> dict:
    """
    Returns a dict of {driver_name: bool} for the three standard risk drivers.
    Customize the answer matching logic to fit your questionnaire values.
    """
    classification = answers.get(Q_DATA_CLASSIFICATION, "")
    transfer       = answers.get(Q_DATA_TRANSFER, "")

    confidential_data   = any(v.lower() in classification.lower() for v in CONFIDENTIAL_VALUES)
    data_transfer       = bool(transfer) and transfer.lower() not in ("no", "false", "n/a", "")
    vendor_confidential = vendor and confidential_data

    return {
        "confidential_or_restricted_data": confidential_data,
        "data_transfer_outside_org":        data_transfer,
        "vendor_with_confidential_data":    vendor_confidential,
    }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def build_dashboard_data() -> dict:
    print("Authenticating...")
    token = get_token()

    print("Fetching use cases...")
    use_cases = get_use_cases(token)
    total = len(use_cases)
    print(f"  {total} use cases found")

    approval_counts     = {"Awaiting Submission": 0, "Active Review": 0, "Reviews Approved": 0}
    lifecycle_counts    = {}
    risk_counts         = {"High": 0, "Medium": 0, "Low": 0, "Unspecified": 0}
    vendor_count        = 0
    driver_totals       = {
        "confidential_or_restricted_data": 0,
        "data_transfer_outside_org":        0,
        "vendor_with_confidential_data":    0,
    }
    tta_days            = []
    new_last_30_days    = 0
    now                 = datetime.now(timezone.utc)

    for uc in use_cases:
        attrs    = uc.get("attributes", {})
        uc_id    = uc.get("id")

        # Approval status
        reviews = get_reviews(uc_id, token)
        status  = approval_status(reviews)
        approval_counts[status] += 1

        # Time to approval
        tta = time_to_approval_days(uc, reviews)
        if tta is not None:
            tta_days.append(tta)

        # Lifecycle (custom field)
        lifecycle = attrs.get("custom_fields", {}).get(Q_LIFECYCLE_FIELD, "Unspecified")
        lifecycle_counts[lifecycle] = lifecycle_counts.get(lifecycle, 0) + 1

        # Risk score
        risk = attrs.get("risk_level") or "Unspecified"
        risk_counts[risk] = risk_counts.get(risk, 0) + 1

        # Questionnaire-derived fields
        answers = get_questionnaire_answers(uc_id, token)
        vendor  = is_vendor(answers)
        if vendor:
            vendor_count += 1

        for driver, val in risk_drivers(answers, vendor).items():
            if val:
                driver_totals[driver] += 1

        # New registrations (last 30 days)
        created_at = attrs.get("created_at", "")
        if created_at:
            try:
                t = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                if (now - t).days <= 30:
                    new_last_30_days += 1
            except Exception:
                pass

    median_tta = round(statistics.median(tta_days), 1) if tta_days else None

    snapshot = {
        "generated_at":          now.isoformat(),
        "total_ai_systems":      total,
        "approval_status": {
            "awaiting_submission": approval_counts["Awaiting Submission"],
            "active_review":       approval_counts["Active Review"],
            "reviews_approved":    approval_counts["Reviews Approved"],
        },
        "lifecycle_mix":         lifecycle_counts,
        "vendor_vs_internal": {
            "vendor":   vendor_count,
            "internal": total - vendor_count,
        },
        "risk_distribution":     risk_counts,
        "risk_drivers":          driver_totals,
        "median_time_to_approval_days": median_tta,
        "new_registrations_last_30_days": new_last_30_days,
    }

    return snapshot


def main():
    data = build_dashboard_data()

    with open(OUTPUT_PATH, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nDone. Snapshot written to {OUTPUT_PATH}")
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
