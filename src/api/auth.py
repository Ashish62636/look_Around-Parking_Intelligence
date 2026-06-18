"""
src/api/auth.py
===============
API Key authentication middleware for the FastAPI service.
Looks for 'X-API-Key' header, validating against environment variables or a default.
"""

import os
from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def get_api_key() -> str:
    """Retrieve the expected API key from environment, defaulting if not set."""
    return os.getenv("PARKING_API_KEY", "parking_intel_key_2026")

async def verify_api_key(api_key_header_value: str = Security(api_key_header)) -> str:
    """Validate the incoming API key header against the expected value."""
    expected_key = get_api_key()
    
    if not api_key_header_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key in header (X-API-Key)",
        )
        
    if api_key_header_value != expected_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key",
        )
        
    return api_key_header_value
