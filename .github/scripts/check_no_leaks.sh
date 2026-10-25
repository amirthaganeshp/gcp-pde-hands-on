#!/usr/bin/env bash
# Assert that the run-list left no emulator or server process behind.
#
# This encodes a real bug, found on 2026-09-27 by running the whole list as
# one batch: proc.terminate() killed the `gcloud beta emulators start`
# WRAPPER and orphaned the java/Go child that actually holds the port. Five
# orphans were left behind, the oldest running for over five hours, while
# four READMEs claimed each script "starts and stops its own emulator".
#
# Individually-passing scripts cannot catch this. Only the batch can.
set -uo pipefail

PATTERN='cbtemulator|firestore_emulator|firestore-emulator\.jar|pubsub-emulator|redis-server|kafka\.Kafka'

LEFT=$(ps -eo pid,etimes,cmd 2>/dev/null | grep -E "$PATTERN" | grep -v grep || true)

if [ -z "$LEFT" ]; then
  echo "clean - no emulator, broker or cache process left running"
  exit 0
fi

echo "LEAKED processes still running after the run-list:"
echo "$LEFT" | cut -c1-140
echo
echo "Each script must stop what it started. See _stop_emulator() - terminate"
echo "the process GROUP, not just the gcloud wrapper."
exit 1
