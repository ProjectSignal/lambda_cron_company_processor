"""AWS Lambda entry point for the cron new company processor."""

from __future__ import annotations

import json
from typing import Any, Dict

from dotenv import load_dotenv

from config import config
from logging_config import setup_logger
from processor import NewCompanyProcessor

load_dotenv()

logger = setup_logger(__name__)

_processor: NewCompanyProcessor | None = None


def _get_processor() -> NewCompanyProcessor:
    global _processor
    if _processor is None:
        logger.info("Initialising new company processor")
        config.validate()
        _processor = NewCompanyProcessor()
    return _processor


def _extract_payload(event: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise lambda event formats (direct invoke, API Gateway, tests)."""
    body = event.get("body")
    if isinstance(body, str):
        try:
            body = json.loads(body or "{}")
        except json.JSONDecodeError:
            logger.warning("Unable to decode event body; defaulting to top-level keys")
            body = {}

    if isinstance(body, dict) and body:
        payload = dict(body)
    else:
        payload = dict(event)

    return payload


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Dispatch company processing actions."""
    payload = _extract_payload(event)
    action = payload.get("operation") or payload.get("action") or "process"
    webpage_id = payload.get("webpageId")

    if not webpage_id:
        logger.error("webpageId missing from event payload")
        return {
            "statusCode": 400,
            "body": json.dumps({
                "success": False,
                "error": "webpageId required",
            }),
        }

    processor = _get_processor()

    if action.lower() in {"compare", "compareapis", "compare_apis"}:
        logger.info("Running provider comparison for webpage %s", webpage_id)
        result = processor.compare_apis_for_webpage(webpage_id)
        status_code = 200 if result.get("success") else 500
        return {
            "statusCode": status_code,
            "body": json.dumps(result, default=str),
        }

    logger.info("Processing webpage %s", webpage_id)
    result = processor.process_webpage(webpage_id)
    success = bool(result.get("success"))

    response_body = {
        "webpageId": webpage_id,
        "success": success,
        "via": result.get("via"),
        "nodesUpdated": result.get("nodes_updated", 0),
    }

    if success:
        response_body["message"] = "Company processed successfully"
    else:
        response_body["error"] = result.get("error", "processing_failed")
        response_body["jinaError"] = result.get("jina_error")
        response_body["rapidapiError"] = result.get("rapidapi_error")

    status_code = 200 if success else 500
    return {
        "statusCode": status_code,
        "body": json.dumps(response_body, default=str),
    }
