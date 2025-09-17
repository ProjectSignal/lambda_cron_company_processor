"""REST-backed data access helpers for company processing."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from clients import ServiceClients, get_clients
from logging_config import setup_logger

logger = setup_logger(__name__)


class CompanyDataService:
    """Wrap Brace API calls used by the company processor."""

    def __init__(self, clients: Optional[ServiceClients] = None) -> None:
        self._clients = clients or get_clients()
        self._api = self._clients.api

    def fetch_webpage(self, webpage_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a webpage document by id."""
        try:
            # API Route: webpages.getById, Input: params {"webpageId": id}, Output: {"data": {...}}
            response = self._api.get(f"webpages/{webpage_id}")
            if isinstance(response, dict) and response.get("success") is False:
                logger.error("Webpage fetch failed for %s: %s", webpage_id, response.get("message"))
                return None
            if isinstance(response, dict) and "data" in response:
                return response["data"]
            return response
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to load webpage %s via API: %s", webpage_id, exc)
            return None

    def list_test_webpages(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Return webpages for provider comparison tests."""
        payload = {"limit": limit}
        try:
            # API Route: webpages.listTestCandidates, Input: payload, Output: {"webpages": [...]}
            response = self._api.request("POST", "webpages/list-test-candidates", payload)
            if isinstance(response, dict) and response.get("success") is False:
                logger.error("List test webpages failed: %s", response.get("message"))
                return []
            return response.get("webpages", []) or response.get("data", [])
        except Exception as exc:
            logger.error("Failed to load test webpages: %s", exc)
            return []

    def update_webpage(self, webpage_id: str, update_data: Dict[str, Any]) -> bool:
        """Persist scraped company data."""
        try:
            # API Route: webpages.updateById, Input: update_data, Output: {"success": bool}
            response = self._api.request("PATCH", f"webpages/{webpage_id}", update_data)
            if isinstance(response, dict):
                if response.get("success") is False:
                    logger.error("Webpage update failed for %s: %s", webpage_id, response.get("message"))
                    return False
                if response.get("success") is not None:
                    return bool(response.get("success"))
                if response.get("data"):
                    return True
            return True
        except Exception as exc:
            logger.error("Failed to update webpage %s: %s", webpage_id, exc)
            return False

    def mark_webpage_failed(self, webpage_id: str, error_type: str, error_message: str) -> bool:
        """Mark a webpage extraction attempt as failed."""
        payload = {
            "webpageId": webpage_id,
            "errorType": error_type,
            "errorMessage": error_message,
        }
        try:
            # API Route: webpages.markFailed, Input: payload, Output: {"success": bool}
            response = self._api.request("POST", "webpages/mark-failed", payload)
            if isinstance(response, dict) and response.get("success") is False:
                logger.error("Marking webpage %s failed: %s", webpage_id, response.get("message"))
                return False
            return bool(response.get("success", True))
        except Exception as exc:
            logger.error("Failed to mark webpage %s as failed: %s", webpage_id, exc)
            return False

    def update_nodes_with_company_data(self, webpage_id: str, company_data: Dict[str, Any]) -> int:
        """Propagate company metadata into associated nodes."""
        payload = {
            "webpageId": webpage_id,
            "companyData": company_data,
        }
        try:
            # API Route: nodes.applyCompanyEnrichment, Input: payload, Output: {"updated": int}
            response = self._api.request("POST", "nodes/apply-company-enrichment", payload)
            if isinstance(response, dict) and response.get("success") is False:
                logger.error("Company enrichment failed for %s: %s", webpage_id, response.get("message"))
                return 0
            return int(response.get("updated", response.get("count", 0)))
        except Exception as exc:
            logger.error("Failed to propagate company data for %s: %s", webpage_id, exc)
            return 0

    def cleanup_failed_webpage(self, webpage_id: str) -> bool:
        """Remove webpage references and delete the record after fatal failure."""
        payload = {"webpageId": webpage_id}
        try:
            # API Route: webpages.cleanupFailed, Input: payload, Output: {"success": bool}
            response = self._api.request("POST", "webpages/cleanup-failed", payload)
            if isinstance(response, dict) and response.get("success") is False:
                logger.error("Cleanup failed for webpage %s: %s", webpage_id, response.get("message"))
                return False
            return bool(response.get("success", True))
        except Exception as exc:
            logger.error("Failed to cleanup webpage %s: %s", webpage_id, exc)
            return False

    def get_processing_stats(self) -> Dict[str, Any]:
        """Fetch aggregate processing statistics for reporting."""
        try:
            # API Route: webpages.processingStats, Input: {}, Output: {"stats": {...}}
            response = self._api.get("webpages/processing-stats")
            if isinstance(response, dict) and response.get("success") is False:
                logger.error("Processing stats fetch failed: %s", response.get("message"))
                return {}
            return response.get("stats") or response
        except Exception as exc:
            logger.error("Failed to retrieve processing stats: %s", exc)
            return {}


__all__ = ["CompanyDataService"]
