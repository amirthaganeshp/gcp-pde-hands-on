# Dataform — what the illustration shows

The README explains the *service*. This file explains the *check*: what `dataform compile`
actually does, what it proved here, and — just as importantly — what a clean compile does **not**
mean.

---

## What `compile` is

Dataform's CLI separates **compiling** from **running**, and only the first is local.

| | connects to BigQuery? | executes SQL? | needs credentials? |
|---|---|---|---|
| **`dataform compile`** | **no** | **no** | **no** |
| `dataform run` | yes | yes | yes |

`compile` parses every `.sqlx` file, resolves each `ref()` into a real fully-qualified name, builds
the dependency DAG, generates the SQL each action *would* run, and reports errors. It prints the
whole graph as JSON.

**That makes it the only part of this service with an honest local check** — and the reason this
folder is ✅ rather than 📝.

> `defaultProject: pde-learning-placeholder` in `workflow_settings.yaml` is a placeholder string.
> Name resolution is offline, so the project only has to *exist as text*.

## The project being compiled

[`dataform/definitions/`](dataform/definitions/) — deliberately small, but covering the four things
the exam cares about:

| file | type | demonstrates |
|---|---|---|
| `sources.sqlx` | declaration | a source Dataform **references but does not manage** |
| `stg_trips.sqlx` | view | cleaning, and the first `ref()` edge |
| `trips_daily.sqlx` | table | `partitionBy` / `clusterBy`, and **config-block assertions** |
| `trips_daily_incremental.sqlx` | incremental | `uniqueKey` + `when(incremental(), …)` |
| `assert_no_future_trips.sqlx` | assertion | a **hand-written** data-quality test |

## What the run measured

```
Compiled 6 action(s) with 0 error(s).
  datasets     :  3   (things Dataform creates)
  assertions   :  3
  declarations :  1   (sources it only REFERENCES - not an action)

BigQuery connections made: 0.  Credentials used: none.
```

### The DAG, built from `ref()` alone

```
raw.trips_raw          ->  analytics.stg_trips
analytics.stg_trips    ->  analytics.trips_daily
analytics.stg_trips    ->  analytics.trips_daily_incremental
```

**Nothing in the project lists an execution order.** Three edges, each recovered from a `ref()`
call inside the SQL. The graph *is* the code, which is why it cannot drift from it — the failure
mode of a hand-maintained set of scheduled queries.

### Assertions: 1 written, 2 generated

```
Written by hand (1):   analytics_assertions.assert_no_future_trips
Generated (2):         ..._trips_daily_assertions_uniqueKey_0
                       ..._trips_daily_assertions_rowConditions
```

**`uniqueKey` / `nonNull` / `rowConditions` in a config block become real assertion *actions* in
the graph.** They are not documentation — they run, and a failure stops the run **before** the
reporting table is published.

> That is the whole argument over a scheduled query: **a scheduled query producing wrong numbers
> succeeds.**

### One file, two compiled queries

The clearest thing compile shows. `when(incremental(), …)` produces two variants, and you can read
both without running anything:

```sql
-- FIRST RUN / full refresh          -- EVERY RUN AFTER
SELECT ...                            SELECT ...
FROM `...analytics.stg_trips`         FROM `...analytics.stg_trips`
                                      WHERE trip_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY)
GROUP BY trip_date, start_station     GROUP BY trip_date, start_station
```

They differ by exactly the `WHERE`. With `uniqueKey: ["trip_date", "start_station"]` the second
becomes a **MERGE**, which is what makes the 3-day reprocessing window safe: re-running an
overlapping window **updates** rows instead of duplicating them.

**An incremental without a `uniqueKey` is a blind append**, and re-running it double-counts — the
same idempotency rule as the CDC `MERGE` in
[`07_migration_cdc`](../../07_migration_cdc/01_datastream/) and Airflow retries in
[`05_orchestration`](../../05_orchestration/01_composer/).

## Does the check actually catch anything?

A check that only ever passes proves nothing. So the script copies the project, makes a
one-character typo, and compiles the copy:

```
Changed  ref("stg_trips")  ->  ref("stg_trip")

CAUGHT: 2 compilation error(s).
  trips_daily.sqlx: Could not resolve "stg_trip"
  trips_daily.sqlx: Missing dependency detected: ... depends on "stg_trip" which does not exist
```

**Caught in seconds, with no project and no credentials.** The same typo in a scheduled query is
found when the dashboard is wrong.

## Two things this build taught, both real

**1. The action name is the filename.** The first version of this project used numbered files —
`02_stg_trips.sqlx` — and every `ref("stg_trips")` failed to resolve, because the action was
called `02_stg_trips`. The fix is to drop the numbers, and the lesson is that **numbering Dataform
files is a habit carried over from imperative SQL scripts**: the DAG determines order, so the names
should be the table names.

**2. WSL gives you Linux `node` and Windows `npx` in the same shell.** The Windows nodejs directory
contains extensionless `npm`/`npx` shell scripts but only `node.exe` — so `command -v node` finds
the Linux one while `command -v npx` finds the Windows one under `/mnt/c`. Running that npx under
Linux hands Windows paths to a Windows node and fails in a way that looks like a broken project.
`find_npx()` prefers an explicitly Linux npx and **refuses `/mnt/`**, exactly as `find_gcloud()`
does in [`01_ingestion/01_pubsub`](../../01_ingestion/01_pubsub/).

**3. A login shell was hiding a real bug — the full run-list found it.** Every manual test of this
script used `bash -lc`, which sources the profile and puts `~/.local/bin` on `PATH`. Run from a
plain **non-login** shell, npx died instantly:

```
/usr/bin/env: 'node': No such file or directory
```

npx is a script whose shebang is `#!/usr/bin/env node`. With `node` only on the *login* PATH, the
error says node is missing when it is plainly installed.

**And the first fix was also wrong.** `Path(npx).resolve().parent` follows the symlink chain *all
the way*, and npx's chain ends inside npm's own library directory, which has no `node` in it:

```
~/.local/bin/npx
  -> ~/.local/node/bin/npx
  -> ~/.local/node/lib/node_modules/npm/bin/npx-cli.js     <- no node here
```

`_node_dir()` now walks the chain **one hop at a time** and takes the first directory that actually
contains an executable `node` — usually the very first, the bin directory you were handed.

> The lesson generalises past this script: **if you only ever test in an interactive or login
> shell, you are not testing what CI runs.**

## What a clean compile does NOT mean

```
- it does not connect to BigQuery, or check that trips_raw exists
- it does not verify a referenced column is in the source schema
- it does not run a single assertion (compile builds them; only `run` executes)
- it does not detect that your SQL is logically wrong
```

**A clean compile means the graph is sound, not that the pipeline is correct.** That is still worth
having in CI: it catches every broken `ref()`, every circular dependency and every syntax error
before deployment — which is the class of failure that otherwise reaches production.
