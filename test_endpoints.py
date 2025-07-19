#!/usr/bin/env python3
"""
Comprehensive endpoint testing script for BrainOps backend
"""

import requests
import json
import sys
from datetime import datetime

# Test configuration
TEST_CONFIGS = [
    {
        "name": "Render Direct",
        "base_url": "https://brainops-backend.onrender.com",
        "headers": {"Host": "api.brainstackstudio.com"}
    },
    {
        "name": "API Domain",
        "base_url": "https://api.brainstackstudio.com",
        "headers": {}
    },
    {
        "name": "BrainStack Domain",
        "base_url": "https://brainstackstudio.com",
        "headers": {}
    },
    {
        "name": "Local Docker",
        "base_url": "http://localhost:8001",
        "headers": {"Host": "api.brainstackstudio.com"}
    }
]

# Endpoints to test
ENDPOINTS = [
    {"path": "/", "method": "GET", "auth": False},
    {"path": "/health", "method": "GET", "auth": False},
    {"path": "/health/detailed", "method": "GET", "auth": False},
    {"path": "/api/v1/health", "method": "GET", "auth": False},
    {"path": "/docs", "method": "GET", "auth": False},
    {"path": "/openapi.json", "method": "GET", "auth": False},
    {"path": "/auth/register", "method": "POST", "auth": False, "data": {
        "email": "test@example.com",
        "username": "testuser",
        "password": "Test123!"
    }},
    {"path": "/auth/login", "method": "POST", "auth": False, "data": {
        "username": "test@example.com",
        "password": "Test123!"
    }},
    {"path": "/erp/jobs", "method": "GET", "auth": True},
    {"path": "/erp/estimates", "method": "GET", "auth": True},
    {"path": "/crm/customers", "method": "GET", "auth": True},
    {"path": "/marketplace/templates", "method": "GET", "auth": False}
]

def test_endpoint(base_url, endpoint, headers, token=None):
    """Test a single endpoint"""
    url = base_url + endpoint["path"]
    headers = headers.copy()
    
    if endpoint.get("auth") and token:
        headers["Authorization"] = f"Bearer {token}"
    
    try:
        if endpoint["method"] == "GET":
            response = requests.get(url, headers=headers, timeout=5, verify=False)
        else:
            headers["Content-Type"] = "application/json"
            response = requests.post(
                url, 
                headers=headers, 
                json=endpoint.get("data", {}),
                timeout=5,
                verify=False
            )
        
        return {
            "status": response.status_code,
            "success": 200 <= response.status_code < 300,
            "response": response.text[:200] if response.text else None,
            "headers": dict(response.headers)
        }
    except requests.exceptions.ConnectionError:
        return {"status": "CONNECTION_ERROR", "success": False}
    except requests.exceptions.Timeout:
        return {"status": "TIMEOUT", "success": False}
    except Exception as e:
        return {"status": f"ERROR: {str(e)}", "success": False}

def main():
    print(f"\n{'='*80}")
    print(f"BrainOps Backend Endpoint Testing - {datetime.now()}")
    print(f"{'='*80}\n")
    
    results = {}
    
    for config in TEST_CONFIGS:
        print(f"\n[{config['name']}] Testing {config['base_url']}...")
        print("-" * 60)
        
        results[config['name']] = {}
        token = None
        
        for endpoint in ENDPOINTS:
            result = test_endpoint(
                config['base_url'], 
                endpoint, 
                config['headers'],
                token
            )
            
            status_symbol = "✅" if result["success"] else "❌"
            print(f"{status_symbol} {endpoint['method']:6} {endpoint['path']:30} -> {result['status']}")
            
            results[config['name']][endpoint['path']] = result
            
            # Extract token from login response
            if endpoint["path"] == "/auth/login" and result["success"]:
                try:
                    data = json.loads(result["response"])
                    token = data.get("access_token")
                except:
                    pass
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    
    for config_name, endpoints in results.items():
        total = len(endpoints)
        success = sum(1 for r in endpoints.values() if r["success"])
        print(f"\n{config_name}:")
        print(f"  Total endpoints: {total}")
        print(f"  Successful: {success}")
        print(f"  Failed: {total - success}")
        print(f"  Success rate: {(success/total)*100:.1f}%")
    
    # Write detailed results
    with open("endpoint_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nDetailed results saved to endpoint_test_results.json")

if __name__ == "__main__":
    main()