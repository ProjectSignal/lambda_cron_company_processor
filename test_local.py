#!/usr/bin/env python3
"""Quick smoke test harness for lambda_cron_new_company_processor."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict
from unittest.mock import patch

# Provide required env vars before importing Lambda modules
os.environ.setdefault("BASE_API_URL", "https://api.dev.brace.test")
os.environ.setdefault("INSIGHTS_API_KEY", "test-key")
os.environ.setdefault("JINA_READER_API_KEY", "test-jina")
os.environ.setdefault("RAPIDAPI_KEY", "")

import lambda_handler


@dataclass
class FakeService:
    """Minimal stub emulating CompanyDataService responses for tests."""

    def fetch_webpage(self, webpage_id: str) -> Dict[str, Any]:
        return {
            "_id": webpage_id,
            "url": "https://www.linkedin.com/company/brace-test/",
            "platform": "linkedin",
        }

    def list_test_webpages(self, limit: int = 5):  # pragma: no cover - auxiliary helper
        return []

    def update_webpage(self, webpage_id: str, update_data: Dict[str, Any]) -> bool:
        print(f"[FakeService] update_webpage called for {webpage_id} -> keys: {list(update_data.keys())}")
        return True

    def mark_webpage_failed(self, webpage_id: str, error_type: str, error_message: str) -> bool:
        print(f"[FakeService] mark_webpage_failed: {webpage_id} {error_type} {error_message}")
        return True

    def update_nodes_with_company_data(self, webpage_id: str, company_data: Dict[str, Any]) -> int:
        print(f"[FakeService] update_nodes_with_company_data for {webpage_id}")
        return 2

    def cleanup_failed_webpage(self, webpage_id: str) -> bool:
        print(f"[FakeService] cleanup_failed_webpage for {webpage_id}")
        return True

    def get_processing_stats(self):  # pragma: no cover - auxiliary helper
        return {}


SAMPLE_HTML = """
<html>
  <body>
    <h1 class="top-card-layout__title">Brace Test Company</h1>
  </body>
</html>
"""


def run_smoke_test() -> None:
    # Reset cached processor so our patches take effect each run
    lambda_handler._processor = None  # type: ignore[attr-defined]

    event = {
        "webpageId": "fake-webpage-123",
        "trigger": "local-test",
    }

    with patch("processor.CompanyDataService", new=FakeService):
        with patch("external_apis.JinaFetcher.fetch", return_value=SAMPLE_HTML):
            with patch("data_mapper.validate_extracted_data", return_value=True):
                response = lambda_handler.lambda_handler(event, None)

    print("Response:")
    print(json.dumps(response, indent=2))


if __name__ == "__main__":
    run_smoke_test()
