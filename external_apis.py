import requests
import re
from typing import Optional, Dict, Any, Protocol
from abc import ABC, abstractmethod
import time
import logging

from config import config
from logging_config import setup_logger

logger = setup_logger(__name__)


def extract_linkedin_username(url: str) -> Optional[str]:
    """Extracts the LinkedIn username/identifier from various URL patterns."""
    if not url:
        return None
    
    # Match linkedin.com/ followed by any segment (like company, school, in),
    # then capture the next segment (the username/identifier) before a slash or query params.
    # Examples:
    # - linkedin.com/company/the-username/ -> the-username
    # - linkedin.com/school/the-username?a=b -> the-username
    # - linkedin.com/in/the-username -> the-username
    match = re.search(r'linkedin\.com/[^/]+/([^/?]+)', url)
    if match:
        return match.group(1)  # Return the captured username/identifier
    
    logger.warning(f"Could not extract LinkedIn username/identifier from URL pattern: {url}")
    return None


class CompanyDataFetcher(ABC):
    """Abstract base class for company data fetchers to enable easy provider swapping"""
    
    @abstractmethod
    def fetch(self, url_or_identifier: str) -> Optional[Dict[str, Any]]:
        """Fetch company data from external API"""
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the name of this provider"""
        pass


class JinaFetcher(CompanyDataFetcher):
    """Fetcher for Jina AI Reader API with HTML fetching and error handling"""
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, 
                 timeout: Optional[int] = None, retry_delay: Optional[float] = None):
        self.api_key = api_key or config.JINA_READER_API_KEY
        self.base_url = base_url or config.JINA_BASE_URL
        self.timeout = timeout or config.REQUEST_TIMEOUT
        self.retry_delay = retry_delay or config.SLEEP_BETWEEN_REQUESTS
        
        if not self.api_key:
            raise ValueError("Jina AI API key is required")
    
    def fetch(self, url: str) -> Optional[str]:
        """Fetches HTML content for a given URL using the Jina AI Reader API."""
        target_url = f"{self.base_url.rstrip('/')}/{url}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "text/html",  # Request HTML format
            "X-Return-Format": "html"
        }
        
        logger.info(f"Fetching URL via Jina: {url}")
        
        try:
            response = requests.get(target_url, headers=headers, timeout=self.timeout)
            response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)
            
            logger.info(f"Successfully fetched HTML for {url}, status: {response.status_code}")
            return response.text
            
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout fetching URL: {url}")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error fetching URL {url}: {e.response.status_code} - {e.response.text[:200]}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error fetching URL {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching URL {url}: {e}")
            return None
    
    def get_provider_name(self) -> str:
        return "jina"


class RapidAPIFetcher(CompanyDataFetcher):
    """Fetcher for RapidAPI LinkedIn company data with response parsing"""
    
    def __init__(self, api_key: Optional[str] = None, api_host: Optional[str] = None, 
                 api_url: Optional[str] = None, timeout: Optional[int] = None,
                 retry_delay: Optional[float] = None):
        self.api_key = api_key or config.RAPIDAPI_KEY
        self.api_host = api_host or config.RAPIDAPI_HOST
        self.api_url = api_url or config.RAPIDAPI_URL
        self.timeout = timeout or config.REQUEST_TIMEOUT
        self.retry_delay = retry_delay or config.SLEEP_BETWEEN_REQUESTS
        
        if not self.api_key:
            logger.warning("RapidAPI key not configured - this fetcher will not be functional")
    
    def fetch(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetches company data using RapidAPI, extracts username from URL first."""
        if not self.api_key:
            logger.warning("RapidAPI key not configured, skipping API call")
            return None
        
        # Extract LinkedIn username from URL
        username = extract_linkedin_username(url)
        if not username:
            logger.error(f"Could not extract username from URL for RapidAPI: {url}")
            return None
        
        return self._fetch_by_username(username)
    
    def _fetch_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Fetches company data by LinkedIn username using RapidAPI."""
        headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": self.api_host
        }
        querystring = {"username": username}
        
        try:
            logger.info(f"Calling RapidAPI for username: {username}")
            response = requests.get(self.api_url, headers=headers, params=querystring, timeout=self.timeout)
            response.raise_for_status()
            response_json = response.json()
            
            if response_json.get("success") and response_json.get("data"):
                logger.info(f"Successfully fetched data from RapidAPI for {username}")
                return response_json["data"]
            else:
                error_message = response_json.get("message", "No data returned")
                logger.error(f"RapidAPI returned unsuccessful response for {username}: {error_message}")
                return None
                
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout calling RapidAPI for {username}")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error calling RapidAPI for {username}: {e.response.status_code} - {e.response.text[:200]}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error calling RapidAPI for {username}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling RapidAPI for {username}: {e}")
            return None
    
    def get_provider_name(self) -> str:
        return "rapidapi"

