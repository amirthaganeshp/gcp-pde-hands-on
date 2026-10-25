#!/usr/bin/env bash
# Run the canonical run-list and report every exit code.
#
#   bash .github/scripts/run_list.sh fast    # 14 items, no system services
#   bash .github/scripts/run_list.sh full    # all 21
#
# Deliberately does NOT abort on the first failure: every item runs, so one
# broken script cannot mask the state of the rest. Exits non-zero at the end
# if anything failed.
#
# Runs locally as well as in CI - a CI-only script is one you cannot test.
set -uo pipefail

MODE="${1:-fast}"

# Find a python that actually has this repo's dependencies.
#   - honour $PYTHON if the caller set it
#   - otherwise prefer the project venv (WSL), where beam/pyspark/pyarrow live
#   - otherwise fall back to whatever is on PATH (this is the CI case)
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  if [ -x "$HOME/venvs/pde/bin/python" ]; then
    PY="$HOME/venvs/pde/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PY="python3"
  else
    PY="python"
  fi
fi
AIRFLOW_BIN="${AIRFLOW_BIN:-$HOME/venvs/airflow/bin/airflow}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT" || exit 1

FAST=(
  "00_setup/make_data.py"
  "02_beam_dataflow/01_the_beam_model.py"
  "02_beam_dataflow/02_windows_and_watermarks.py"
  "02_beam_dataflow/03_batch_processing.py"
  "03_bigquery/01_bigquery/partition_pruning.py"
  "03_bigquery/02_dataform/compile_check.py"
  "04_managed_spark/01_spark/spark_basics.py"
  "06_storage_decisions/01_object/storage_class_cost.py"
  "07_migration_cdc/01_datastream/cdc_patterns.py"
  "07_migration_cdc/02_transfer/transfer_decision.py"
  "08_sharing_and_viz/01_sharing/sharing_privacy.py"
  "10_governance_security/01_sensitive_data/deidentification.py"
  "11_ops_cost_monitoring/01_cost/bigquery_economics.py"
  "11_ops_cost_monitoring/02_monitoring/alerting_thresholds.py"
)

EXTRA=(
  "01_ingestion/01_pubsub/pubsub_basics.py"
  "01_ingestion/02_kafka/kafka_basics.py"
  "06_storage_decisions/04_in_memory/memorystore_caching.py"
  "06_storage_decisions/06_nosql/01_bigtable/row_key_design.py"
  "06_storage_decisions/06_nosql/02_firestore/firestore_queries.py"
  "12_capstone/pipeline_end_to_end.py"
)

case "$MODE" in
  fast) SCRIPTS=("${FAST[@]}") ;;
  full) SCRIPTS=("${FAST[@]}" "${EXTRA[@]}") ;;
  *) echo "usage: $0 [fast|full]" >&2; exit 2 ;;
esac

echo "python: $PY"
if ! "$PY" -c "import apache_beam" >/dev/null 2>&1; then
  echo
  echo "WARNING: '$PY' cannot import apache_beam, so the Beam examples will fail."
  echo "         On this machine the dependencies live in the WSL venv. Run inside"
  echo "         WSL, or set PYTHON=/path/to/python explicitly."
  echo
fi

LOGDIR="$(mktemp -d)"
RESULTS="$LOGDIR/results.tsv"
: > "$RESULTS"
FAILED=0
TOTAL_START=$SECONDS

# The Airflow item is appended after the loop (own virtualenv), so count it
# here too - otherwise the header says 20 and the summary says 21.
HEADER_COUNT=${#SCRIPTS[@]}
[ "$MODE" = "full" ] && HEADER_COUNT=$((HEADER_COUNT + 1))
echo "=== run-list ($MODE): $HEADER_COUNT scripts ==="
for s in "${SCRIPTS[@]}"; do
  printf '  %-62s ' "$s"
  START=$SECONDS
  log="$LOGDIR/$(echo "$s" | tr '/' '_').log"
  timeout 900 "$PY" "$s" > "$log" 2>&1
  RC=$?
  DUR=$((SECONDS - START))
  printf 'rc=%-3s %3ss\n' "$RC" "$DUR"
  printf '%s\t%s\t%s\n' "$RC" "$DUR" "$s" >> "$RESULTS"
  if [ "$RC" -ne 0 ]; then
    FAILED=$((FAILED + 1))
    echo "----- output of failing $s -----"
    tail -40 "$log"
    echo "----- end -----"
  fi
done

# Airflow lives in its own virtualenv, deliberately: it and Beam have
# genuinely incompatible pins (cryptography, grpcio).
if [ "$MODE" = "full" ]; then
  printf '  %-62s ' "airflow dags test trips_daily"
  START=$SECONDS
  log="$LOGDIR/airflow.log"
  if [ -x "$AIRFLOW_BIN" ]; then
    ( cd 05_orchestration/01_composer && \
      AIRFLOW_HOME="${AIRFLOW_HOME:-$HOME/airflow}" \
      timeout 900 "$AIRFLOW_BIN" dags test trips_daily 2026-06-05 ) > "$log" 2>&1
    RC=$?
  else
    echo "airflow not found at $AIRFLOW_BIN" > "$log"
    RC=127
  fi
  DUR=$((SECONDS - START))
  printf 'rc=%-3s %3ss\n' "$RC" "$DUR"
  printf '%s\t%s\t%s\n' "$RC" "$DUR" "airflow dags test trips_daily" >> "$RESULTS"
  if [ "$RC" -ne 0 ]; then
    FAILED=$((FAILED + 1))
    echo "----- output of failing airflow -----"; tail -40 "$log"; echo "----- end -----"
  fi
fi

TOTAL=$((SECONDS - TOTAL_START))
COUNT=$(wc -l < "$RESULTS")

echo
echo "=== $((COUNT - FAILED)) of $COUNT passed in ${TOTAL}s ==="

# A results table in the GitHub run summary, so a failure is readable without
# opening the log.
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  {
    echo "### run-list (\`$MODE\`)"
    echo
    echo "**$((COUNT - FAILED)) of $COUNT passed in ${TOTAL}s**"
    echo
    echo "| | secs | script |"
    echo "|---|---|---|"
    while IFS=$'\t' read -r rc secs name; do
      if [ "$rc" -eq 0 ]; then mark="ok"; else mark="**FAIL ($rc)**"; fi
      echo "| $mark | $secs | \`$name\` |"
    done < "$RESULTS"
  } >> "$GITHUB_STEP_SUMMARY"
fi

exit $(( FAILED > 0 ? 1 : 0 ))
