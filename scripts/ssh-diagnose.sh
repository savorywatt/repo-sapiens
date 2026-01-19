#!/bin/bash
# SSH Connection Diagnostic - runs tests to identify blocking patterns

HOST="10.0.0.254"
echo "=== SSH Diagnostic for $HOST ==="
echo "Started: $(date)"
echo ""

# Test 1: Baseline connectivity
echo "--- Test 1: Baseline Connectivity ---"
echo -n "Ping: "; ping -c 1 -W 2 "$HOST" >/dev/null 2>&1 && echo "OK" || echo "FAIL"
echo -n "Gitea (3000): "; curl -s --max-time 2 "http://$HOST:3000/api/v1/version" >/dev/null && echo "OK" || echo "FAIL"
echo -n "SSH (22): "; timeout 5 ssh -o ConnectTimeout=3 -o BatchMode=yes "$HOST" "echo OK" 2>/dev/null && echo "" || echo "FAIL"
echo ""

# Test 2: Rapid connection test
echo "--- Test 2: Rapid Connection Pattern (5 attempts, 0.5s apart) ---"
for i in 1 2 3 4 5; do
    result=$(timeout 5 ssh -o ConnectTimeout=3 -o BatchMode=yes "$HOST" "echo OK" 2>&1)
    [[ "$result" == "OK" ]] && echo "  $i: OK" || echo "  $i: FAIL ($(echo $result | grep -oE 'timed out|refused|reset' || echo 'error'))"
    sleep 0.5
done
echo ""

# Test 3: Recovery time test
echo "--- Test 3: Recovery Time Test ---"
echo "Waiting 10s to see if SSH recovers..."
sleep 10
result=$(timeout 8 ssh -o ConnectTimeout=5 -o BatchMode=yes "$HOST" "echo OK" 2>&1)
[[ "$result" == "OK" ]] && echo "  After 10s: RECOVERED" || echo "  After 10s: STILL BLOCKED"

sleep 20
result=$(timeout 8 ssh -o ConnectTimeout=5 -o BatchMode=yes "$HOST" "echo OK" 2>&1)
[[ "$result" == "OK" ]] && echo "  After 30s: RECOVERED" || echo "  After 30s: STILL BLOCKED"
echo ""

# Test 4: Port scan during block
echo "--- Test 4: Port Accessibility (during potential block) ---"
# Trigger block first
for i in 1 2 3; do timeout 1 ssh -o ConnectTimeout=1 -o BatchMode=yes "$HOST" ":" 2>/dev/null; done
sleep 1

echo -n "  Port 22 (nc): "; timeout 2 nc -zv "$HOST" 22 2>&1 | grep -q "succeeded\|open" && echo "OPEN" || echo "BLOCKED/CLOSED"
echo -n "  Port 3000 (nc): "; timeout 2 nc -zv "$HOST" 3000 2>&1 | grep -q "succeeded\|open" && echo "OPEN" || echo "BLOCKED/CLOSED"
echo -n "  Port 2222 (nc): "; timeout 2 nc -zv "$HOST" 2222 2>&1 | grep -q "succeeded\|open" && echo "OPEN" || echo "BLOCKED/CLOSED"
echo ""

echo "=== Diagnostic Complete ==="
echo "If SSH fails after 1-2 connections but recovers after 30s+, likely rate limiting."
echo "If port 22 shows BLOCKED but 3000/2222 work, it's SSH-specific filtering."
