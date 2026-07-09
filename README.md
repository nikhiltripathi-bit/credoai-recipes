# Credo AI Recipes

Runnable integration recipes for connecting your systems to the [Credo AI](https://credo.ai) governance platform.

Clone a recipe, set your credentials, and run in under 30 minutes.

---

## Integrations

Browse all recipes in the [integrations/](./integrations) folder.

| System | Type | Status |
|---|---|---|
| [JIRA](./integrations/jira/use-case-creation) | Use case creation | ✅ Available |
| [ServiceNow](./integrations/servicenow/use-case-creation) | Use case creation | 🔜 Coming soon |
| [Salesforce](./integrations/salesforce/use-case-creation) | Use case creation | 🔜 Coming soon |
| [Databricks](./integrations/databricks/model-registry-sync) | Model registry sync | 🔜 Coming soon |
| [Amazon Bedrock](./integrations/amazon-bedrock/model-registry-sync) | Model registry sync | 🔜 Coming soon |
| [Azure AI Foundry](./integrations/azure-ai-foundry/model-registry-sync) | Model registry sync | 🔜 Coming soon |

---

## Quick start

```bash
git clone https://github.com/credo-ai/credoai-recipes.git
cd credoai-recipes/integrations/jira/use-case-creation
cp .env.example .env
# Edit .env with your credentials
cd server/python
pip install -r requirements.txt
uvicorn main:app --port 5000
```

---

## Request an integration

Don't see what you need? [Open a request](https://github.com/credo-ai/credoai-recipes/issues/new?template=integration_request.md).

---

## Resources

- Docs: [docs.credo.ai](https://docs.credo.ai)
- Developer Slack: `#credo-ai-integrations`
- Support: support.credo.ai
