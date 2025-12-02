#!/bin/bash

# Test script for Advanced Analytics

API_URL="https://3sz03rlwzi.execute-api.us-east-1.amazonaws.com/prod"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Advanced Analytics Test Script ===${NC}\n"

# Step 1: Login to get token
echo -e "${YELLOW}Step 1: Logging in...${NC}"
read -p "Enter your email: " EMAIL
read -sp "Enter your password: " PASSWORD
echo

LOGIN_RESPONSE=$(curl -s -X POST "${API_URL}/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"${EMAIL}\", \"password\": \"${PASSWORD}\"}")

TOKEN=$(echo $LOGIN_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['access_token'])" 2>/dev/null)

if [ -z "$TOKEN" ]; then
  echo -e "${RED}Login failed!${NC}"
  echo "Response: $LOGIN_RESPONSE"
  exit 1
fi

echo -e "${GREEN}Login successful!${NC}\n"

# Step 2: Check existing snapshots
echo -e "${YELLOW}Step 2: Checking existing portfolio history snapshots...${NC}"
SNAPSHOTS_RESPONSE=$(curl -s -X GET "${API_URL}/portfolio/history/snapshots" \
  -H "Authorization: Bearer ${TOKEN}")

echo "Snapshots response:"
echo $SNAPSHOTS_RESPONSE | python3 -m json.tool
echo

# Step 3: Create snapshots
echo -e "${YELLOW}Step 3: Creating portfolio snapshots...${NC}"
echo "Creating snapshot 1..."
SNAPSHOT1=$(curl -s -X POST "${API_URL}/portfolio/history/snapshot" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"portfolio_type": "combined"}')

echo $SNAPSHOT1 | python3 -m json.tool
echo

# Wait 2 seconds
sleep 2

echo "Creating snapshot 2..."
SNAPSHOT2=$(curl -s -X POST "${API_URL}/portfolio/history/snapshot" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"portfolio_type": "combined"}')

echo $SNAPSHOT2 | python3 -m json.tool
echo

sleep 2

echo "Creating snapshot 3..."
SNAPSHOT3=$(curl -s -X POST "${API_URL}/portfolio/history/snapshot" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"portfolio_type": "combined"}')

echo $SNAPSHOT3 | python3 -m json.tool
echo

echo -e "${GREEN}Snapshots created!${NC}\n"

# Step 4: Test Analytics - Advanced Metrics
echo -e "${YELLOW}Step 4: Testing Advanced Metrics endpoint...${NC}"
METRICS_RESPONSE=$(curl -s -X GET "${API_URL}/analytics/metrics?period=365" \
  -H "Authorization: Bearer ${TOKEN}")

echo "Advanced Metrics Response:"
echo $METRICS_RESPONSE | python3 -m json.tool
echo

# Step 5: Test Analytics - Benchmark Comparison
echo -e "${YELLOW}Step 5: Testing Benchmark Comparison endpoint...${NC}"
BENCHMARK_RESPONSE=$(curl -s -X GET "${API_URL}/analytics/benchmarks?period=365&benchmarks=SP500,BTC" \
  -H "Authorization: Bearer ${TOKEN}")

echo "Benchmark Comparison Response:"
echo $BENCHMARK_RESPONSE | python3 -m json.tool
echo

# Step 6: Test Analytics - Risk Analysis
echo -e "${YELLOW}Step 6: Testing Risk Analysis endpoint...${NC}"
RISK_RESPONSE=$(curl -s -X GET "${API_URL}/analytics/risk" \
  -H "Authorization: Bearer ${TOKEN}")

echo "Risk Analysis Response:"
echo $RISK_RESPONSE | python3 -m json.tool
echo

echo -e "${GREEN}=== Test Complete! ===${NC}"
echo -e "Now go to your browser and check the Analytics tab > Advanced Metrics section"
