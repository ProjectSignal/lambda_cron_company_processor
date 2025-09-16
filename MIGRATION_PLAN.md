# lambda_cron_new_company_processor – Migration Plan

## Objectives
- Align project layout, entrypoint naming, and tooling with the shared Lambda conventions (reference: `lambda_network_capital`).
- Remove all direct MongoDB access and route persistence through the Brace REST APIs.
- Preserve company deduplication, enrichment, and failure-handling behaviours while improving observability.
- Deliver CI/CD assets and documentation updates so the Lambda can deploy via CodeBuild like the other services.

## Planned Workstreams
1. **Repository & Tooling Setup**
   - Initialise a dedicated git repository inside the lambda directory.
   - Add `buildspec.yml`, `.gitignore`, and README updates in line with platform standards.
   - Refresh `requirements.txt` to drop MongoDB dependencies.

2. **Configuration & Client Layer**
   - Replace `config.py` with a package exposing REST configuration (`BASE_API_URL`, `INSIGHTS_API_KEY`, retry settings) while keeping provider keys.
   - Introduce a reusable `ApiClient` (mirroring cron node processor) that handles retries, authentication, and JSON serialization.

3. **Data Access Migration**
   - Replace `NewCompanyDB` with a thin service wrapper that talks to APIs. Each new method will document the expected route using the `# API Route:` comment pattern.
   - API surfaces to cover:
     | Legacy Operation | New API Interaction |
     | ---------------- | ------------------- |
     | Load webpage by `_id` | `GET /api/webpages/{webpageId}` |
     | Enumerate comparison candidates | `POST /api/webpages/list-test-candidates` (placeholder with TODO comment) |
     | Persist scrape output | `PATCH /api/webpages/{webpageId}` |
     | Mark extraction failure | `POST /api/webpages/mark-failed` |
     | Enrich referencing nodes | `POST /api/nodes/apply-company-enrichment` |
     | Cleanup failed webpages | `POST /api/webpages/cleanup-failed` |
     | Aggregate processing stats | `GET /api/webpages/processing-stats` |

4. **Processor & Handler Alignment**
   - Update `processor.py` to rely on the new service instead of Mongo, keeping Jina/RapidAPI flow intact.
   - Rename `handler.py` → `lambda_handler.py`; normalise event parsing so the Lambda accepts payloads with `webpageId` (and optional `userId`/`trigger`) via body/top-level keys.
   - Return structured responses `{statusCode, body}` consistent with other cron lambdas, including detailed error messaging for retries.

5. **Documentation & Validation Assets**
   - Update or replace `DEPLOYMENT.md` to reflect API-first architecture and CodeBuild deployment.
   - Add local invocation samples (`test_event.json`, updated `test_local.py`) that demonstrate the new event contract.

## Validation Strategy
- Run `python -m compileall` or lint-equivalent (where permitted) to catch syntax issues.
- Execute updated local test harness against mocked API client to ensure handler wiring works.
- Manually verify critical flows by simulating Jina success, RapidAPI fallback, and failure paths through unit-friendly hooks.

## Risks & Mitigations
- **Unavailable API endpoints**: Documented placeholders in service layer so backend team can implement routes; provide graceful fallback responses.
- **Behavioural regression**: Maintain existing metadata enrichment logic and logging; add unit scaffolding to cover dedup/enrichment decisions.
- **Environment drift**: Ensure config validation fails fast when required API keys are missing.

## Deliverables
- Refactored codebase with new service layer and handler.
- Updated dependency list and CI/CD artefacts.
- Migration summary capturing key decisions and follow-ups.
