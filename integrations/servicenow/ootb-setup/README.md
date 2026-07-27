# ServiceNow ↔ Credo AI — OOTB Integration Setup

Install the Credo AI Portal scoped app and register the connection. When done, ServiceNow becomes a governance intake surface and a live mirror of every use-case state change from Credo AI.

**What you get:**
- Embedded intake form inside ServiceNow — users create governed use cases without leaving ServiceNow
- Real-time sync of risk level, workflow stage, and review status into `credo_ai_use_case_table`
- A clean table to build downstream automations on (change requests, incidents, notifications)

**No custom code required.** This is configuration only.

---

## Prerequisites

| Item | Where to get it |
|---|---|
| ServiceNow instance (Vancouver or later) | Your org's SN admin |
| ServiceNow admin access | To install apps, assign roles, create users |
| Credo AI API token | Credo AI app → Settings → Tokens |
| Credo AI Tenant ID | Credo AI app → Settings → Information |
| Credo AI Integration Service base URL | Provided by Credo AI |

---

## Step 1: Install the scoped app

In your ServiceNow instance, go to **ServiceNow Store** and install:

> **Credo AI Portal** (`x_1764381_credo_0`)

Requires Vancouver or later. If you do not have Store access, contact your ServiceNow admin.

---

## Step 2: Assign roles

Create a dedicated integration user — do not use a personal account.

| User | Role to assign | Purpose |
|---|---|---|
| Your SN admin | `x_1764381_credo_0.admin` | Runs Guided Setup, manages config |
| New integration user (e.g. `credoai_integration_user`) | `x_1764381_credo_0.integration_user` | Account Credo AI authenticates as for outbound sync |
| End users | `x_1764381_credo_0.user` | Submit the intake form |

Set the integration user as **web-service-access-only** — it should not have interactive login.

---

## Step 3: Run Guided Setup

Navigate to **Credo AI Portal → Guided Setup** and complete all steps:

1. Confirm roles are assigned (Step 2 above)
2. Enter your **Credo AI API token** (Settings → Tokens)
3. Enter your **Tenant ID** (Settings → Information)
4. Note the **integration user's password** — you will need it in Step 4

Self-hosted Credo AI only: also set `API base URL`, `web-component URL`, and `app URL` in Guided Setup. Cloud customers skip this.

---

## Step 4: Register the connection from Credo AI

This turns on the outbound sync (Credo AI → ServiceNow). Run once per ServiceNow instance.

```bash
curl -X POST "{CREDO_BASE_URL}/api/v2/{TENANT}/integrations" \
  -H "Authorization: Bearer {CREDO_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "type": "integrations",
      "attributes": {
        "type": "service_now",
        "data": {
          "service_now_instance_url": "https://<your-instance>.service-now.com",
          "username": "credoai_integration_user",
          "password": "<integration_user_password>"
        }
      }
    }
  }'
```

Expected response: `201 Created` with an integration `id`. Save that ID — you need it to delete and reconfigure later.

To reconfigure, delete first, then re-create:

```bash
curl -X DELETE "{CREDO_BASE_URL}/api/v2/{TENANT}/integrations/{INTEGRATION_ID}" \
  -H "Authorization: Bearer {CREDO_API_TOKEN}"
```

---

## Step 5: Verify the intake form loads

In ServiceNow, navigate to the Credo AI Portal page and confirm the intake form renders. If the form is blank:

1. Go to **System Properties** and find `x_1764381_credo_0.sri_hash_integrity`
2. Go to `https://wc.credo.ai/registry.json` and copy the value at `resources.use-case-intake-form.js.integrity`
3. Paste it into the system property and save

This is the most common setup failure. The SRI hash must be refreshed after every scoped-app update — add it to your app-update runbook.

---

## Step 6: Test end-to-end

1. Submit a test use case via the intake form in ServiceNow
2. Confirm it appears in Credo AI (use cases list)
3. In Credo AI, update the use case (change a field, advance a workflow stage)
4. In ServiceNow, query `credo_ai_use_case_table` and confirm the row was created or updated:

```javascript
// Scripts - Background
var gr = new GlideRecord('credo_ai_use_case_table');
gr.addQuery('use_case_name', 'CONTAINS', 'your test use case name');
gr.query();
while (gr.next()) {
    gs.info(gr.use_case_id + ' | ' + gr.use_case_name + ' | ' + gr.metadata);
}
```

Expected: one row with `use_case_id` populated and `metadata` containing workflow stage and risk level.

---

## What lands in `credo_ai_use_case_table`

Every use-case event from Credo AI (create, update, delete) syncs to this table in real time.

| Column | Field name | Type | Notes |
|---|---|---|---|
| Use Case ID | `use_case_id` | String | Join key — matches Credo AI |
| Use Case Name | `use_case_name` | String | |
| Description | `use_case_description` | String | |
| Metadata | `metadata` | JSON string | AI type, risk level, workflow stage/step/status, source, industries, domains, regions |
| Custom Fields | `custom_fields` | JSON string | All custom fields on the use case |
| Questionnaire | `questionnaire` | JSON string | Associated questionnaires |
| Questionnaire Evidences | `questionnaire_evidences` | JSON string | Completed questionnaire evidences |

This table is the surface for every automation you build downstream. Examples:

- Open a Change Request when `metadata.workflow.stage` reaches a deployment gate
- Raise an Incident when `metadata.risk_classification_level` changes to `High`
- Notify a Slack/Teams channel on any update
- Write into IRM/GRC Risk or Control records

None of these ship OOTB — the integration delivers the data; the automations are yours to build in Flow Designer.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Intake form is blank | SRI hash mismatch | Refresh `sri_hash_integrity` system property (Step 5) |
| `POST /integrations` returns 401 | Invalid or expired API token | Regenerate token in Credo AI → Settings → Tokens |
| Outbound sync not appearing in table | Connection not registered | Confirm Step 4 ran and returned 201 |
| 200 response but table row not created | ServiceNow returned HTML (SSO redirect, hibernating instance, WAF) | Check Credo AI sync issues; confirm SN instance is reachable and the scoped app is installed |
| Use case created in Credo AI but no SN row | Integration user lacks `integration_user` role | Re-assign role, re-register connection |
| Reconfiguring doesn't take effect | Old integration record still active | DELETE existing integration first, then POST new one |
| Outbound sync works for dev, not prod | Multi-instance not configured | Run Step 4 once per instance — the connector fans out to all registered `service_now` integrations |

Still stuck? Slack: `#credo-ai-integrations` | Support: support.credo.ai

---

## Data flow summary

```
ServiceNow intake form
  └─ POST /api/v2/{tenant}/use_cases  →  Credo AI (bearer token)
       └─ governs the use case (triage, review, workflow)
            └─ event-driven push on every change
                 └─ GET/POST/PUT/DELETE on credo_ai_use_case_table  →  ServiceNow (HTTP Basic)
                      └─ your Flow Designer automations fire off this table
```

Direction: intake is bidirectional (create from either side); workflow status is **Credo AI → ServiceNow only**. A ServiceNow action cannot advance a Credo AI workflow state without a custom API call.

---

## Full guide

[docs.credo.ai/integrations/servicenow/ootb-setup](https://docs.credo.ai/integrations/servicenow/ootb-setup)
