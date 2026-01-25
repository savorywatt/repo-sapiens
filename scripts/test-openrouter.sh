#!/usr/bin/env bash
# Test OpenRouter API key and model access
#
# Usage:
#   ./scripts/test-openrouter.sh YOUR_API_KEY
#   OPENROUTER_API_KEY=xxx ./scripts/test-openrouter.sh

set -e

API_KEY="${1:-$OPENROUTER_API_KEY}"
MODEL="${2:-deepseek/deepseek-r1-0528:free}"

if [[ -z "$API_KEY" ]]; then
    echo "Usage: $0 <api_key> [model]"
    echo "   or: OPENROUTER_API_KEY=xxx $0"
    exit 1
fi

echo "Testing OpenRouter API..."
echo "Model: $MODEL"
echo "Key: ${API_KEY:0:10}...${API_KEY: -4}"
echo ""

# Test 1: List models (no auth required)
echo "=== Test 1: List models (checking connectivity) ==="
MODEL_COUNT=$(curl -s "https://openrouter.ai/api/v1/models" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('data',[])))" 2>/dev/null || echo "0")
echo "Available models: $MODEL_COUNT"
echo ""

# Test 2: Simple chat without tools
echo "=== Test 2: Simple chat request ==="
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "https://openrouter.ai/api/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d "{\"model\": \"$MODEL\", \"messages\": [{\"role\": \"user\", \"content\": \"Say hello in 5 words or less\"}]}")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)

echo "HTTP Status: $HTTP_CODE"
if [[ "$HTTP_CODE" == "200" ]]; then
    echo "Success!"
    echo "Response: $(echo "$BODY" | python3 -c "import sys,json; r=json.load(sys.stdin); print(r.get('choices',[{}])[0].get('message',{}).get('content','')[:200])" 2>/dev/null || echo "$BODY")"
else
    echo "Error response:"
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
fi
echo ""

# Test 3: Chat with tools (what the workflow uses)
echo "=== Test 3: Chat with tools (function calling) ==="
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "https://openrouter.ai/api/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "model": "'"$MODEL"'",
    "messages": [{"role": "user", "content": "What is 2+2?"}],
    "tools": [{"type": "function", "function": {"name": "calculate", "description": "Do math", "parameters": {"type": "object", "properties": {"expr": {"type": "string"}}}}}],
    "tool_choice": "auto"
  }')

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)

echo "HTTP Status: $HTTP_CODE"
if [[ "$HTTP_CODE" == "200" ]]; then
    echo "Success! Tools are supported."
elif [[ "$HTTP_CODE" == "404" ]]; then
    echo "404 Error - This might be why the workflow fails!"
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
else
    echo "Response:"
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
fi
