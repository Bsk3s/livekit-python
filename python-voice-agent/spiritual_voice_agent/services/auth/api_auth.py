"""
Simple API Key Authentication for sensitive endpoints
"""

import os
import hashlib
from fastapi import HTTPException, Header
from typing import Optional

def get_api_key() -> str:
    """Get API key from environment variable"""
    api_key = os.getenv("DASHBOARD_API_KEY")
    if not api_key:
        raise ValueError("DASHBOARD_API_KEY environment variable is required")
    return api_key

def verify_api_key(x_api_key: Optional[str] = Header(None)) -> bool:
    """Verify API key from request header"""
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing X-API-Key header"
        )
    
    try:
        expected_key = get_api_key()
        
        # Use secure comparison to prevent timing attacks
        if not _secure_compare(x_api_key, expected_key):
            raise HTTPException(
                status_code=403,
                detail="Invalid API key"
            )
        return True
    except ValueError:
        # API key not configured - allow access for development
        return True

def _secure_compare(a: str, b: str) -> bool:
    """Secure string comparison to prevent timing attacks"""
    if len(a) != len(b):
        return False
    
    result = 0
    for x, y in zip(a, b):
        result |= ord(x) ^ ord(y)
    return result == 0