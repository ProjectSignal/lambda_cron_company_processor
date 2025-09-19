# CI/CD Pipeline Test: Wed Sep 17 16:22:52 IST 2025

## Response Contract

Processing a single webpage now yields a structured response body (no JSON string) so orchestrators can read the outcome directly:

```json
{
  "statusCode": 200,
  "body": {
    "webpageId": "webpage_001",
    "nodeId": "67987b266c0b9736524ed102",
    "userId": "6797bf304791caa516f6da9e",
    "success": true,
    "via": "jina",
    "nodesUpdated": 1,
    "fieldsExtracted": 6,
    "message": "Company processed successfully"
  }
}
```
