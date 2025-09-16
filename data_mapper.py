import datetime
from typing import Dict, Any, Optional, List
import re
import logging

from config import config

logger = logging.getLogger(__name__)


def map_rapidapi_to_standard(rapid_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Maps data from RapidAPI response to standard database format.
    Maintains compatibility with existing RapidAPI to standard format mapping from newCompanyProcessor.py
    """
    payload = {}
    now = datetime.datetime.now(datetime.timezone.utc)

    # Direct/Equivalent Mappings (Prioritize RapidAPI data)
    payload["name"] = rapid_data.get("name")
    payload["about"] = rapid_data.get("description")  # Map description to about
    payload["headline"] = rapid_data.get("tagline")  # Map tagline to headline
    payload["website"] = rapid_data.get("website")
    
    if rapid_data.get("headquarter"):
        payload["headquarters"] = rapid_data["headquarter"].get("city")  # Get city from headquarter object
    
    if rapid_data.get("industries"):
        payload["industry"] = rapid_data["industries"][0] if rapid_data["industries"] else None  # Take the first industry
    
    if rapid_data.get("specialities"):
        payload["specialties"] = ", ".join(rapid_data["specialities"])  # Join specialties array into a string
    
    if rapid_data.get("founded"):
        payload["founded"] = str(rapid_data["founded"].get("year")) if rapid_data["founded"].get("year") else None

    # Size and Followers
    payload["company_size"] = rapid_data.get("staffCountRange") or str(rapid_data.get("staffCount"))  # Prefer range, fallback to count
    payload["followers"] = str(rapid_data.get("followerCount")) if rapid_data.get("followerCount") is not None else None

    # Add New Fields from RapidAPI
    payload["universalName"] = rapid_data.get("universalName")
    payload["phone"] = rapid_data.get("phone")
    
    if rapid_data.get("logos") and len(rapid_data.get("logos")) > 0:
        last_logo = rapid_data.get("logos")[-1]
        payload["companyLogo"] = last_logo.get("url") if last_logo and "url" in last_logo else None
    
    payload["staffCount"] = rapid_data.get("staffCount")  # Explicit staff count
    payload["locations"] = rapid_data.get("locations")  # Store locations array
    payload["crunchbaseUrl"] = rapid_data.get("crunchbaseUrl")
    payload["fundingData"] = rapid_data.get("fundingData")
    
    # 'type' might conflict, maybe name it rapidApiType? Let's stick with 'type' for now if it's empty often
    payload["type"] = rapid_data.get("type") or payload.get("type")  # Keep existing type if RapidAPI one is empty

    # Metadata - will be added by add_processing_metadata function
    # payload["processed_via"] = "rapidapi"  # Mark processing source

    # Remove keys with None values before returning
    return {k: v for k, v in payload.items() if v is not None}


def map_jina_to_standard(jina_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Maps data extracted from Jina HTML parsing to standard database format.
    This assumes html_to_object from linkedinCompanyNewScraper returns structured data.
    """
    # For Jina data, we expect it's already in a good format from html_to_object
    # but we might need to normalize some fields
    payload = {}
    
    # Copy over standard fields
    standard_fields = [
        "name", "about", "website", "industry", "headquarters", 
        "headline", "company_size", "followers", "specialties", 
        "type", "founded", "companyLogo"
    ]
    
    for field in standard_fields:
        if field in jina_data and jina_data[field]:
            payload[field] = jina_data[field]
    
    # Clean and normalize data
    payload = normalize_company_data(payload)
    
    return payload


def normalize_company_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize and clean company data fields."""
    normalized = data.copy()
    
    # Clean website URLs
    if "website" in normalized and normalized["website"]:
        website = str(normalized["website"]).strip()
        if website and not website.startswith(('http://', 'https://')):
            normalized["website"] = f"https://{website}"
    
    # Normalize company size format
    if "company_size" in normalized and normalized["company_size"]:
        size = str(normalized["company_size"]).strip()
        # Standardize common formats
        size_mappings = {
            "1-10": "1-10 employees",
            "11-50": "11-50 employees", 
            "51-200": "51-200 employees",
            "201-500": "201-500 employees",
            "501-1000": "501-1000 employees",
            "1001-5000": "1001-5000 employees",
            "5001-10000": "5001-10000 employees",
            "10000+": "10,001+ employees"
        }
        normalized["company_size"] = size_mappings.get(size, size)
    
    # Clean and normalize text fields
    text_fields = ["name", "about", "headline", "headquarters", "industry"]
    for field in text_fields:
        if field in normalized and normalized[field]:
            # Basic text cleaning
            text = str(normalized[field]).strip()
            # Remove excessive whitespace
            text = re.sub(r'\s+', ' ', text)
            normalized[field] = text
    
    return normalized


def validate_extracted_data(data: Dict[str, Any], min_required: Optional[int] = None) -> bool:
    """
    Validate if extracted data has minimum required fields.
    Uses configurable validation thresholds and field requirements.
    """
    min_required = min_required or config.MIN_POPULATED_FIELDS_THRESHOLD
    key_fields = config.REQUIRED_FIELDS_FOR_VALIDATION
    
    # Count non-empty, non-None fields
    valid_fields = 0
    populated_fields = []
    
    for field in key_fields:
        value = data.get(field)
        if value and str(value).strip():  # Check for non-empty string values
            valid_fields += 1
            populated_fields.append(field)
    
    is_valid = valid_fields >= min_required
    
    if is_valid:
        print(f"Data validation passed: {valid_fields}/{len(key_fields)} key fields present (required: {min_required})")
        print(f"Populated fields: {', '.join(populated_fields)}")
    else:
        print(f"Data validation failed: only {valid_fields}/{len(key_fields)} key fields present (minimum required: {min_required})")
        print(f"Populated fields: {', '.join(populated_fields) if populated_fields else 'None'}")
        missing_fields = [f for f in key_fields if not data.get(f) or not str(data.get(f)).strip()]
        print(f"Missing/empty fields: {', '.join(missing_fields)}")
    
    return is_valid


def add_processing_metadata(data: Dict[str, Any], method: str, original_url: str = None) -> Dict[str, Any]:
    """Add metadata fields for processing tracking with enhanced information."""
    now = datetime.datetime.now(datetime.timezone.utc)
    
    metadata = {
        "platform": "linkedin",
        "scrapped": True,
        "extracted": True,
        "processed_via": method,
        "extractedAt": now,
        "scrappedAt": now,
        "processedAt": now,
        "websiteMarkdownStatus": "not_attempted",
        "processor_version": "new_company_processor_v1",
        "worker_id": config.WORKER_ID
    }
    
    # Add method-specific metadata
    if method == "jina":
        metadata["extraction_method"] = "html_parsing"
    elif method == "rapidapi":
        metadata["extraction_method"] = "api_direct"
    
    # Merge with existing data, ensuring metadata doesn't override important data
    result = {**data, **metadata}
    
    # Preserve original URL if provided (prevents overwriting with empty string from html_to_object)
    if original_url:
        result["url"] = original_url
    
    # Remove None values
    return {k: v for k, v in result.items() if v is not None}


def validate_provider_data(data: Dict[str, Any], provider: str) -> Dict[str, Any]:
    """
    Validate and report on data quality from a specific provider.
    Returns enhanced data with quality metrics.
    """
    if not data:
        return {
            "valid": False, 
            "quality_score": 0, 
            "quality_report": "No data provided",
            "data": None
        }
    
    quality_metrics = {
        "total_fields": len(data),
        "populated_fields": len([v for v in data.values() if v and str(v).strip()]),
        "critical_fields_present": 0,
        "provider": provider
    }
    
    # Check critical fields
    critical_fields = ["name", "about", "website"]
    for field in critical_fields:
        if data.get(field) and str(data.get(field)).strip():
            quality_metrics["critical_fields_present"] += 1
    
    # Calculate quality score (0-100)
    max_possible_score = len(config.REQUIRED_FIELDS_FOR_VALIDATION) * 10
    field_score = quality_metrics["populated_fields"] * 10
    critical_bonus = quality_metrics["critical_fields_present"] * 15
    
    quality_score = min(100, (field_score + critical_bonus) * 100 // max_possible_score)
    
    is_valid = validate_extracted_data(data)
    
    quality_report = f"Provider: {provider}, Score: {quality_score}/100, " \
                    f"Fields: {quality_metrics['populated_fields']}/{quality_metrics['total_fields']}, " \
                    f"Critical: {quality_metrics['critical_fields_present']}/{len(critical_fields)}"
    
    return {
        "valid": is_valid,
        "quality_score": quality_score,
        "quality_report": quality_report,
        "quality_metrics": quality_metrics,
        "data": data
    }


def merge_provider_data(primary_data: Dict[str, Any], fallback_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge data from multiple providers, giving priority to primary provider
    but filling in gaps with fallback data.
    """
    if not primary_data:
        return fallback_data or {}
    
    if not fallback_data:
        return primary_data
    
    merged = fallback_data.copy()  # Start with fallback as base
    
    # Override with primary data (primary takes precedence)
    for key, value in primary_data.items():
        if value and str(value).strip():  # Only override with non-empty values
            merged[key] = value
    
    return merged


def calculate_data_quality_score(data: Dict[str, Any], processing_time: float = 0) -> Dict[str, Any]:
    """
    Calculate comprehensive quality score for API comparison.
    Returns detailed quality metrics for benchmarking API performance.
    """
    if not data:
        return {
            "overall_score": 0,
            "field_score": 0,
            "critical_score": 0,
            "completeness_score": 0,
            "speed_score": 0,
            "populated_fields": 0,
            "total_fields": 0,
            "critical_fields": 0,
            "grade": "F"
        }
    
    # Define field weights and critical fields
    key_fields = config.REQUIRED_FIELDS_FOR_VALIDATION
    critical_fields = ["name", "about", "website", "industry"]
    
    # Calculate field metrics
    populated_fields = len([k for k, v in data.items() if v and str(v).strip()])
    total_fields = len(key_fields)
    critical_populated = len([f for f in critical_fields if data.get(f) and str(data.get(f)).strip()])
    
    # Calculate scores (0-100 scale)
    field_score = (populated_fields / total_fields) * 100 if total_fields > 0 else 0
    critical_score = (critical_populated / len(critical_fields)) * 100 if critical_fields else 0
    completeness_score = min(100, (populated_fields / len(key_fields)) * 100) if key_fields else 0
    
    # Speed score (faster = better, capped at 10 seconds)
    speed_score = max(0, 100 - (processing_time * 10)) if processing_time > 0 else 100
    
    # Overall score (weighted average)
    overall_score = (
        field_score * 0.3 +           # 30% weight on field population
        critical_score * 0.4 +        # 40% weight on critical fields
        completeness_score * 0.2 +    # 20% weight on completeness
        speed_score * 0.1             # 10% weight on speed
    )
    
    # Determine grade
    if overall_score >= 90:
        grade = "A+"
    elif overall_score >= 80:
        grade = "A"
    elif overall_score >= 70:
        grade = "B"
    elif overall_score >= 60:
        grade = "C"
    elif overall_score >= 50:
        grade = "D"
    else:
        grade = "F"
    
    return {
        "overall_score": round(overall_score, 1),
        "field_score": round(field_score, 1),
        "critical_score": round(critical_score, 1),
        "completeness_score": round(completeness_score, 1),
        "speed_score": round(speed_score, 1),
        "populated_fields": populated_fields,
        "total_fields": total_fields,
        "critical_fields": critical_populated,
        "grade": grade,
        "processing_time": processing_time
    }


def compare_api_quality(jina_data: Dict[str, Any], rapidapi_data: Dict[str, Any], 
                       jina_time: float = 0, rapidapi_time: float = 0) -> Dict[str, Any]:
    """
    Compare quality metrics between Jina and RapidAPI results.
    Returns detailed comparison with winner determination.
    """
    jina_quality = calculate_data_quality_score(jina_data, jina_time)
    rapidapi_quality = calculate_data_quality_score(rapidapi_data, rapidapi_time)
    
    # Determine winners in each category
    comparison = {
        "jina": jina_quality,
        "rapidapi": rapidapi_quality,
        "winners": {
            "overall": "jina" if jina_quality["overall_score"] > rapidapi_quality["overall_score"] 
                      else "rapidapi" if rapidapi_quality["overall_score"] > jina_quality["overall_score"] 
                      else "tie",
            "fields": "jina" if jina_quality["populated_fields"] > rapidapi_quality["populated_fields"] 
                     else "rapidapi" if rapidapi_quality["populated_fields"] > jina_quality["populated_fields"] 
                     else "tie",
            "critical": "jina" if jina_quality["critical_fields"] > rapidapi_quality["critical_fields"] 
                       else "rapidapi" if rapidapi_quality["critical_fields"] > jina_quality["critical_fields"] 
                       else "tie",
            "speed": "jina" if jina_time < rapidapi_time and jina_time > 0 and rapidapi_time > 0
                    else "rapidapi" if rapidapi_time < jina_time and jina_time > 0 and rapidapi_time > 0
                    else "tie"
        },
        "score_difference": abs(jina_quality["overall_score"] - rapidapi_quality["overall_score"]),
        "significant_difference": abs(jina_quality["overall_score"] - rapidapi_quality["overall_score"]) > 10
    }
    
    return comparison