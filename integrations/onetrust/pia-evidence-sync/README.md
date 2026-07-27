# OneTrust PIA → Credo AI Control Evidence

When a user submits a Privacy Impact Assessment (PIA) ID in a Credo AI intake questionnaire, this service fetches the full assessment from OneTrust and uploads key fields as control evidence — automatically, on every questionnaire event.

- Triggered by Credo AI webhook — no polling
- Fetches 3 PIA fields: Assessment ID, Risk Level, Open Risks and Recommendations
- Uploads as evidence on a configurable "Complete PIA" control
- Overwrites on every sync — OneTrust is always the source of truth

---

## Prerequisites

| Item | Where to get it |
|---|---|
| Credo AI API key | Credo AI app → Settings → Tokens |
| Credo AI tenant slug | Credo AI app → Settings → Information |
| Credo AI Integration Service base URL | Provided by Credo AI |
| OneTrust OAuth client ID and secret | OneTrust → Developer → API Credentials |
| OneTrust base URL | Your org's OneTrust instance URL |
| Credo AI questionnaire with a PIA ID field | Configured by your governance team |
| Credo AI control ID for "Complete PIA" | From your Credo AI control library |
| Python 3.11+ | python.org |

---

## Step 1: Set credentials

```bash
cp .env.example .env
```

Open `.env` and fill in all values. Two IDs require coordination with your governance team:

| Variable | How to find it |
|---|---|
| `ONETRUST_ID_QUESTION_ID` | Credo AI → your intake questionnaire → inspect the PIA ID field → copy its question ID |
| `CREDO_CONTROL_ID` | Credo AI → Controls library → find "Complete Privacy Impact Assessment" → copy its ID |

---

## Step 2: Field mapping

Confirm which OneTrust assessment fields map to Credo AI evidence. Defaults match the standard PIA template:

| OneTrust field | Question ID | Credo AI evidence field |
|---|---|---|
| Assessment ID | (top-level record) | OneTrust ID |
| Risk Level | `Q12.7` | PIA Risk Assessment |
| Open Risks and Recommendations | `Q12.11` | Open Privacy Risks and Recommended Actions |

If your OneTrust PIA uses different question IDs, update `extract_evidence_fields()` in `server/python/main.py`.

---

## Step 3: Install and run

```bash
cd server/python
pip install -r requirements.txt
uvicorn main:app --port 8400
```

The service listens on `POST /webhooks/credo`.

For production, expose this endpoint over HTTPS. For local testing, use [ngrok](https://ngrok.com):

```bash
ngrok http 8400
```

Note the public URL — you need it in Step 4.

---

## Step 4: Register the Credo AI webhook

Register once. This tells Credo AI to notify your service on every questionnaire event.

```bash
curl -X POST "{CREDO_BASE_URL}/webhooks" \
  -H "Authorization: Bearer {CREDO_API_TOKEN}" \
  -H "X-Tenant: {CREDO_TENANT}" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://<your-public-url>/webhooks/credo",
    "events": ["use_case_evidence_created"]
  }'
```

Save the webhook `id` from the response — use it to delete or update the registration later.

To delete:

```bash
curl -X DELETE "{CREDO_BASE_URL}/webhooks/{WEBHOOK_ID}" \
  -H "Authorization: Bearer {CREDO_API_TOKEN}" \
  -H "X-Tenant: {CREDO_TENANT}"
```

---

## Step 5: Test end-to-end

1. In Credo AI, open a use case and navigate to its intake questionnaire
2. Find the PIA ID question and enter a valid OneTrust Assessment ID
3. Submit the field
4. Watch the service logs — you should see the webhook arrive and evidence upload complete
5. In Credo AI, open the use case → Controls → find the "Complete PIA" control → confirm evidence is populated with three fields

To test without a live OneTrust instance, set `ONETRUST_BASE_URL` to a mock server or add a `--dry-run` flag to `extract_evidence_fields()`.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Webhook never arrives | Wrong URL registered or service not reachable | Confirm `ngrok`/public URL is correct and service is running |
| `401` on Credo AI token call | Invalid API key or tenant | Check `.env` values |
| `401` on OneTrust token call | Invalid client credentials | Regenerate in OneTrust → Developer → API Credentials |
| Assessment fetch returns `404` | Assessment ID doesn't exist or wrong OneTrust tenant | Confirm the ID the user entered is valid in OneTrust |
| Evidence uploads but fields are blank | Question IDs don't match your PIA template | Check `Q12.7` and `Q12.11` in your OneTrust assessment export; update `extract_evidence_fields()` |
| Control not found on use case | `CREDO_CONTROL_ID` is wrong | Confirm control ID from Credo AI control library |
| Webhook fires but `assessment_id` is `None` | `ONETRUST_ID_QUESTION_ID` doesn't match your questionnaire | Re-inspect the question ID in Credo AI questionnaire settings |
| Evidence not overwriting on re-submit | Evidence endpoint creating duplicates | Confirm your Credo AI evidence endpoint supports upsert; add dedup logic if needed |

Still stuck? Slack: `#credo-ai-integrations` | Support: support.credo.ai

---

## How it works

```
User fills in OneTrust PIA ID in Credo AI questionnaire
  └─ Credo AI fires use_case_evidence_created webhook
       └─ Service fetches the questionnaire answer (the OneTrust ID)
            └─ Service fetches PIA assessment from OneTrust API
                 └─ Extracts: Assessment ID, Risk Level (Q12.7), Open Risks (Q12.11)
                      └─ Uploads as evidence on "Complete PIA" control in Credo AI
```

OneTrust is the source of truth. Every webhook event overwrites the previous evidence — re-submitting the form with the same ID refreshes the evidence from the latest OneTrust state.

---

## Extending this pattern

This pattern works for any GRC tool that exposes an assessment API:

- **IP Assessments** — swap the OneTrust endpoint and question IDs; same service shape
- **Other GRC tools** (Archer, OneTrust Cookie Compliance, TrustArc) — replace `get_onetrust_assessment()` with a call to your tool's API; keep everything else

---

## Full guide

[docs.credo.ai/integrations/onetrust/pia-evidence-sync](https://docs.credo.ai/integrations/onetrust/pia-evidence-sync)
