#!/bin/bash

# Interactive setup script for Advanced Analytics
API_URL="https://3sz03rlwzi.execute-api.us-east-1.amazonaws.com/prod"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

clear
echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Advanced Metrics Setup & Test Script    ║${NC}"
echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo
echo -e "${YELLOW}This script will:${NC}"
echo "  1. Login to your account"
echo "  2. Create portfolio snapshots (needed for metrics)"
echo "  3. Test all advanced analytics endpoints"
echo "  4. Display your metrics"
echo
echo -e "${YELLOW}You need at least 2 snapshots for metrics to work.${NC}"
echo

# Get credentials
read -p "Enter your email: " EMAIL
read -sp "Enter your password: " PASSWORD
echo
echo

# Step 1: Login
echo -e "${YELLOW}[1/6] Logging in...${NC}"
LOGIN_RESPONSE=$(curl -s -X POST "${API_URL}/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"${EMAIL}\", \"password\": \"${PASSWORD}\"}")

TOKEN=$(echo $LOGIN_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['access_token'])" 2>/dev/null)

if [ -z "$TOKEN" ]; then
  echo -e "${RED}✗ Login failed!${NC}"
  echo "Response: $LOGIN_RESPONSE"
  exit 1
fi

echo -e "${GREEN}✓ Login successful!${NC}"
echo

# Step 2: Check portfolio
echo -e "${YELLOW}[2/6] Checking your portfolio...${NC}"
PORTFOLIO_RESPONSE=$(curl -s -X GET "${API_URL}/portfolio/summary" \
  -H "Authorization: Bearer ${TOKEN}")

TOTAL_VALUE=$(echo $PORTFOLIO_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('data', {}).get('total_value', 0))" 2>/dev/null)
CRYPTO_COUNT=$(echo $PORTFOLIO_RESPONSE | python3 -c "import sys, json; print(len(json.load(sys.stdin).get('data', {}).get('crypto_assets', [])))" 2>/dev/null)
STOCK_COUNT=$(echo $PORTFOLIO_RESPONSE | python3 -c "import sys, json; print(len(json.load(sys.stdin).get('data', {}).get('stock_assets', [])))" 2>/dev/null)

echo -e "${GREEN}✓ Portfolio loaded${NC}"
echo "  Total Value: \$${TOTAL_VALUE}"
echo "  Crypto Assets: ${CRYPTO_COUNT}"
echo "  Stock Assets: ${STOCK_COUNT}"
echo

# Step 3: Check existing snapshots
echo -e "${YELLOW}[3/6] Checking existing historical data...${NC}"
HISTORY_RESPONSE=$(curl -s -X GET "${API_URL}/portfolio/history?period=30D&portfolio_type=combined" \
  -H "Authorization: Bearer ${TOKEN}")

DATA_POINTS=$(echo $HISTORY_RESPONSE | python3 -c "import sys, json; print(len(json.load(sys.stdin).get('data', {}).get('data_points', [])))" 2>/dev/null)

if [ -z "$DATA_POINTS" ] || [ "$DATA_POINTS" = "None" ]; then
  DATA_POINTS=0
fi

echo -e "${GREEN}✓ Found ${DATA_POINTS} existing data points${NC}"

if [ "$DATA_POINTS" -ge 2 ]; then
  echo -e "${GREEN}  You already have enough data for metrics!${NC}"
else
  echo -e "${YELLOW}  Need to create snapshots (minimum 2 required)${NC}"
fi
echo

# Step 4: Create snapshots
SNAPSHOTS_NEEDED=$((2 - DATA_POINTS))
if [ $SNAPSHOTS_NEEDED -lt 0 ]; then
  SNAPSHOTS_NEEDED=0
fi

if [ $SNAPSHOTS_NEEDED -gt 0 ]; then
  echo -e "${YELLOW}[4/6] Creating ${SNAPSHOTS_NEEDED} snapshot(s)...${NC}"

  # Create a few extra to ensure we have varied data
  for i in $(seq 1 3); do
    echo -n "  Creating snapshot $i... "
    SNAPSHOT=$(curl -s -X POST "${API_URL}/portfolio/history/snapshot" \
      -H "Authorization: Bearer ${TOKEN}" \
      -H "Content-Type: application/json" \
      -d '{"portfolio_type": "combined"}')

    SUCCESS=$(echo $SNAPSHOT | python3 -c "import sys, json; print(json.load(sys.stdin).get('success', False))" 2>/dev/null)

    if [ "$SUCCESS" = "True" ]; then
      echo -e "${GREEN}✓${NC}"
    else
      echo -e "${RED}✗${NC}"
    fi

    sleep 1
  done
  echo
