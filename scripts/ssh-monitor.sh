#!/bin/bash
# SSH Connection Monitor for 10.0.0.254
# Logs connection attempts and helps pinpoint when/why SSH dies

HOST="10.0.0.254"
LOG_FILE="${1:-/tmp/ssh-monitor.log}"

echo "SSH Monitor started at $(date)" | tee -a "$LOG_FILE"
echo "Logging to: $LOG_FILE"
echo "Press Ctrl+C to stop"
echo "---"

attempt=0
last_status="unknown"
fail_streak=0

while true; do
    attempt=$((attempt + 1))
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    # Test SSH
    start=$(date +%s.%N)
    ssh_result=$(timeout 5 ssh -o ConnectTimeout=3 -o BatchMode=yes "$HOST" "echo OK" 2>&1)
    end=$(date +%s.%N)
    elapsed=$(echo "$end - $start" | bc 2>/dev/null || echo "?")

    if [[ "$ssh_result" == "OK" ]]; then
        status="OK"
        fail_streak=0
        color="\033[32m"  # green
    else
        status="FAIL"
        fail_streak=$((fail_streak + 1))
        color="\033[31m"  # red
        # Extract error
        error=$(echo "$ssh_result" | grep -oE "(timed out|refused|reset|denied)" | head -1)
        [[ -z "$error" ]] && error="unknown"
    fi

    # Test ping (for comparison)
    ping_ok=$(ping -c 1 -W 1 "$HOST" >/dev/null 2>&1 && echo "Y" || echo "N")

    # Test Gitea port
    gitea_ok=$(timeout 2 curl -s "http://$HOST:3000/api/v1/version" >/dev/null && echo "Y" || echo "N")

    # Log line
    line="[$timestamp] #$attempt SSH:$status (${elapsed}s) Ping:$ping_ok Gitea:$gitea_ok"
    [[ "$status" == "FAIL" ]] && line="$line err=$error streak=$fail_streak"

    echo -e "${color}${line}\033[0m"
    echo "$line" >> "$LOG_FILE"

    # Alert on state change
    if [[ "$status" != "$last_status" ]]; then
        echo ">>> STATE CHANGE: $last_status -> $status at $timestamp" | tee -a "$LOG_FILE"
    fi
    last_status="$status"

    sleep 2
done
