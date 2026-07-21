#!/data/data/com.termux/files/usr/bin/bash
# Termux helper: continuously report serving cell to Tower Device Monitor collector.
# Usage: ./tower_report_loop.sh http://192.168.1.10:8787 phone-1 5

set -euo pipefail
URL="${1:-http://127.0.0.1:8787}"
DEVICE_ID="${2:-phone-1}"
INTERVAL="${3:-5}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Reporting to $URL every ${INTERVAL}s as $DEVICE_ID"
while true; do
  python3 "$SCRIPT_DIR/tower_device_monitor.py" report --url "$URL" --device-id "$DEVICE_ID" || true
  sleep "$INTERVAL"
done
