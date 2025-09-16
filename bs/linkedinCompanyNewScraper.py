# bs/linkedinCompanyNewScraper.py
# Contains the logic to parse LinkedIn company page HTML
# Lambda-compatible version - no file system dependencies

import re
import html
import logging
from urllib.parse import urlparse, parse_qs
from typing import Dict, Any

logger = logging.getLogger(__name__)


def html_to_object(html_content: str) -> Dict[str, Any]:
    """
    Extracts company information from LinkedIn company page HTML using regex.
    Lambda-compatible version with enhanced error handling and logging.

    Args:
        html_content: A string containing the HTML source code of the LinkedIn company page.

    Returns:
        A dictionary containing the extracted company data. Returns empty strings
        for fields not found. Compatible with Lambda environment.
    """
    if not html_content or not isinstance(html_content, str):
        logger.warning("html_to_object received empty or invalid HTML content")
        return {}
    
    data = {
        "type": "",
        "name": "",
        "about": "",
        "company_size": "",
        "followers": "",
        "headquarters": "",
        "industry": "",
        "specialties": "",
        "website": "",
        "headline": ""  # Added for compatibility
    }

    try:
        # --- Extraction using Regex ---

        # name (h1 title)
        match = re.search(r'<h1\s+class="top-card-layout__title.*?>(.*?)</h1>', html_content, re.DOTALL)
        if match:
            data['name'] = html.unescape(match.group(1).strip())
            logger.info(f"Extracted company name: {data['name']}")

        # headquarters and followers (h3 under headline)
        hq_match = re.search(r'<div[^>]*data-test-id="about-us__headquarters"[^>]*>.*?<dd[^>]*>(.*?)</dd>', html_content, re.DOTALL)
        if hq_match:
             data['headquarters'] = html.unescape(hq_match.group(1).strip())
             logger.info(f"Extracted headquarters: {data['headquarters']}")

        # Followers - look for a specific pattern if not found in h3 combo
        # This pattern might need adjustment based on more examples
        followers_match = re.search(r'<h3\s+class="top-card-layout__first-subline.*?<span.*?</span>\s*([^<]+?)\s*followers', html_content, re.IGNORECASE | re.DOTALL)
        if followers_match:
            followers_text = html.unescape(followers_match.group(1).strip())
            data['followers'] = followers_text.replace(',', '').strip() # Remove commas
            logger.info(f"Extracted followers: {data['followers']}")
        else: # Fallback to potentially combined h3 structure if specific pattern fails
             match_hq_follow = re.search(r'<h3\s+class="top-card-layout__first-subline.*?>(.*?)<span.*?</span>(.*?)</h3>', html_content, re.DOTALL)
             if match_hq_follow:
                 # If HQ wasn't found separately, try here
                 if not data['headquarters']:
                      data['headquarters'] = html.unescape(match_hq_follow.group(1).strip())
                 followers_text = html.unescape(match_hq_follow.group(2).strip())
                 # Extract only the number part
                 follower_num_match = re.search(r'([\d,]+)\s+followers', followers_text, re.IGNORECASE)
                 if follower_num_match:
                     data['followers'] = follower_num_match.group(1).replace(',', '').strip()
                     logger.info(f"Extracted followers (fallback): {data['followers']}")

        # About Section Details
        about_section_match = re.search(r'<section[^>]*data-test-id="about-us".*?>(.*?)</section>', html_content, re.DOTALL)
        if about_section_match:
            about_section_html = about_section_match.group(1)

            # about
            match = re.search(r'<p[^>]*data-test-id="about-us__description"[^>]*>(.*?)</p>', about_section_html, re.DOTALL)
            if match:
                raw_about = html.unescape(match.group(1).strip())
                # Clean common trailing phrases/links
                raw_about = re.sub(r'\n*Check out our career opportunities.*', '', raw_about, flags=re.DOTALL | re.IGNORECASE).strip()
                raw_about = re.sub(r'\n\*\*\* Imprint / Impressum:.*', '', raw_about, flags=re.DOTALL | re.IGNORECASE).strip()
                cleaned_about = raw_about.replace('\n', ' ').strip() # Replace newlines with spaces
                data['about'] = ' '.join(cleaned_about.split()) # Consolidate whitespace
                logger.info(f"Extracted about (first 100 chars): {data['about'][:100]}...")

            # website
            website_url = "" # Use a temporary variable
            match = re.search(r'<div[^>]*data-test-id="about-us__website"[^>]*>.*?<a[^>]*href="(.*?)"[^>]*>.*?</a>', about_section_html, re.DOTALL)
            if match:
                 website_url = html.unescape(match.group(1).strip())
            else: # Fallback if href is not directly in the link text
                 match = re.search(r'<div[^>]*data-test-id="about-us__website"[^>]*>.*?<a[^>]*>(.*?)<[/]?icon', about_section_html, re.DOTALL)
                 if match:
                     # Check if the text itself might be a URL, though less common
                     potential_url = html.unescape(match.group(1).strip())
                     if potential_url.startswith("http://") or potential_url.startswith("https://"):
                         website_url = potential_url # Assume it's the URL if it looks like one

            # Clean LinkedIn redirect URLs
            if website_url.startswith("https://www.linkedin.com/redir/redirect?"):
                try:
                    parsed_url = urlparse(website_url)
                    query_params = parse_qs(parsed_url.query)
                    if 'url' in query_params:
                        website_url = query_params['url'][0] # Get the first (and usually only) 'url' parameter
                except Exception as e:
                    logger.error(f"Error cleaning LinkedIn redirect URL: {e}")

            data['website'] = website_url # Assign the final cleaned URL
            if data['website']:
                logger.info(f"Extracted website: {data['website']}")

            # industry
            match = re.search(r'<div[^>]*data-test-id="about-us__industry"[^>]*>.*?<dd[^>]*>(.*?)</dd>', about_section_html, re.DOTALL)
            if match:
                 data['industry'] = html.unescape(match.group(1).strip())
                 logger.info(f"Extracted industry: {data['industry']}")

            # company_size
            match = re.search(r'<div[^>]*data-test-id="about-us__size"[^>]*>.*?<dd[^>]*>(.*?)</dd>', about_section_html, re.DOTALL)
            if match:
                 size_text = html.unescape(match.group(1).strip())
                 # Extract the core part, e.g., '10,001+' or '51-200'
                 size_core_match = re.search(r'([\d,]+(?:-\d{1,3}(?:,\d{3})*|\+)?)\s+employees', size_text, re.IGNORECASE)
                 if size_core_match:
                     data['company_size'] = size_core_match.group(1).strip() + " employees" # Standardize format
                 else: # Fallback if 'employees' text is not present but number is
                      num_match = re.search(r'^[\d,-]+\+?', size_text)
                      if num_match:
                          data['company_size'] = num_match.group(0).strip() + " employees"
                      else:
                          data['company_size'] = size_text # Keep original if pattern fails
                 logger.info(f"Extracted company size: {data['company_size']}")

            # type (e.g., Public Company, Privately Held)
            match = re.search(r'<div[^>]*data-test-id="about-us__organizationType"[^>]*>.*?<dd[^>]*>(.*?)</dd>', about_section_html, re.DOTALL)
            if match:
                 data['type'] = html.unescape(match.group(1).strip())
                 logger.info(f"Extracted organization type: {data['type']}")

            # specialties
            match = re.search(r'<div[^>]*data-test-id="about-us__specialties"[^>]*>.*?<dd[^>]*>(.*?)</dd>', about_section_html, re.DOTALL)
            if match:
                 data['specialties'] = html.unescape(match.group(1).strip())
                 logger.info(f"Extracted specialties: {data['specialties']}")

        # Try to extract headline if available (some LinkedIn pages have this)
        headline_match = re.search(r'<h2\s+class="top-card-layout__headline.*?>(.*?)</h2>', html_content, re.DOTALL)
        if headline_match:
            data['headline'] = html.unescape(headline_match.group(1).strip())
            logger.info(f"Extracted headline: {data['headline']}")

    except Exception as e:
        logger.error(f"Error during HTML parsing: {e}")
        # Return partial data if parsing fails
        
    # --- Final Cleanup --- 
    # Ensure no None values, replace with empty strings
    for key, value in data.items():
        if value is None:
            data[key] = ""

    # Count populated fields for logging
    populated_count = len([v for v in data.values() if v and str(v).strip()])
    logger.info(f"HTML parsing complete. Populated {populated_count}/{len(data)} fields")

    return data