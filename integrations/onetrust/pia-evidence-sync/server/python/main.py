import os
import json
import httpx
from fastapi import FastAPI, Request, HTTPException

app = FastAPI()

CREDO_BASE_URL   = os.environ["CREDO_BASE_URL"]
CREDO_API_KEY    = os.environ["CREDO_API_KEY"]
CREDO_TENANT     = os.environ["CREDO_TENANT"]
ONETRUST_BASE_URL = os.environ["ONETRUST_BASE_URL"]
ONETRUST_CLIENT_ID     = os.environ["ONETRUST_CLIENT_ID"]
ONETRUST_CLIENT_SECRET = os.environ["ONETRUST_CLIENT_SECRET"]

# Question IDs — update these to match your Credo AI questionnaire configuration
ONETRUST_ID_QUESTION_ID = os.environ["ONETRUST_ID_QUESTION_ID"]
CREDO_CONTROL_ID        = os.environ["CREDO_CONTROL_ID"]


def get_credo_token() -> str:
    r = httpx.post(
        f"{CREDO_BASE_URL}/auth/token",
        headers={"X-API-Key": CREDO_API_KEY, "X-Tenant": CREDO_TENANT},
    )
    r.raise_for_status()
    return r.json()["access_token"]


def get_onetrust_token() -> str:
    r = httpx.post(
        f"{ONETRUST_BASE_URL}/api/access/v1/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": ONETRUST_CLIENT_ID,
            "client_secret": ONETRUST_CLIENT_SECRET,
        },
    )
    r.raise_for_status()
    return r.json()["access_token"]


def get_questionnaire_answer(use_case_id: str, question_id: str, credo_token: str) -> str | None:
    r = httpx.get(
        f"{CREDO_BASE_URL}/use_cases/{use_case_id}/evidence",
        headers={"Authorization": f"Bearer {credo_token}", "X-Tenant": CREDO_TENANT},
    )
    r.raise_for_status()
    for item in r.json().get("data", []):
        if item.get("attributes", {}).get("question_id") == question_id:
            return item["attributes"].get("value")
    return None


def get_onetrust_assessment(assessment_id: str, ot_token: str) -> dict:
    r = httpx.get(
        f"{ONETRUST_BASE_URL}/api/assessment/v2/assessments/{assessment_id}/export",
        headers={"Authorization": f"Bearer {ot_token}"},
    )
    r.raise_for_status()
    return r.json()


def extract_evidence_fields(assessment: dict) -> dict:
    sections = assessment.get("sections", [])
    fields = {"onetrust_id": assessment.get("id", ""), "risk_level": "", "open_risks": ""}

    for section in sections:
        for question in section.get("questions", []):
            qid = question.get("questionId", "")
            answer = question.get("answer", {}).get("value", "")
            if qid == "Q12.7":
                fields["risk_level"] = answer
            elif qid == "Q12.11":
                fields["open_risks"] = answer

    return fields


def add_control_evidence(use_case_id: str, fields: dict, credo_token: str):
    headers = {
        "Authorization": f"Bearer {credo_token}",
        "X-Tenant": CREDO_TENANT,
        "Content-Type": "application/json",
    }

    # Add the control to the use case
    httpx.post(
        f"{CREDO_BASE_URL}/use_cases/{use_case_id}/controls",
        headers=headers,
        json={"control_id": CREDO_CONTROL_ID},
    ).raise_for_status()

    # Upload the evidence
    evidence_text = (
        f"OneTrust ID: {fields['onetrust_id']}\n"
        f"PIA Risk Assessment: {fields['risk_level']}\n"
        f"Open Privacy Risks and Recommended Actions: {fields['open_risks']}"
    )
    httpx.post(
        f"{CREDO_BASE_URL}/use_cases/{use_case_id}/controls/{CREDO_CONTROL_ID}/evidence",
        headers=headers,
        json={"text": evidence_text, "source": "onetrust"},
    ).raise_for_status()


@app.post("/webhooks/credo")
async def credo_webhook(request: Request):
    payload = await request.json()

    event_type = payload.get("event_type")
    if event_type not in ("use_case_evidence_created", "use_case_questionnaire_added"):
        return {"message": "ignored"}

    use_case_id = payload.get("data", {}).get("use_case_id")
    if not use_case_id:
        raise HTTPException(status_code=400, detail="missing use_case_id")

    credo_token = get_credo_token()

    assessment_id = get_questionnaire_answer(use_case_id, ONETRUST_ID_QUESTION_ID, credo_token)
    if not assessment_id:
        return {"message": "OneTrust ID question not answered yet — skipped"}

    ot_token = get_onetrust_token()
    assessment = get_onetrust_assessment(assessment_id, ot_token)
    fields = extract_evidence_fields(assessment)

    add_control_evidence(use_case_id, fields, credo_token)

    return {"use_case_id": use_case_id, "onetrust_id": assessment_id, "status": "synced"}
