# Credo AI Integration Recipes

Runnable integration examples for connecting your systems to the Credo AI platform.

Each recipe is self-contained — clone, configure, and run in under 30 minutes.

---

## Available Integrations

### Use Case Creation
| System | What it does | Status |
|---|---|---|
| [JIRA](./jira/use-case-creation) | Auto-create use cases when a JIRA issue is created | ✅ Available |
| [ServiceNow](./servicenow/use-case-creation) | Auto-create use cases from AI intake table records | 🔜 Coming soon |
| [Salesforce](./salesforce/use-case-creation) | Auto-create use cases from Salesforce records | 🔜 Coming soon |

### Model & Vendor Registry Sync
| System | What it does | Status |
|---|---|---|
| [Databricks](./databricks/model-registry-sync) | Sync models from Databricks Model Registry to Credo AI | 🔜 Coming soon |
| [Amazon Bedrock](./amazon-bedrock/model-registry-sync) | Sync models from Amazon Bedrock to Credo AI | 🔜 Coming soon |
| [Azure AI Foundry](./azure-ai-foundry/model-registry-sync) | Sync models from Azure AI Foundry to Credo AI | 🔜 Coming soon |

---

## How to use a recipe

```bash
# 1. Clone the repo
git clone https://github.com/credo-ai/credoai-recipes.git

# 2. Navigate to the recipe you need
cd integrations/jira/use-case-creation

# 3. Copy and fill in your credentials
cp .env.example .env

# 4. Install and run
cd server/python
pip install -r requirements.txt
uvicorn main:app --port 5000
```

---

## Request an integration

Don't see what you need? [Open an issue](https://github.com/credo-ai/credoai-recipes/issues/new?template=integration_request.md).

---

## Resources

- Docs: [docs.credo.ai](https://docs.credo.ai)
- Developer Slack: `#credo-ai-integrations`
- Support: support.credo.ai
