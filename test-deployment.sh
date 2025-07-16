#!/bin/bash
set -e

# Configuration
API_URL="${1:-http://localhost:8000}"
echo "Testing deployment at: $API_URL"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Function to test endpoint
test_endpoint() {
    local endpoint=$1
    local expected_status=$2
    local description=$3
    
    echo -n "Testing $description... "
    
    response=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL$endpoint")
    
    if [ "$response" -eq "$expected_status" ]; then
        echo -e "${GREEN}✓ PASSED${NC} (Status: $response)"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗ FAILED${NC} (Expected: $expected_status, Got: $response)"
        ((TESTS_FAILED++))
    fi
}

# Function to test API with data
test_api_post() {
    local endpoint=$1
    local data=$2
    local expected_status=$3
    local description=$4
    
    echo -n "Testing $description... "
    
    response=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
        -H "Content-Type: application/json" \
        -d "$data" \
        "$API_URL$endpoint")
    
    if [ "$response" -eq "$expected_status" ]; then
        echo -e "${GREEN}✓ PASSED${NC} (Status: $response)"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗ FAILED${NC} (Expected: $expected_status, Got: $response)"
        ((TESTS_FAILED++))
    fi
}

echo "=== Starting API Tests ==="
echo

# Health checks
echo "--- Health Checks ---"
test_endpoint "/healthz" 200 "Health endpoint"
test_endpoint "/docs" 200 "API documentation"
test_endpoint "/redoc" 200 "ReDoc documentation"
test_endpoint "/openapi.json" 200 "OpenAPI schema"

# API endpoints
echo -e "\n--- API Endpoints ---"
test_endpoint "/api/v1/status" 200 "API status"

# AI endpoints (may require auth)
echo -e "\n--- AI Integration Tests ---"
test_api_post "/api/v1/ai/chat" '{"message":"Hello"}' 401 "AI chat (expect 401 without auth)"
test_api_post "/api/v1/ai/complete" '{"prompt":"Test"}' 401 "AI completion (expect 401 without auth)"

# Integration endpoints
echo -e "\n--- Integration Tests ---"
test_endpoint "/api/v1/integrations/clickup/status" 401 "ClickUp status (expect 401)"
test_endpoint "/api/v1/integrations/notion/status" 401 "Notion status (expect 401)"
test_endpoint "/api/v1/integrations/stripe/status" 401 "Stripe status (expect 401)"

# Database connectivity
echo -e "\n--- Database Tests ---"
test_endpoint "/api/v1/db/status" 200 "Database connectivity"

# Redis connectivity
echo -e "\n--- Cache Tests ---"
test_endpoint "/api/v1/cache/status" 200 "Redis connectivity"

# Performance test
echo -e "\n--- Performance Tests ---"
echo -n "Testing response time... "
start_time=$(date +%s.%N)
curl -s "$API_URL/healthz" > /dev/null
end_time=$(date +%s.%N)
response_time=$(echo "$end_time - $start_time" | bc)

if (( $(echo "$response_time < 1.0" | bc -l) )); then
    echo -e "${GREEN}✓ PASSED${NC} (Response time: ${response_time}s)"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}⚠ WARNING${NC} (Response time: ${response_time}s - consider optimization)"
fi

# Load test (simple)
echo -e "\n--- Load Tests ---"
echo -n "Testing concurrent requests (10 requests)... "
errors=0
for i in {1..10}; do
    curl -s -o /dev/null "$API_URL/healthz" || ((errors++)) &
done
wait

if [ $errors -eq 0 ]; then
    echo -e "${GREEN}✓ PASSED${NC} (All requests successful)"
    ((TESTS_PASSED++))
else
    echo -e "${RED}✗ FAILED${NC} ($errors requests failed)"
    ((TESTS_FAILED++))
fi

# Security headers test
echo -e "\n--- Security Tests ---"
echo -n "Testing security headers... "
headers=$(curl -s -I "$API_URL/healthz")

security_headers=("X-Content-Type-Options" "X-Frame-Options" "X-XSS-Protection")
missing_headers=()

for header in "${security_headers[@]}"; do
    if ! echo "$headers" | grep -qi "$header"; then
        missing_headers+=("$header")
    fi
done

if [ ${#missing_headers[@]} -eq 0 ]; then
    echo -e "${GREEN}✓ PASSED${NC} (All security headers present)"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}⚠ WARNING${NC} (Missing headers: ${missing_headers[*]})"
fi

# SSL/TLS test (only for HTTPS URLs)
if [[ $API_URL == https://* ]]; then
    echo -e "\n--- SSL/TLS Tests ---"
    echo -n "Testing SSL certificate... "
    
    if curl -s --fail "$API_URL/healthz" > /dev/null; then
        echo -e "${GREEN}✓ PASSED${NC} (Valid SSL certificate)"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗ FAILED${NC} (SSL certificate issue)"
        ((TESTS_FAILED++))
    fi
fi

# Summary
echo -e "\n=== Test Summary ==="
echo -e "Total tests: $((TESTS_PASSED + TESTS_FAILED))"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "\n${GREEN}All tests passed! Deployment is healthy.${NC}"
    exit 0
else
    echo -e "\n${RED}Some tests failed. Please check the deployment.${NC}"
    exit 1
fi