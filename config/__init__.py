"""Expose a singleton config instance for the Lambda."""

# Load environment variables for local testing (optional for Lambda)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not available in Lambda environment - skip loading .env files
    pass

from .settings import Config, config

__all__ = ["Config", "config"]
