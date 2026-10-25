"""Dataform: compile the project, resolve the DAG, and prove the check has teeth.

`dataform compile` is the ONLY part of Dataform with an honest local check.
It parses every .sqlx file, resolves each ref() into a real dependency edge,
generates the SQL each action would run, and reports errors - all WITHOUT
connecting to BigQuery, without credentials, and without executing any SQL.

  1. Compile the project and read the resolved graph
  2. The DAG, as Dataform built it from ref() alone
  3. Assertions: the ones you declared vs the ones config generated
  4. The generated SQL - and why an incremental becomes a MERGE
  5. Break a ref() on a COPY, and watch compile catch it

EXECUTED IN FULL. Every number printed below was measured on this machine.

Nothing here touches BigQuery. `defaultProject` in workflow_settings.yaml is a
placeholder string - name resolution is offline, so it only has to exist.

Run:
    python 03_bigquery/02_dataform/compile_check.py

Needs node + npx. The CLI is fetched by npx on first run and cached after.

Guide reference: Success Guide pp. 60-64 (Dataform & BigQuery Pipelines).
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE / "dataform"
CLI = "@dataform/cli@3.0.0"


def rule(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def find_npx() -> str:
    """Find an npx that matches the OS we are actually running on.

    THE TRAP, and it is worse than the gcloud one: WSL puts the Windows PATH
    on the Linux PATH, and the Windows nodejs directory contains extensionless
    `npm` and `npx` shell scripts but only `node.exe`. So inside WSL you get

        node -> /home/you/.local/bin/node        (Linux, correct)
        npx  -> /mnt/c/Program Files/nodejs/npx  (WINDOWS, wrong)

    in the SAME shell. Running that npx under Linux hands Windows paths to a
    Windows node and fails in a way that looks like a broken project.
    """
    if platform.system() == "Windows":
        found = shutil.which("npx")
        if not found:
            raise SystemExit("npx not found on PATH. Install Node.js.")
        return found

    # Linux/WSL: prefer an explicitly Linux npx, and refuse anything on /mnt.
    for candidate in (Path.home() / ".local/bin/npx", Path("/usr/bin/npx"),
                      Path("/usr/local/bin/npx")):
        if candidate.exists():
            return str(candidate)

    found = shutil.which("npx")
    if found and found.startswith("/mnt/"):
        raise SystemExit(
            f"the only npx on PATH is a WINDOWS install ({found}).\n"
            "    Under WSL that cannot run this project. Install node in Linux,\n"
            "    or run this script from Windows instead."
        )
    if not found:
        raise SystemExit("npx not found.")
    return found


def npx_env(npx: str) -> dict:
    """Environment in which npx can actually find node.

    SECOND TRAP, found by running the repo's full run-list in a NON-LOGIN
    shell: npx is a script whose shebang is `#!/usr/bin/env node`. If node
    lives somewhere only the login profile adds to PATH (~/.local/bin here),
    then `bash -lc` works and plain `bash script.sh` fails with

        /usr/bin/env: 'node': No such file or directory

    which reads as "node is not installed" when it plainly is. So prepend the
    directory that actually holds the resolved npx/node to PATH.
    """
    env = dict(os.environ)
    node_dir = _node_dir(npx)
    if node_dir:
        env["PATH"] = f"{node_dir}{os.pathsep}{env.get('PATH', '')}"
    return env


def _node_dir(npx: str) -> str | None:
    """Directory containing the `node` that goes with this npx.

    NOT simply Path(npx).resolve().parent - resolve() follows the symlink
    chain ALL the way, and npx's chain ends inside npm's own lib directory:

        ~/.local/bin/npx
          -> ~/.local/node/bin/npx
          -> ~/.local/node/lib/node_modules/npm/bin/npx-cli.js   <- no node here

    So walk the chain one hop at a time and take the FIRST directory that
    actually contains an executable node - which is usually the very first,
    the bin directory you were given.
    """
    seen: set[str] = set()
    p = Path(npx)
    while True:
        candidate = p.parent / "node"
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(p.parent)
        if not p.is_symlink():
            break
        target = Path(os.readlink(p))
        p = target if target.is_absolute() else p.parent / target
        if str(p) in seen:
            break
        seen.add(str(p))

    found = shutil.which("node")
    return str(Path(found).parent) if found else None


def compile_project(project_dir: Path, npx: str) -> tuple[dict, str]:
    """Run `dataform compile --json`. Returns (parsed graph, stderr)."""
    proc = subprocess.run(
        [npx, "-y", CLI, "compile", "--json"],
        cwd=project_dir, capture_output=True, text=True,
        env=npx_env(npx),
        # npx on Windows is a .cmd shim; shell=True is needed there only.
        shell=(platform.system() == "Windows"),
    )
    out = proc.stdout.strip()
    if not out:
        return {}, proc.stderr
    try:
        return json.loads(out), proc.stderr
    except json.JSONDecodeError:
        return {}, proc.stderr or out


def qualified(target: dict) -> str:
    return f"{target.get('schema')}.{target.get('name')}"


# ------------------------------------------------------------------ 1 + 2
def section_dag(graph: dict) -> None:
    rule("1. THE COMPILED GRAPH")

    tables = graph.get("tables", [])
    assertions = graph.get("assertions", [])
    declarations = graph.get("declarations", [])
    errors = graph.get("graphErrors", {}).get("compilationErrors", [])

    # The CLI's own "Compiled N action(s)" counts datasets + assertions.
    # A declaration REFERENCES something Dataform does not manage, so it is in
    # the graph but is not an action - it creates nothing.
    actions = len(tables) + len(assertions)
    print(f"  Compiled {actions} action(s) with {len(errors)} error(s).")
    print(f"    datasets     : {len(tables):>2}   (things Dataform creates)")
    print(f"    assertions   : {len(assertions):>2}")
    print(f"    declarations : {len(declarations):>2}   (sources it only REFERENCES - not an action)")
    print(f"\n  dataformCoreVersion: {graph.get('dataformCoreVersion')}")
    print("  BigQuery connections made: 0.  Credentials used: none.")

    rule("2. THE DAG - built from ref(), not declared anywhere")

    # Every edge below came from a ref() call in the SQL. Nothing lists them.
    edges: list[tuple[str, str]] = []
    for t in tables:
        for dep in t.get("dependencyTargets", []):
            edges.append((qualified(dep), qualified(t["target"])))

    for d in declarations:
        print(f"  [declaration] {qualified(d['target'])}")
    for t in tables:
        kind = (t.get("enumType") or "?").lower()
        deps = [qualified(x) for x in t.get("dependencyTargets", [])]
        dep_s = ", ".join(deps) if deps else "-"
        print(f"  [{kind:<11}] {qualified(t['target']):<38} <- {dep_s}")

    print(f"\n  {len(edges)} dependency edge(s), every one resolved from a ref():")
    for src, dst in edges:
        print(f"    {src}  ->  {dst}")

    print("\n  Nothing in this project lists an execution order. The graph IS the")
    print("  code, which is why it cannot drift from it - the failure mode of a")
    print("  hand-maintained list of scheduled queries.")


# ---------------------------------------------------------------------- 3
def section_assertions(graph: dict) -> None:
    rule("3. ASSERTIONS - declared by hand vs generated from config")

    assertions = graph.get("assertions", [])
    hand, generated = [], []
    for a in assertions:
        name = a["target"]["name"]
        # A generated assertion carries the source table's name as a prefix.
        (generated if "_assertions_" in name else hand).append(a)

    print(f"  {len(assertions)} assertion(s) total\n")
    print(f"  Written by hand ({len(hand)}):")
    for a in hand:
        print(f"    {qualified(a['target'])}")
    print(f"\n  Generated from the config block ({len(generated)}):")
    for a in generated:
        print(f"    {qualified(a['target'])}")

    print("\n  uniqueKey / nonNull / rowConditions in a config block become REAL")
    print("  assertion actions in the graph. They are not comments - they run, and")
    print("  a failure stops the run BEFORE the reporting table is published.")
    print("\n  That is the whole argument over a scheduled query: a scheduled query")
    print("  producing wrong numbers SUCCEEDS.")


# ---------------------------------------------------------------------- 4
def section_generated_sql(graph: dict) -> None:
    rule("4. THE GENERATED SQL - an incremental is a MERGE")

    inc = next((t for t in graph.get("tables", [])
                if (t.get("enumType") or "").upper() == "INCREMENTAL"), None)
    if not inc:
        print("  (no incremental table found)")
        return

    def show(label: str, sql: str) -> None:
        print(f"  --- {label} ---")
        for line in [l for l in (sql or "").strip().splitlines() if l.strip()]:
            print(f"    {line}")
        print()

    print(f"  {qualified(inc['target'])}")
    print(f"  uniqueKey: {inc.get('uniqueKey')}\n")
    print("  ONE .sqlx file compiled into TWO queries, because of when():\n")

    show("FIRST RUN / full refresh - the when(incremental()) branch is ABSENT",
         inc.get("query"))
    show("EVERY RUN AFTER - the branch is PRESENT",
         inc.get("incrementalQuery"))

    print("  Note the ref() is already resolved to a real, fully-qualified name in")
    print("  both. That resolution is the thing compile exists to do.\n")
    print("  On the FIRST run this creates the table. On every run after, the")
    print("  uniqueKey turns it into a MERGE on (trip_date, start_station).")
    print("\n  That is what makes the 3-day reprocessing window safe: re-running an")
    print("  overlapping window UPDATES rows instead of duplicating them. An")
    print("  incremental without a uniqueKey is a blind append, and re-running it")
    print("  double-counts - the same idempotency rule as the CDC MERGE in")
    print("  07_migration_cdc and the Airflow retries in 05_orchestration.")


# ---------------------------------------------------------------------- 5
def section_break_it(npx: str) -> None:
    rule("5. DOES THE CHECK ACTUALLY CATCH ANYTHING?")

    print("  A check that only ever passes proves nothing. So: copy the project,")
    print("  break one ref(), and compile the copy.\n")

    with tempfile.TemporaryDirectory() as tmp:
        broken = Path(tmp) / "dataform"
        shutil.copytree(PROJECT, broken)

        target = broken / "definitions" / "trips_daily.sqlx"
        text = target.read_text(encoding="utf-8")
        text = text.replace('${ref("stg_trips")}', '${ref("stg_trip")}')  # typo
        target.write_text(text, encoding="utf-8")
        print('  Changed  ref("stg_trips")  ->  ref("stg_trip")   (one missing "s")\n')

        graph, stderr = compile_project(broken, npx)
        errors = graph.get("graphErrors", {}).get("compilationErrors", []) if graph else []

        if errors:
            print(f"  CAUGHT: {len(errors)} compilation error(s).")
            for e in errors[:3]:
                msg = (e.get("message") or "").splitlines()[0]
                print(f"    {Path(e.get('fileName','?')).name}: {msg}")
        elif stderr.strip():
            first = [l for l in stderr.splitlines() if "Error" in l or "error" in l]
            print(f"  CAUGHT: compile reported an error.")
            if first:
                print(f"    {first[0].strip()[:150]}")
        else:
            print("  NOT CAUGHT - which would mean this check is worthless.")

    print("\n  A one-character typo in a table reference is caught in seconds, with")
    print("  no project, no credentials and no query executed. The same typo in a")
    print("  scheduled query is found when the dashboard is wrong.")


def main() -> None:
    if not PROJECT.exists():
        raise SystemExit(f"project not found: {PROJECT}")

    npx = find_npx()
    print("DATAFORM COMPILE - resolving the DAG offline")
    print(f"  npx     : {npx}")
    print(f"  project : {PROJECT}")
    print(f"  cli     : {CLI}  (fetched by npx, cached after the first run)")

    graph, stderr = compile_project(PROJECT, npx)
    if not graph:
        print("\n  compile produced no JSON. stderr follows:\n")
        print(stderr[:2000])
        raise SystemExit(1)

    section_dag(graph)
    section_assertions(graph)
    section_generated_sql(graph)
    section_break_it(npx)

    rule("WHAT THIS DOES NOT DO")
    print("""  compile is a STATIC check. It resolves names, builds the graph and
  generates SQL. It does not:

    - connect to BigQuery, or validate that trips_raw exists
    - check that a column you referenced is really in the source schema
    - run a single assertion (they compile; only `dataform run` executes them)
    - detect that your SQL is logically wrong

  So a clean compile means the GRAPH is sound, not that the pipeline is
  correct. That is still worth having in CI: it catches every broken ref,
  every circular dependency and every syntax error before deployment, which
  is the class of failure that otherwise reaches production.""")


if __name__ == "__main__":
    main()
