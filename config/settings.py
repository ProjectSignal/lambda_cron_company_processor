"""Configuration module for the cron new company processor Lambda."""

import os
from typing import Optional


class Config:
    """Expose environment-backed configuration for the Lambda runtime."""

    def __init__(self) -> None:
        # REST API settings
        self.BASE_API_URL = self._get_env("BASE_API_URL", required=True).rstrip("/")
        self.API_KEY = self._get_env("INSIGHTS_API_KEY", required=True)
        self.API_TIMEOUT_SECONDS = int(self._get_env("API_TIMEOUT_SECONDS", default="30"))
        self.API_MAX_RETRIES = int(self._get_env("API_MAX_RETRIES", default="3"))

        # External providers
        self.JINA_READER_API_KEY = self._get_env("JINA_READER_API_KEY", required=True)
        self.JINA_BASE_URL = self._get_env("JINA_BASE_URL", default="https://r.jina.ai/")
        self.RAPIDAPI_KEY = self._get_env("RAPIDAPI_KEY")
        self.RAPIDAPI_HOST = self._get_env("RAPIDAPI_HOST", default="linkedin-api8.p.rapidapi.com")
        default_rapidapi_url = f"https://{self.RAPIDAPI_HOST or 'linkedin-api8.p.rapidapi.com'}/get-company-details"
        self.RAPIDAPI_URL = self._get_env("RAPIDAPI_URL", default=default_rapidapi_url)

        # Processing behaviour
        self.CLEANUP_ON_FAILURE = self._get_env("CLEANUP_ON_FAILURE", default="true").lower() == "true"

        # Data quality thresholds
        required_fields_raw = self._get_env(
            "REQUIRED_FIELDS_FOR_VALIDATION",
            default="name,about,website,industry,headquarters,headline,company_size,followers",
        )
        self.REQUIRED_FIELDS_FOR_VALIDATION = [field.strip() for field in required_fields_raw.split(",") if field.strip()]
        self.MIN_POPULATED_FIELDS_THRESHOLD = int(
            self._get_env("MIN_POPULATED_FIELDS_THRESHOLD", default="3")
        )

    def _get_env(self, key: str, default: Optional[str] = None, *, required: bool = False) -> str:
        value = os.getenv(key, default)
        if required and not value:
            raise ValueError(f"Required environment variable {key} is not set")
        return value

    def validate(self) -> None:
        required_vars = [
            "BASE_API_URL",
            "API_KEY",
            "JINA_READER_API_KEY",
        ]
        missing_vars = [var for var in required_vars if not getattr(self, var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

        if self.API_TIMEOUT_SECONDS <= 0:
            raise ValueError("API_TIMEOUT_SECONDS must be greater than 0")


config = Config()

__all__ = ["Config", "config"]
