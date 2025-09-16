from typing import Dict, Any, Optional
import logging

from config import config
from external_apis import JinaFetcher, RapidAPIFetcher
from data_mapper import map_rapidapi_to_standard, validate_extracted_data, add_processing_metadata
from bs.linkedinCompanyNewScraper import html_to_object
from services import CompanyDataService
from logging_config import setup_logger

logger = setup_logger(__name__)


class NewCompanyProcessor:
    """Core NewCompanyProcessor class that orchestrates the company webpage processing logic."""
    
    def __init__(self, data_service: Optional[CompanyDataService] = None):
        self.service = data_service or CompanyDataService()
        self.jina_fetcher = JinaFetcher()
        self.rapidapi_fetcher = RapidAPIFetcher() if config.RAPIDAPI_KEY else None
    
    def process_webpage(self, webpage_id: str) -> Dict[str, Any]:
        """
        Process a single webpage by attempting Jina first, then RapidAPI fallback.
        Returns structured result indicating success/failure and processing method used.
        """
        try:
            logger.info(f"Processing webpage: {webpage_id}")
            
            # Retrieve webpage from API
            webpage = self.service.fetch_webpage(webpage_id)
            if not webpage:
                error_msg = f"Webpage {webpage_id} not found"
                logger.error(error_msg)
                return {"success": False, "error": error_msg, "webpage_id": webpage_id}
            
            url = webpage.get("url")
            if not url:
                error_msg = f"No URL found for webpage {webpage_id}"
                logger.error(error_msg)
                self.service.mark_webpage_failed(webpage_id, "missing_url", error_msg)
                return {"success": False, "error": error_msg, "webpage_id": webpage_id}
            
            logger.info(f"Processing URL: {url}")
            
            # Try Jina first
            jina_result = self.process_with_jina(webpage_id, url)
            if jina_result["success"]:
                return jina_result
            
            logger.warning(f"Jina processing failed for {webpage_id}, trying RapidAPI fallback")
            
            # Try RapidAPI as fallback only if API key is configured
            if self.rapidapi_fetcher:
                rapidapi_result = self.process_with_rapidapi(webpage_id, url)
                if rapidapi_result["success"]:
                    return rapidapi_result
            else:
                logger.warning(f"RapidAPI key not configured, skipping RapidAPI fallback for {webpage_id}")
                rapidapi_result = {"success": False, "error": "rapidapi_key_not_configured"}
            
            # Both methods failed
            error_msg = f"Both Jina and RapidAPI failed for webpage {webpage_id}"
            logger.error(error_msg)
            
            # Cleanup if configured
            if config.CLEANUP_ON_FAILURE:
                logger.info(f"Cleaning up failed webpage {webpage_id}")
                self.service.cleanup_failed_webpage(webpage_id)
            else:
                self.service.mark_webpage_failed(webpage_id, "both_apis_failed", error_msg)
            
            return {
                "success": False,
                "error": "both_apis_failed",
                "webpage_id": webpage_id,
                "jina_error": jina_result.get("error"),
                "rapidapi_error": rapidapi_result.get("error")
            }
            
        except Exception as e:
            error_msg = f"Unexpected error processing webpage {webpage_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            self.service.mark_webpage_failed(webpage_id, "processing_error", error_msg)
            
            return {"success": False, "error": error_msg, "webpage_id": webpage_id}
    
    def process_with_jina(self, webpage_id: str, url: str) -> Dict[str, Any]:
        """Process webpage using Jina AI to fetch HTML and parse it."""
        try:
            logger.info(f"Attempting Jina processing for webpage {webpage_id}")
            
            # Fetch HTML via Jina
            html_content = self.jina_fetcher.fetch(url)
            if not html_content:
                self.service.mark_webpage_failed(webpage_id, "jina_fetch_failed", "Failed to fetch HTML from Jina API")
                return {"success": False, "error": "jina_fetch_failed", "webpage_id": webpage_id}
            
            # Parse HTML with html_to_object
            try:
                extracted_data = html_to_object(html_content)
                if not extracted_data:
                    self.service.mark_webpage_failed(webpage_id, "html_parsing_failed", "HTML parsing returned no data")
                    return {"success": False, "error": "html_parsing_failed", "webpage_id": webpage_id}
            except Exception as e:
                error_msg = f"Error parsing HTML for webpage {webpage_id}: {str(e)}"
                logger.error(error_msg)
                self.service.mark_webpage_failed(webpage_id, "html_parsing_error", error_msg)
                return {"success": False, "error": f"html_parsing_error: {str(e)}", "webpage_id": webpage_id}
            
            # Validate data quality
            if not validate_extracted_data(extracted_data):
                self.service.mark_webpage_failed(webpage_id, "data_validation_failed", "Insufficient data extracted from HTML")
                return {"success": False, "error": "data_validation_failed", "webpage_id": webpage_id}
            
            # Add processing metadata
            update_data = add_processing_metadata(extracted_data, "jina", url)
            
            # Update database
            success = self.service.update_webpage(webpage_id, update_data)
            if not success:
                self.service.mark_webpage_failed(webpage_id, "database_update_failed", "Failed to update webpage in database")
                return {"success": False, "error": "database_update_failed", "webpage_id": webpage_id}
            
            # Update nodes with company data
            updated_nodes = self.service.update_nodes_with_company_data(webpage_id, extracted_data)
            
            logger.info(f"Successfully processed webpage {webpage_id} with Jina (updated {updated_nodes} nodes)")
            return {
                "success": True,
                "via": "jina",
                "webpage_id": webpage_id,
                "nodes_updated": updated_nodes,
                "fields_extracted": len([k for k, v in extracted_data.items() if v])
            }
            
        except Exception as e:
            error_msg = f"Jina processing error for webpage {webpage_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.service.mark_webpage_failed(webpage_id, "jina_processing_error", error_msg)
            return {"success": False, "error": error_msg, "webpage_id": webpage_id}
    
    def process_with_rapidapi(self, webpage_id: str, url: str) -> Dict[str, Any]:
        """Process webpage using RapidAPI as fallback."""
        try:
            logger.info(f"Attempting RapidAPI processing for webpage {webpage_id}")
            
            # Fetch data from RapidAPI
            rapid_data = self.rapidapi_fetcher.fetch(url)
            if not rapid_data:
                self.service.mark_webpage_failed(webpage_id, "rapidapi_failed_api", "RapidAPI returned no data")
                return {"success": False, "error": "rapidapi_fetch_failed", "webpage_id": webpage_id}
            
            # Map RapidAPI data to standard format
            try:
                mapped_data = map_rapidapi_to_standard(rapid_data)
                if not mapped_data:
                    self.service.mark_webpage_failed(webpage_id, "data_mapping_failed", "RapidAPI data mapping failed")
                    return {"success": False, "error": "data_mapping_failed", "webpage_id": webpage_id}
            except Exception as e:
                error_msg = f"Error mapping RapidAPI data for webpage {webpage_id}: {str(e)}"
                logger.error(error_msg)
                self.service.mark_webpage_failed(webpage_id, "rapidapi_mapping_error", error_msg)
                return {"success": False, "error": f"data_mapping_error: {str(e)}", "webpage_id": webpage_id}
            
            # Validate mapped data
            if not validate_extracted_data(mapped_data):
                self.service.mark_webpage_failed(webpage_id, "data_validation_failed", "RapidAPI data validation failed")
                return {"success": False, "error": "data_validation_failed", "webpage_id": webpage_id}
            
            # Add processing metadata
            update_data = add_processing_metadata(mapped_data, "rapidapi", url)
            
            # Update database
            success = self.service.update_webpage(webpage_id, update_data)
            if not success:
                self.service.mark_webpage_failed(webpage_id, "database_update_failed", "Failed to update webpage with RapidAPI data")
                return {"success": False, "error": "database_update_failed", "webpage_id": webpage_id}
            
            # Update nodes with company data
            updated_nodes = self.service.update_nodes_with_company_data(webpage_id, mapped_data)
            
            logger.info(f"Successfully processed webpage {webpage_id} with RapidAPI (updated {updated_nodes} nodes)")
            return {
                "success": True,
                "via": "rapidapi",
                "webpage_id": webpage_id,
                "nodes_updated": updated_nodes,
                "fields_extracted": len([k for k, v in mapped_data.items() if v])
            }
            
        except Exception as e:
            error_msg = f"RapidAPI processing error for webpage {webpage_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.service.mark_webpage_failed(webpage_id, "rapidapi_processing_error", error_msg)
            return {"success": False, "error": error_msg, "webpage_id": webpage_id}
    
    def compare_apis_for_webpage(self, webpage_id: str) -> Dict[str, Any]:
        """
        Compare both Jina and RapidAPI results for the same webpage.
        Returns detailed comparison data for testing purposes.
        """
        try:
            logger.info(f"Starting API comparison for webpage: {webpage_id}")
            
            # Get webpage data
            webpage = self.service.fetch_webpage(webpage_id)
            if not webpage:
                return {
                    "success": False,
                    "error": f"Webpage {webpage_id} not found",
                    "webpage_id": webpage_id
                }
            
            url = webpage.get("url")
            if not url:
                return {
                    "success": False,
                    "error": f"No URL found for webpage {webpage_id}",
                    "webpage_id": webpage_id
                }
            
            # Test both APIs
            jina_result = self._test_jina_only(webpage_id, url)
            rapidapi_result = self._test_rapidapi_only(webpage_id, url)
            
            return {
                "success": True,
                "webpage_id": webpage_id,
                "url": url,
                "jina": jina_result,
                "rapidapi": rapidapi_result,
                "comparison": self._generate_field_comparison(jina_result, rapidapi_result)
            }
            
        except Exception as e:
            error_msg = f"API comparison error for webpage {webpage_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg, "webpage_id": webpage_id}
    
    def _test_jina_only(self, webpage_id: str, url: str) -> Dict[str, Any]:
        """Test Jina API independently and return detailed results."""
        import time
        start_time = time.time()
        
        try:
            # Fetch HTML via Jina
            html_content = self.jina_fetcher.fetch(url)
            fetch_time = time.time() - start_time
            
            if not html_content:
                return {
                    "success": False,
                    "error": "Failed to fetch HTML from Jina API",
                    "fetch_time": fetch_time,
                    "data": None
                }
            
            # Parse HTML
            parse_start = time.time()
            extracted_data = html_to_object(html_content)
            parse_time = time.time() - parse_start
            total_time = time.time() - start_time
            
            if not extracted_data:
                return {
                    "success": False,
                    "error": "HTML parsing returned no data",
                    "fetch_time": fetch_time,
                    "parse_time": parse_time,
                    "total_time": total_time,
                    "data": None
                }
            
            # Validate data
            is_valid = validate_extracted_data(extracted_data)
            
            return {
                "success": True,
                "fetch_time": fetch_time,
                "parse_time": parse_time,
                "total_time": total_time,
                "data_valid": is_valid,
                "fields_count": len([k for k, v in extracted_data.items() if v and str(v).strip()]),
                "data": extracted_data
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Jina processing error: {str(e)}",
                "fetch_time": time.time() - start_time,
                "data": None
            }
    
    def _test_rapidapi_only(self, webpage_id: str, url: str) -> Dict[str, Any]:
        """Test RapidAPI independently and return detailed results."""
        import time
        start_time = time.time()
        
        try:
            if not self.rapidapi_fetcher:
                return {
                    "success": False,
                    "error": "RapidAPI not configured",
                    "fetch_time": 0,
                    "data": None
                }
            
            # Fetch data from RapidAPI
            rapid_data = self.rapidapi_fetcher.fetch(url)
            fetch_time = time.time() - start_time
            
            if not rapid_data:
                return {
                    "success": False,
                    "error": "RapidAPI returned no data",
                    "fetch_time": fetch_time,
                    "data": None
                }
            
            # Map data
            map_start = time.time()
            mapped_data = map_rapidapi_to_standard(rapid_data)
            map_time = time.time() - map_start
            total_time = time.time() - start_time
            
            if not mapped_data:
                return {
                    "success": False,
                    "error": "RapidAPI data mapping failed",
                    "fetch_time": fetch_time,
                    "map_time": map_time,
                    "total_time": total_time,
                    "data": None
                }
            
            # Validate data
            is_valid = validate_extracted_data(mapped_data)
            
            return {
                "success": True,
                "fetch_time": fetch_time,
                "map_time": map_time,
                "total_time": total_time,
                "data_valid": is_valid,
                "fields_count": len([k for k, v in mapped_data.items() if v and str(v).strip()]),
                "data": mapped_data,
                "raw_data": rapid_data
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"RapidAPI processing error: {str(e)}",
                "fetch_time": time.time() - start_time,
                "data": None
            }
    
    def _generate_field_comparison(self, jina_result: Dict[str, Any], rapidapi_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate field-by-field comparison between APIs."""
        comparison = {
            "jina_success": jina_result.get("success", False),
            "rapidapi_success": rapidapi_result.get("success", False),
            "field_comparison": {},
            "summary": {}
        }
        
        if not jina_result.get("success") and not rapidapi_result.get("success"):
            comparison["summary"]["winner"] = "both_failed"
            return comparison
        
        jina_data = jina_result.get("data", {}) or {}
        rapidapi_data = rapidapi_result.get("data", {}) or {}
        
        # Compare key fields
        key_fields = ["name", "about", "website", "industry", "headquarters", "headline", "company_size", "followers", "specialties"]
        
        for field in key_fields:
            jina_value = jina_data.get(field, "")
            rapidapi_value = rapidapi_data.get(field, "")
            
            comparison["field_comparison"][field] = {
                "jina": jina_value,
                "rapidapi": rapidapi_value,
                "both_have_data": bool(jina_value and rapidapi_value),
                "only_jina": bool(jina_value and not rapidapi_value),
                "only_rapidapi": bool(rapidapi_value and not jina_value),
                "neither": bool(not jina_value and not rapidapi_value)
            }
        
        # Generate summary
        jina_fields = len([k for k, v in jina_data.items() if v and str(v).strip()])
        rapidapi_fields = len([k for k, v in rapidapi_data.items() if v and str(v).strip()])
        
        comparison["summary"] = {
            "jina_fields_count": jina_fields,
            "rapidapi_fields_count": rapidapi_fields,
            "jina_time": jina_result.get("total_time", 0),
            "rapidapi_time": rapidapi_result.get("total_time", 0),
            "winner_by_fields": "jina" if jina_fields > rapidapi_fields else "rapidapi" if rapidapi_fields > jina_fields else "tie",
            "winner_by_speed": "jina" if jina_result.get("total_time", 999) < rapidapi_result.get("total_time", 999) else "rapidapi"
        }
        
        return comparison
    
    
