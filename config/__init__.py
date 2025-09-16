"""Expose a singleton config instance for the Lambda."""

from dotenv import load_dotenv

load_dotenv()

from .settings import Config, config

__all__ = ["Config", "config"]