else
  echo -e "${YELLOW}[4/6] Skipping snapshot creation (already have enough data)${NC}"
  echo
fi

# Step 5: Test Advanced Metrics
echo -e "${YELLOW}[5/6] Fetching Advanced Metrics...${NC}"
METRICS_RESPONSE=$(curl -s -X GET "${API_URL}/analytics/metrics?period=365" \
  -H "Authorization: Bearer ${TOKEN}")

METRICS_STATUS=$(echo $METRICS_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('data', {}).get('status', 'unknown'))" 2>/dev/null)

if [ "$METRICS_STATUS" = "calculated" ]; then
  echo -e "${GREEN}✓ Metrics calculated successfully!${NC}"
  echo
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BLUE}           YOUR PORTFOLIO METRICS            ${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

  # Parse metrics
  SHARPE=$(echo $METRICS_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('data', {}).get('metrics', {}).get('sharpe_ratio', 'N/A'))" 2>/dev/null)
  VOLATILITY=$(echo $METRICS_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('data', {}).get('metrics', {}).get('annualized_volatility', 'N/A'))" 2>/dev/null)
  MAX_DD=$(echo $METRICS_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('data', {}).get('metrics', {}).get('max_drawdown', 'N/A'))" 2>/dev/null)
  TOTAL_RETURN=$(echo $METRICS_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('data', {}).get('metrics', {}).get('total_return', 'N/A'))" 2>/dev/null)
  WIN_RATE=$(echo $METRICS_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('data', {}).get('metrics', {}).get('win_rate', 'N/A'))" 2>/dev/null)

  echo "  Sharpe Ratio: $SHARPE (>1 is good)"
  echo "  Volatility: ${VOLATILITY}% (annual)"
  echo "  Max Drawdown: ${MAX_DD}%"
  echo "  Total Return: ${TOTAL_RETURN}%"
  echo "  Win Rate: ${WIN_RATE}%"
  echo
elif [ "$METRICS_STATUS" = "insufficient_data" ]; then
  MESSAGE=$(echo $METRICS_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('data', {}).get('message', 'Unknown error'))" 2>/dev/null)
  echo -e "${YELLOW}⚠ Insufficient data for metrics${NC}"
  echo "  Message: $MESSAGE"
  echo "  ${YELLOW}Note: You may need to wait or add more portfolio assets${NC}"
  echo
else
  echo -e "${RED}✗ Unexpected response${NC}"
  echo $METRICS_RESPONSE | python3 -m json.tool
  echo
fi

# Step 6: Test Benchmarks
echo -e "${YELLOW}[6/6] Fetching Benchmark Comparison...${NC}"
BENCHMARK_RESPONSE=$(curl -s -X GET "${API_URL}/analytics/benchmarks?period=365&benchmarks=SP500,BTC" \
  -H "Authorization: Bearer ${TOKEN}")

COMPARISONS=$(echo $BENCHMARK_RESPONSE | python3 -c "import sys, json; print(len(json.load(sys.stdin).get('data', {}).get('comparisons', [])))" 2>/dev/null)

if [ "$COMPARISONS" -gt 0 ]; then
  echo -e "${GREEN}✓ Benchmark data loaded (${COMPARISONS} comparisons)${NC}"
else
  echo -e "${YELLOW}⚠ No benchmark data available yet${NC}"
fi
echo

# Summary
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓ Setup complete!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo
echo "Next steps:"
echo "  1. Open your browser"
echo "  2. Go to the Analytics tab"
echo "  3. Scroll down to 'Advanced Metrics' section"
echo "  4. You should now see your portfolio metrics!"
echo
echo -e "${YELLOW}Note: If metrics still show 'insufficient data', try:${NC}"
echo "  - Adding more assets to your portfolio"
echo "  - Waiting a day for the automated snapshot"
echo "  - Running this script again tomorrow"
echo
