#!/usr/bin/env python3
"""
Production Smoke Tests for BrainOps API
Run after deployment to verify all endpoints are functional
"""

import sys
import json
import time
from typing import Dict, List, Tuple
import requests
from datetime import datetime
import os
from urllib.parse import urljoin


class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'


class SmokeTestRunner:
    def __init__(self, base_url: str, api_key: str = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        self.results = []
        self.auth_token = None
        
    def log(self, message: str, color: str = ""):
        """Print colored log message."""
        print(f"{color}{message}{Colors.END}")
        
    def test_endpoint(self, method: str, path: str, expected_status: int, 
                     data: Dict = None, headers: Dict = None, name: str = None) -> bool:
        """Test a single endpoint."""
        url = urljoin(self.base_url, path)
        test_name = name or f"{method} {path}"
        
        try:
            # Add auth header if available
            if self.auth_token and headers is None:
                headers = {"Authorization": f"Bearer {self.auth_token}"}
            elif self.auth_token and headers:
                headers["Authorization"] = f"Bearer {self.auth_token}"
                
            # Make request
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                headers=headers,
                timeout=10
            )
            
            # Check status
            success = response.status_code == expected_status
            
            # Log result
            if success:
                self.log(f"✅ {test_name} - {response.status_code}", Colors.GREEN)
            else:
                self.log(f"❌ {test_name} - Expected {expected_status}, got {response.status_code}", Colors.RED)
                if response.text:
                    self.log(f"   Response: {response.text[:200]}", Colors.YELLOW)
                    
            self.results.append((test_name, success, response.status_code))
            return success
            
        except Exception as e:
            self.log(f"❌ {test_name} - Error: {str(e)}", Colors.RED)
            self.results.append((test_name, False, str(e)))
            return False
    
    def run_health_checks(self):
        """Test health check endpoints."""
        self.log("\n🏥 Health Check Tests", Colors.BLUE)
        
        # Basic health
        self.test_endpoint("GET", "/health", 200, name="Basic Health Check")
        
        # API health
        self.test_endpoint("GET", "/api/v1/health", 200, name="API Health Check")
        
        # Detailed health
        self.test_endpoint("GET", "/api/v1/health/detailed", 200, name="Detailed Health Check")
        
    def run_auth_tests(self):
        """Test authentication endpoints."""
        self.log("\n🔐 Authentication Tests", Colors.BLUE)
        
        # Register test user
        test_user = {
            "email": f"smoketest_{int(time.time())}@example.com",
            "password": "TestPassword123!",
            "full_name": "Smoke Test User"
        }
        
        # Register
        response = self.session.post(
            urljoin(self.base_url, "/api/v1/auth/register"),
            json=test_user
        )
        
        if response.status_code == 200:
            self.log("✅ User Registration", Colors.GREEN)
            self.results.append(("User Registration", True, 200))
        else:
            self.log(f"❌ User Registration - {response.status_code}", Colors.RED)
            self.results.append(("User Registration", False, response.status_code))
            return
            
        # Login
        login_data = {
            "email": test_user["email"],
            "password": test_user["password"]
        }
        
        response = self.session.post(
            urljoin(self.base_url, "/api/v1/auth/login"),
            json=login_data
        )
        
        if response.status_code == 200:
            self.log("✅ User Login", Colors.GREEN)
            self.results.append(("User Login", True, 200))
            self.auth_token = response.json().get("access_token")
        else:
            self.log(f"❌ User Login - {response.status_code}", Colors.RED)
            self.results.append(("User Login", False, response.status_code))
            
        # Test authenticated endpoint
        if self.auth_token:
            self.test_endpoint("GET", "/api/v1/users/me", 200, name="Get Current User")
            
    def run_core_endpoint_tests(self):
        """Test core API endpoints."""
        self.log("\n🚀 Core Endpoint Tests", Colors.BLUE)
        
        # Projects
        self.test_endpoint("GET", "/api/v1/projects", 200, name="List Projects")
        
        # Tasks
        self.test_endpoint("GET", "/api/v1/tasks", 200, name="List Tasks")
        
        # Users
        self.test_endpoint("GET", "/api/v1/users", 200, name="List Users")
        
    def run_erp_tests(self):
        """Test ERP endpoints."""
        self.log("\n🏭 ERP Module Tests", Colors.BLUE)
        
        # Estimating
        self.test_endpoint("GET", "/api/v1/erp/estimates", 200, name="List Estimates")
        
        # Job Management
        self.test_endpoint("GET", "/api/v1/erp/jobs", 200, name="List Jobs")
        
        # Field Capture
        self.test_endpoint("GET", "/api/v1/erp/field-reports", 200, name="List Field Reports")
        
        # Compliance
        self.test_endpoint("GET", "/api/v1/erp/compliance/permits", 200, name="List Permits")
        
        # Financial
        self.test_endpoint("GET", "/api/v1/erp/invoices", 200, name="List Invoices")
        
    def run_crm_tests(self):
        """Test CRM endpoints."""
        self.log("\n💼 CRM Module Tests", Colors.BLUE)
        
        # Leads
        self.test_endpoint("GET", "/api/v1/crm/leads", 200, name="List Leads")
        
        # Opportunities
        self.test_endpoint("GET", "/api/v1/crm/opportunities", 200, name="List Opportunities")
        
        # Analytics
        self.test_endpoint("GET", "/api/v1/crm/analytics/pipeline", 200, name="Pipeline Analytics")
        
    def run_ai_tests(self):
        """Test AI/LangGraph endpoints."""
        self.log("\n🤖 AI/LangGraph Tests", Colors.BLUE)
        
        # LangGraph workflows
        self.test_endpoint("GET", "/api/v1/langgraph/workflows", 200, name="List LangGraph Workflows")
        
        # AI Chat (might need API key)
        if os.getenv("OPENAI_API_KEY"):
            chat_data = {"message": "Hello, this is a smoke test"}
            self.test_endpoint("POST", "/api/v1/ai/chat", 200, data=chat_data, name="AI Chat")
            
    def run_weathercraft_tests(self):
        """Test Weathercraft-specific endpoints."""
        self.log("\n🏠 Weathercraft Feature Tests", Colors.BLUE)
        
        # Material Calculator
        calc_data = {
            "sections": [{"length": 40, "width": 30, "pitch": "6/12"}],
            "shingle_type": "architectural"
        }
        self.test_endpoint("POST", "/api/v1/weathercraft/material-calculator", 200, 
                          data=calc_data, name="Material Calculator")
        
        # Smart Inventory
        self.test_endpoint("GET", "/api/v1/weathercraft/inventory/smart-reorder", 200, 
                          name="Smart Inventory Reorder")
        
    def run_integration_tests(self):
        """Test integration endpoints."""
        self.log("\n🔌 Integration Tests", Colors.BLUE)
        
        # List available integrations
        self.test_endpoint("GET", "/api/v1/automation/integrations/available", 200, 
                          name="Available Integrations")
        
        # Webhook health
        self.test_endpoint("GET", "/api/v1/webhooks/health", 200, name="Webhook Health")
        
    def run_performance_tests(self):
        """Run basic performance tests."""
        self.log("\n⚡ Performance Tests", Colors.BLUE)
        
        # Test response times
        endpoints = [
            ("/health", "Health Check"),
            ("/api/v1/health", "API Health"),
            ("/api/v1/projects", "List Projects"),
            ("/api/v1/tasks", "List Tasks")
        ]
        
        for endpoint, name in endpoints:
            start = time.time()
            response = self.session.get(
                urljoin(self.base_url, endpoint),
                headers={"Authorization": f"Bearer {self.auth_token}"} if self.auth_token else None
            )
            elapsed = (time.time() - start) * 1000  # ms
            
            if response.status_code == 200:
                if elapsed < 100:
                    self.log(f"✅ {name} - {elapsed:.0f}ms", Colors.GREEN)
                elif elapsed < 500:
                    self.log(f"⚠️  {name} - {elapsed:.0f}ms (slow)", Colors.YELLOW)
                else:
                    self.log(f"❌ {name} - {elapsed:.0f}ms (too slow)", Colors.RED)
            else:
                self.log(f"❌ {name} - Failed with {response.status_code}", Colors.RED)
                
    def generate_report(self):
        """Generate final test report."""
        self.log("\n📊 Smoke Test Report", Colors.BLUE)
        self.log("=" * 50)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for _, success, _ in self.results if success)
        failed_tests = total_tests - passed_tests
        
        self.log(f"Total Tests: {total_tests}")
        self.log(f"Passed: {passed_tests} ({passed_tests/total_tests*100:.1f}%)", Colors.GREEN)
        self.log(f"Failed: {failed_tests} ({failed_tests/total_tests*100:.1f}%)", 
                Colors.RED if failed_tests > 0 else Colors.GREEN)
        
        if failed_tests > 0:
            self.log("\nFailed Tests:", Colors.RED)
            for name, success, status in self.results:
                if not success:
                    self.log(f"  - {name}: {status}")
                    
        # Generate JSON report
        report = {
            "timestamp": datetime.now().isoformat(),
            "base_url": self.base_url,
            "summary": {
                "total": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "pass_rate": f"{passed_tests/total_tests*100:.1f}%"
            },
            "results": [
                {"test": name, "passed": success, "status": status}
                for name, success, status in self.results
            ]
        }
        
        with open("smoke_test_results.json", "w") as f:
            json.dump(report, f, indent=2)
            
        self.log(f"\nDetailed report saved to: smoke_test_results.json")
        
        return failed_tests == 0
    
    def run_all_tests(self):
        """Run all smoke tests."""
        self.log("🔥 Starting BrainOps Smoke Tests", Colors.BLUE)
        self.log(f"Target: {self.base_url}")
        self.log("=" * 50)
        
        # Run test suites
        self.run_health_checks()
        self.run_auth_tests()
        self.run_core_endpoint_tests()
        self.run_erp_tests()
        self.run_crm_tests()
        self.run_ai_tests()
        self.run_weathercraft_tests()
        self.run_integration_tests()
        self.run_performance_tests()
        
        # Generate report
        all_passed = self.generate_report()
        
        if all_passed:
            self.log("\n✅ All smoke tests passed! System is operational.", Colors.GREEN)
        else:
            self.log("\n❌ Some tests failed. Check the report for details.", Colors.RED)
            
        return all_passed


def main():
    """Run smoke tests."""
    # Get base URL from environment or command line
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = os.getenv("PRODUCTION_URL", "http://localhost:8000")
        
    # Get API key if needed
    api_key = os.getenv("API_KEY")
    
    # Run tests
    runner = SmokeTestRunner(base_url, api_key)
    success = runner.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()