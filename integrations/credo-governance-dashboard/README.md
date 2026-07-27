# Executive AI Governance Dashboard — Registry Data Pipeline

Pull your full AI system registry from Credo AI, compute portfolio-level KPIs, and write a JSON snapshot that any dashboard tool can consume — Tableau, Power BI, a custom React frontend, or a static HTML file.

- No webhooks — on-demand or scheduled pull
- Read-only: Credo AI is the single source of truth, no write-back
- One JSON output file, refreshed on every run
- Configurable via environment variables — no code changes needed for most tenants

**KPIs computed:**

| Metric | Description |
|---|---|
| Total AI systems | Count of all use cases in the registry |
| Approval status | Awaiting Submission / Active Review / Reviews Approved |
| Lifecycle mix | Idea / Experiment / Production (via custom field) |
| Vendor vs internal | Based on intake questionnaire answer |
| Risk distribution | High / Medium / Low / Unspecified (set directly on use case) |
| Risk drivers | Confidential data, data transfer outside org, vendor + confidential data |
| Median time-to-approval | Days from use case creation to final review approval |
| New registrations | Use cases created in the last 30 days |

---

## Prerequisites

| Item | Where to get it |
|---|---|
| Credo AI API key | Credo AI app → Settings → Tokens |
| Credo AI tenant slug | Credo AI app → Settings → Information |
| Credo AI Integration Service base URL | Provided by Credo AI |
| Question IDs for intake fields | Credo AI → questionnaire settings → inspect each field |
| Python 3.11+ | python.org |

---

## Step 1: Set credentials

```bash
cp .env.example .env
```

Open `.env` and fill in all values. The questionnaire question IDs require coordination with whoever configured your Credo AI intake form:

| Variable | How to find it |
|---|---|
| `Q_VENDOR_INTERNAL_QUESTION_ID` | Credo AI → intake questionnaire → find the "internally developed or vendor-based" question → copy its ID |
| `Q_DATA_CLASSIFICATION_QUESTION_ID` | Same questionnaire → data classification question |
| `Q_DATA_TRANSFER_QUESTION_ID` | Same questionnaire → data transfer question |
| `Q_LIFECYCLE_FIELD` | Name of the custom field storing Idea / Experiment / Production (default: `Business Type`) |

If your tenant doesn't use any of these questionnaire fields, leave the corresponding variable blank — the pipeline skips those KPIs.

---

## Step 2: Install and run

```bash
cd pipeline/python
pip install -r requirements.txt
python main.py
```

Output is written to `dashboard_data.json` (or wherever `OUTPUT_PATH` points).

---

## Step 3: Connect your dashboard tool

The output JSON has a stable schema. Point your dashboard tool at the file:

**Tableau / Power BI:** Use a JSON connector pointed at the output file or the S3 path where you write it.

**React / custom frontend:** `fetch('dashboard_data.json')` and bind to the fields.

**Static HTML:** Embed the JSON directly or load it with a `<script>` tag.

---

## Step 4: Schedule refreshes

Run the pipeline on a schedule to keep dashboard data fresh:

**Cron (daily at 6 AM):**
```bash
0 6 * * * cd /path/to/pipeline/python && python main.py >> /var/log/credo-dashboard.log 2>&1
```

**Docker (see Docker section below)** for containerized deployment.

---

## Output schema

```json
{
  "generated_at": "2026-05-27T06:00:00+00:00",
  "total_ai_systems": 42,
  "approval_status": {
    "awaiting_submission": 18,
    "active_review": 10,
    "reviews_approved": 14
  },
  "lifecycle_mix": {
    "Idea": 12,
    "Experiment": 15,
    "Production": 15
  },
  "vendor_vs_internal": {
    "vendor": 20,
    "internal": 22
  },
  "risk_distribution": {
    "High": 5,
    "Medium": 14,
    "Low": 18,
    "Unspecified": 5
  },
  "risk_drivers": {
    "confidential_or_restricted_data": 8,
    "data_transfer_outside_org": 6,
    "vendor_with_confidential_data": 4
  },
  "median_time_to_approval_days": 12.5,
  "new_registrations_last_30_days": 7
}
```

---

## Docker

Build and run locally:

```bash
docker build -t credo-dashboard-pipeline .
docker run --env-file .env -v $(pwd)/output:/app/output \
  -e OUTPUT_PATH=/app/output/dashboard_data.json \
  credo-dashboard-pipeline
```

For production, mount your cloud storage credentials and write `OUTPUT_PATH` to S3 (or equivalent) using your provider's SDK.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `401` on token call | Invalid API key or tenant | Check `.env` values |
| `404` on use cases | Wrong base URL or tenant slug | Confirm `CREDO_BASE_URL` includes `/api/v1/integration` |
| Lifecycle mix all `Unspecified` | Custom field name doesn't match | Confirm `Q_LIFECYCLE_FIELD` matches your tenant's exact field name |
| Vendor/internal all internal | Question ID not set or doesn't match | Inspect your intake questionnaire and update `Q_VENDOR_INTERNAL_QUESTION_ID` |
| Risk drivers all zero | Question IDs not set | Set the question ID env vars; or your questionnaire uses different question IDs |
| Median time-to-approval is `null` | No reviews have been approved yet | Expected for early registries — populates once approvals complete |
| Slow run on large registries | N+1 API calls per use case | Batch the questionnaire/review fetches if your Integration Service version supports it |

Still stuck? Slack: `#credo-ai-integrations` | Support: support.credo.ai

---

## How it works

```
Credo AI Registry API
  └─ GET /use_cases (paginated)
       └─ For each use case:
            ├─ GET /use_cases/{id}/reviews           → approval status, time-to-approval
            └─ GET /use_cases/{id}/questionnaire_answers → vendor flag, risk drivers
  └─ Compute KPIs across all use cases
       └─ Write dashboard_data.json
```

Credo AI is the system of record. Every run overwrites the previous snapshot — the dashboard always reflects the latest registry state.

---

## Extending this pattern

- **Add new KPIs:** Extend `build_dashboard_data()` in `main.py`. The questionnaire answers dict gives you access to any intake question.
- **Write to S3:** Replace the `open(OUTPUT_PATH)` block with `boto3.client('s3').put_object(...)`.
- **Segment by business unit:** Filter use cases by a custom field before computing KPIs to produce per-team breakdowns.
- **Historical trending:** Append each snapshot to a time-series store (e.g. append to a Parquet file in S3) rather than overwriting.

---

## Full guide

[docs.credo.ai/integrations/executive-dashboard](https://docs.credo.ai/integrations/executive-dashboard)
