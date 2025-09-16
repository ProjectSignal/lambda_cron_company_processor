# Deployment Guide – lambda_cron_new_company_processor

This Lambda processes newly discovered LinkedIn company webpages. After the migration it runs on the shared API-first architecture and deploys via AWS CodeBuild.

## Prerequisites
- AWS account with permissions to manage Lambda, IAM, CodeBuild, and CloudWatch Logs.
- GitHub repository connected to AWS CodeBuild through CodeConnections.
- Backend REST API exposing the routes documented in `services.py` (`webpages.getById`, `webpages.updateById`, `nodes.applyCompanyEnrichment`, etc.).
- Jina Reader API key (RapidAPI key optional for fallback).

## Environment Variables
Configure these in the Lambda console or infrastructure-as-code stack:

| Variable | Required | Description |
| -------- | -------- | ----------- |
| `BASE_API_URL` | ✅ | Brace API base URL (e.g. `https://backend.brace.so`) |
| `INSIGHTS_API_KEY` | ✅ | API key injected into the `X-API-Key` header |
| `JINA_READER_API_KEY` | ✅ | Auth token for the Jina Reader service |
| `JINA_BASE_URL` |  | Override for the Jina endpoint (default `https://r.jina.ai/`) |
| `RAPIDAPI_KEY` |  | Enables RapidAPI fallback when provided |
| `RAPIDAPI_HOST` |  | Hostname for RapidAPI calls (default `linkedin-api8.p.rapidapi.com`) |
| `RAPIDAPI_URL` |  | Optional override for the RapidAPI URL |
| `REQUEST_TIMEOUT` |  | External request timeout in seconds (default `45`) |
| `CLEANUP_ON_FAILURE` |  | When `true`, deletes webpages that fail all providers (default `true`) |
| `WORKER_ID` |  | Worker identifier used in telemetry (defaults to Lambda function name) |

Keep the shared XML generator and downstream lambdas aligned by reusing `BASE_API_URL`/`INSIGHTS_API_KEY` conventions.

## CodeBuild Pipeline
1. Place the provided `buildspec.yml` at the repository root.
2. Create a CodeBuild project named `lambda-cron-new-company-processor-build` using runtime `Ubuntu Standard 5.0` and environment variable `LAMBDA_FUNCTION_NAME=lambda-cron-new-company-processor`.
3. Connect the GitHub repository via CodeConnections and trigger on `main` branch pushes.
4. Grant the CodeBuild service role permission to `lambda:GetFunction`, `lambda:UpdateFunctionCode`, and `lambda:Wait`. Include CloudWatch Logs permissions for troubleshooting.

The buildspec installs dependencies, zips the source, and updates the Lambda function code automatically.

## Git Workflow
Each lambda lives in its own repository. Initialise git inside this directory only:

```bash
cd lambda_cron_new_company_processor
git init
```

Commit changes normally and push to GitHub to trigger the pipeline.

## Testing Checklist
1. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv myenv
   source myenv/bin/activate
   pip install -r requirements.txt
   ```
2. Run the smoke script with mocked services:
   ```bash
   python test_local.py
   ```
   The script patches the CompanyDataService and Jina fetcher, exercising the handler without external calls.
3. (Optional) Write unit tests against `processor.NewCompanyProcessor` using mocks for the API client.

## Operational Notes
- The Lambda expects events that include a `webpageId` in the root JSON payload or request body.
- When both providers fail, the function either cleans up the webpage (`CLEANUP_ON_FAILURE=true`) or marks it failed through the API.
- API route placeholders are documented in `services.py`; coordinate with the backend team to ensure implementations exist before production rollout.
