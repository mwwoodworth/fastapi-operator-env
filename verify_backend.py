#!/usr/bin/env python3
"""Verify BrainOps backend is running correctly."""

import requests
import time
import sys

def check_backend(base_url):
    """Check if backend is responding correctly."""
    endpoints = [
        "/health",
        "/api/v1/health",
        "/docs"
    ]
    
    print(f"🔍 Checking backend at: {base_url}")
    print("-" * 50)
    
    all_ok = True
    
    for endpoint in endpoints:
        url = f"{base_url}{endpoint}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                print(f"✅ {endpoint}: OK (200)")
            else:
                print(f"❌ {endpoint}: Failed ({response.status_code})")
                all_ok = False
        except Exception as e:
            print(f"❌ {endpoint}: Error - {str(e)}")
            all_ok = False
    
    print("-" * 50)
    
    if all_ok:
        print("✅ All endpoints are responding correctly!")
        return 0
    else:
        print("❌ Some endpoints failed. Check logs.")
        return 1

if __name__ == "__main__":
    # Default to localhost, can be overridden with command line arg
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    
    # Remove trailing slash if present
    base_url = base_url.rstrip("/")
    
    exit_code = check_backend(base_url)
    sys.exit(exit_code)