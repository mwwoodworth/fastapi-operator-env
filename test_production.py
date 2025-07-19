#!/usr/bin/env python3
"""Production Integration Test Suite"""

import requests
import json
from datetime import datetime
import sys

BASE_URL = "https://brainops-backend-prod.onrender.com"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def test_endpoint(name, method, path, data=None, headers=None):
    """Test a single endpoint"""
    url = f"{BASE_URL}{path}"
    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, json=data, headers=headers)
        elif method == "PUT":
            response = requests.put(url, json=data, headers=headers)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers)
        
        status = "PASS" if response.status_code < 400 else "FAIL"
        color = Colors.GREEN if status == "PASS" else Colors.RED
        
        print(f"{color}[{status}]{Colors.END} {name}")
        print(f"    URL: {url}")
        print(f"    Status: {response.status_code}")
        
        if response.status_code >= 400:
            try:
                print(f"    Response: {response.json()}")
            except:
                print(f"    Response: {response.text[:200]}")
        
        return status == "PASS", response
        
    except Exception as e:
        print(f"{Colors.RED}[FAIL]{Colors.END} {name}")
        print(f"    URL: {url}")
        print(f"    Error: {str(e)}")
        return False, None

def main():
    print(f"\n{Colors.BLUE}=== BrainOps Production Integration Tests ==={Colors.END}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Target: {BASE_URL}\n")
    
    results = []
    
    # Test health endpoints
    print(f"{Colors.YELLOW}## Health Endpoints{Colors.END}")
    results.append(test_endpoint("Health Check", "GET", "/health"))
    results.append(test_endpoint("Root Endpoint", "GET", "/"))
    
    # Test API documentation
    print(f"\n{Colors.YELLOW}## API Documentation{Colors.END}")
    results.append(test_endpoint("OpenAPI Spec", "GET", "/openapi.json"))
    results.append(test_endpoint("Swagger Docs", "GET", "/docs"))
    results.append(test_endpoint("ReDoc", "GET", "/redoc"))
    
    # Test auth endpoints
    print(f"\n{Colors.YELLOW}## Authentication{Colors.END}")
    results.append(test_endpoint("Login", "POST", "/api/v1/auth/login", {
        "email": "test@example.com",
        "password": "test123"
    }))
    results.append(test_endpoint("Register", "POST", "/api/v1/auth/register", {
        "email": "newtest@example.com",
        "password": "test123",
        "full_name": "Test User"
    }))
    
    # Test main API endpoints
    print(f"\n{Colors.YELLOW}## Core API Endpoints{Colors.END}")
    results.append(test_endpoint("Users List", "GET", "/api/v1/users"))
    results.append(test_endpoint("ERP Jobs", "GET", "/api/v1/erp/jobs"))
    results.append(test_endpoint("CRM Leads", "GET", "/api/v1/crm/leads"))
    results.append(test_endpoint("Tasks", "GET", "/api/v1/tasks"))
    
    # Summary
    passed = sum(1 for success, _ in results if success)
    total = len(results)
    
    print(f"\n{Colors.BLUE}=== Test Summary ==={Colors.END}")
    print(f"Total Tests: {total}")
    print(f"{Colors.GREEN}Passed: {passed}{Colors.END}")
    print(f"{Colors.RED}Failed: {total - passed}{Colors.END}")
    
    if passed == total:
        print(f"\n{Colors.GREEN}✅ ALL TESTS PASSED!{Colors.END}")
        return 0
    else:
        print(f"\n{Colors.RED}❌ SOME TESTS FAILED{Colors.END}")
        return 1

if __name__ == "__main__":
    sys.exit(main())