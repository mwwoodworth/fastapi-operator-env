#!/usr/bin/env python3
"""
Comprehensive endpoint testing for BrainOps backend.
Tests all public and protected endpoints.
"""

import requests
import json
from typing import Dict, Any, List

class EndpointTester:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.results = []
        self.token = None
    
    def test_endpoint(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Test a single endpoint."""
        url = f"{self.base_url}{path}"
        headers = kwargs.pop('headers', {})
        
        if self.token and 'Authorization' not in headers:
            headers['Authorization'] = f"Bearer {self.token}"
        
        try:
            response = self.session.request(method, url, headers=headers, **kwargs)
            result = {
                'method': method,
                'path': path,
                'status': response.status_code,
                'success': 200 <= response.status_code < 300,
                'data': response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
            }
        except Exception as e:
            result = {
                'method': method,
                'path': path,
                'status': 0,
                'success': False,
                'error': str(e)
            }
        
        self.results.append(result)
        return result
    
    def run_all_tests(self):
        """Run comprehensive endpoint tests."""
        print("🚀 Starting BrainOps Backend Endpoint Testing")
        print("=" * 60)
        
        # Public endpoints
        print("\n📋 Testing Public Endpoints:")
        self.test_endpoint('GET', '/health')
        self.test_endpoint('GET', '/api/v1/health')
        self.test_endpoint('GET', '/api/docs')
        self.test_endpoint('GET', '/api/openapi.json')
        
        # Auth endpoints
        print("\n🔐 Testing Auth Endpoints:")
        auth_result = self.test_endpoint('POST', '/api/v1/auth/register', json={
            'email': 'test@brainops.com',
            'password': 'TestPassword123!',
            'name': 'Test User'
        })
        
        login_result = self.test_endpoint('POST', '/api/v1/auth/login', json={
            'email': 'test@brainops.com',
            'password': 'TestPassword123!'
        })
        
        if login_result.get('success') and 'data' in login_result:
            self.token = login_result['data'].get('access_token')
        
        # Protected endpoints
        print("\n🔒 Testing Protected Endpoints:")
        self.test_endpoint('GET', '/api/v1/users/me')
        self.test_endpoint('GET', '/api/v1/users')
        self.test_endpoint('GET', '/api/v1/projects')
        self.test_endpoint('GET', '/api/v1/tasks')
        
        # AI endpoints
        print("\n🤖 Testing AI Service Endpoints:")
        self.test_endpoint('GET', '/api/v1/ai/models')
        self.test_endpoint('POST', '/api/v1/ai/completions', json={
            'prompt': 'Test prompt',
            'model': 'gpt-3.5-turbo'
        })
        
        # Webhook endpoints
        print("\n🪝 Testing Webhook Endpoints:")
        self.test_endpoint('GET', '/api/v1/webhooks')
        self.test_endpoint('GET', '/api/v1/webhooks/health')
        
        # Memory/vector endpoints
        print("\n🧠 Testing Memory Endpoints:")
        self.test_endpoint('GET', '/api/v1/memory/collections')
        self.test_endpoint('POST', '/api/v1/memory/search', json={
            'query': 'test search',
            'limit': 10
        })
        
        # Generate report
        self.generate_report()
    
    def generate_report(self):
        """Generate test report."""
        print("\n" + "=" * 60)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 60)
        
        total = len(self.results)
        successful = sum(1 for r in self.results if r['success'])
        failed = total - successful
        
        print(f"\nTotal Endpoints Tested: {total}")
        print(f"✅ Successful: {successful}")
        print(f"❌ Failed: {failed}")
        print(f"Success Rate: {(successful/total)*100:.1f}%")
        
        if failed > 0:
            print("\n⚠️  Failed Endpoints:")
            for result in self.results:
                if not result['success']:
                    print(f"  - {result['method']} {result['path']} (Status: {result['status']})")
                    if 'error' in result:
                        print(f"    Error: {result['error']}")
        
        # Save detailed results
        with open('endpoint_test_results.json', 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print("\n💾 Detailed results saved to: endpoint_test_results.json")

if __name__ == "__main__":
    import sys
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001"
    
    tester = EndpointTester(base_url)
    tester.run_all_tests()