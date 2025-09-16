import time
import logging
import sys
import os
import psutil
import re
from typing import Optional, Dict, Any, Callable
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

def setup_cloudwatch_logging():
    """CloudWatch-compatible logging setup for Lambda environment"""
    # Configure root logger for CloudWatch
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        stream=sys.stdout
    )
    
    # Return logger instance
    return logging.getLogger('lambda_new_company_processor')


def get_logger(name: str):
    """Get a logger instance optimized for CloudWatch compatibility"""
    logger = logging.getLogger(name)
    if not logger.handlers:  # Avoid duplicate handlers
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger




def validate_url(url: str) -> bool:
    """Validate URL format and LinkedIn domain patterns"""
    if not url or not isinstance(url, str):
        return False
    
    url = url.strip().lower()
    
    # Basic URL validation
    if not url.startswith(('http://', 'https://')):
        return False
    
    # LinkedIn domain validation
    linkedin_patterns = [
        'linkedin.com/company/',
        'linkedin.com/school/',
        'www.linkedin.com/company/',
        'www.linkedin.com/school/'
    ]
    
    return any(pattern in url for pattern in linkedin_patterns)


def clean_url(url: str) -> Optional[str]:
    """Clean and normalize LinkedIn URLs"""
    if not url:
        return None
    
    url = url.strip()
    
    # Ensure https
    if url.startswith('http://'):
        url = url.replace('http://', 'https://')
    elif not url.startswith('https://'):
        url = f'https://{url}'
    
    # Remove tracking parameters
    if '?' in url:
        url = url.split('?')[0]
    
    # Remove trailing slash
    if url.endswith('/'):
        url = url[:-1]
    
    return url


def get_lambda_memory_info() -> Dict[str, Any]:
    """Get Lambda memory usage information for monitoring and debugging"""
    try:
        # Get process memory info
        process = psutil.Process()
        memory_info = process.memory_info()
        
        # Get Lambda memory limit from environment
        lambda_memory_limit = int(os.environ.get('AWS_LAMBDA_FUNCTION_MEMORY_SIZE', '512'))
        
        # Convert to MB
        memory_used_mb = memory_info.rss / (1024 * 1024)
        memory_percent = (memory_used_mb / lambda_memory_limit) * 100
        
        return {
            "memory_used_mb": round(memory_used_mb, 2),
            "memory_limit_mb": lambda_memory_limit,
            "memory_percent": round(memory_percent, 2),
            "memory_available_mb": round(lambda_memory_limit - memory_used_mb, 2)
        }
    except Exception as e:
        print(f"Error getting memory info: {e}")
        return {}


def get_lambda_timeout_info(context=None) -> Dict[str, Any]:
    """Get Lambda timeout information for proactive timeout handling"""
    try:
        if context and hasattr(context, 'get_remaining_time_in_millis'):
            remaining_time_ms = context.get_remaining_time_in_millis()
            remaining_time_seconds = remaining_time_ms / 1000
            
            return {
                "remaining_time_ms": remaining_time_ms,
                "remaining_time_seconds": round(remaining_time_seconds, 2),
                "timeout_warning": remaining_time_seconds < 30  # Warn if less than 30 seconds left
            }
        else:
            # Fallback to environment variable
            timeout_seconds = int(os.environ.get('AWS_LAMBDA_FUNCTION_TIMEOUT', '900'))
            return {
                "configured_timeout_seconds": timeout_seconds,
                "remaining_time_seconds": "unknown",
                "timeout_warning": False
            }
    except Exception as e:
        print(f"Error getting timeout info: {e}")
        return {}


def monitor_performance(func: Callable):
    """
    Decorator to monitor function performance including timing and memory usage.
    Useful for identifying performance bottlenecks in Lambda processing.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        start_memory = get_lambda_memory_info()
        
        print(f"Starting {func.__name__} - Memory: {start_memory.get('memory_used_mb', 'unknown')}MB")
        
        try:
            result = func(*args, **kwargs)
            
            end_time = time.time()
            end_memory = get_lambda_memory_info()
            duration = end_time - start_time
            
            memory_delta = 0
            if start_memory and end_memory:
                memory_delta = end_memory.get('memory_used_mb', 0) - start_memory.get('memory_used_mb', 0)
            
            print(f"Completed {func.__name__} - Duration: {duration:.2f}s, Memory delta: {memory_delta:.2f}MB")
            
            return result
            
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            print(f"Failed {func.__name__} - Duration: {duration:.2f}s, Error: {str(e)}")
            raise
    
    return wrapper




def safe_sleep(seconds: float):
    """Safe sleep function that respects Lambda timeout constraints"""
    if seconds <= 0:
        return
    
    # Check if we have enough time left to sleep
    timeout_info = get_lambda_timeout_info()
    remaining_seconds = timeout_info.get("remaining_time_seconds", float('inf'))
    
    if isinstance(remaining_seconds, (int, float)):
        if remaining_seconds < seconds + 10:  # Keep 10 second buffer
            print(f"Skipping sleep({seconds}s) due to Lambda timeout constraint (remaining: {remaining_seconds}s)")
            return
    
    time.sleep(seconds)


def format_processing_summary(stats: Dict[str, Any]) -> str:
    """Format processing statistics into a readable summary"""
    summary_lines = [
        f"Processing Summary:",
        f"  Total attempted: {stats.get('total_attempted', 0)}",
        f"  Successfully processed: {stats.get('processed_count', 0)}",
        f"  Failed: {stats.get('failed_count', 0)}",
        f"  Success rate: {stats.get('success_rate', 0):.1f}%"
    ]
    
    if stats.get('duration_seconds'):
        summary_lines.append(f"  Duration: {stats['duration_seconds']:.2f}s")
    
    if stats.get('throughput_per_second'):
        summary_lines.append(f"  Throughput: {stats['throughput_per_second']:.2f} items/second")
    
    return "\n".join(summary_lines)
