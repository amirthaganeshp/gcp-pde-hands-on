# Checks

Scripts that verify the repository still works. **You never have to run them** — they exist so a
mistake shows up on purpose rather than by accident.

---

## 1. Run them on your own machine (no GitHub involved)

**On this laptop, run them inside WSL** — that is where the dependencies (Beam, PySpark, the
emulators, Java) are installed. Windows PowerShell has none of them.

Open a WSL shell:

```powershell
wsl -d Ubuntu-24.04
```

Then — and this matters — **change into the repo folder first**, because the command is a path
*relative to it*:

```bash
cd /path/to/gcloud-learning-pde        # wherever you cloned it
bash .github/scripts/run_list.sh fast
```

> If you see `No such file or directory`, you are in the wrong folder — that is all it means.
> `pwd` shows where you are.

The script finds the right Python by itself (it prefers `~/venvs/pde`), so there is nothing to set
up. It prints which one it chose on the first line, and warns you if that Python is missing the
dependencies.

It runs 14 of the 21 example scripts and prints a pass/fail line for each:

```
=== run-list (fast): 14 scripts ===
  00_setup/make_data.py                          rc=0     4s
  02_beam_dataflow/01_the_beam_model.py          rc=0     5s
  ...
=== 14 of 14 passed in 77s ===
```

`rc=0` means that script was fine. Anything else is a failure, and the script prints the last 40
lines of its output so you can see why.

The other three:

```bash
bash .github/scripts/run_list.sh full     # all 21 (needs emulators, Kafka, Redis, Airflow)
python .github/scripts/check_links.py     # every link between the READMEs still works
bash .github/scripts/check_no_leaks.sh    # nothing was left running in the background
```

**Measured here:** `fast` 14/14 in ~75 s · `full` 21/21 in 170–185 s · links 175/175 · leaks none.

---

## 2. Recipe: run them automatically on your own GitHub

*("Automatically" = every time you push, GitHub runs all this for you and emails you if something
broke. That is all CI means.)*

**This will not work on an enterprise-managed account** whose policy blocks hosted runners —
see section 4. On a personal account it does.

### Step 1 — make an empty repo on your personal account

Go to [github.com/new](https://github.com/new) while signed in as **your personal account** (not
a work-managed one). Name it whatever you like. **Choose Private.** Do not tick "Add a README".

> Private is the right default. Private repos get **2,000 free Actions minutes a month**, and the
> fast job takes about 3 minutes — so roughly 600 pushes a month before you'd pay anything. You
> will not get near that.

### Step 2 — point a copy of this repo at it

**Option A — keep the history:**

```bash
git clone <URL-of-this-repo> pde-personal
cd pde-personal
git remote set-url origin https://github.com/YOUR-USERNAME/YOUR-REPO-NAME.git
```

**Option B — start with a clean history** (one fresh commit, no past commit messages carried
over). Useful if the existing history contains anything you would rather not publish:

```bash
git clone <URL-of-this-repo> pde-personal
cd pde-personal
rm -rf .git
git init -b main
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPO-NAME.git
```

Option B loses the commit-by-commit story but gives you a repository with exactly the content you
can see in the files, and nothing else.

### Step 3 — turn the triggers on

Open `.github/workflows/run-list.yml`. Near the top you will see six commented lines. **Delete the
`#` from each** so it goes from this:

```yaml
on:
  workflow_dispatch:
  # push:
  #   branches: [main]
  # pull_request:
  #   branches: [main]
  # schedule:
  #   - cron: "0 6 * * 1"
```

to this:

```yaml
on:
  workflow_dispatch:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: "0 6 * * 1"
```

Indentation matters in YAML — keep the spacing exactly as shown.

### Step 4 — push

```bash
git add .github/workflows/run-list.yml
git commit -m "Enable CI"
git push -u origin main
```

### Step 5 — watch it

Open your repo on github.com and click the **Actions** tab. You will see a run appear within a few
seconds.

**What success looks like:** a green tick, and a results table under the run summary listing all 14
scripts. **What a failure looks like:** a red X, with the failing script named and its output
printed in the log.

That is it. From then on it runs on every push, with no action from you.

### What runs, and when

| job | when | how long | what it covers |
|---|---|---|---|
| **fast** | every push and PR | ~3 min | 14 items. Nothing to install beyond pip. |
| **full** | Mondays, or the **Run workflow** button | ~15 min | all 21 — emulators, Kafka, Redis, Airflow — plus the leak check |

`full` is kept off pushes on purpose: it is five times slower for very little extra signal.

---

## 3. What each check is for

| script | checks |
|---|---|
| **`run_list.sh`** | Runs every example. **Does not stop at the first failure**, so one broken script cannot hide the state of the others. Exits non-zero if anything failed. |
| **`check_links.py`** | Every link between the ~50 READMEs. Cheap, and it catches links that quietly rot as files move. |
| **`check_no_leaks.sh`** | Asserts no emulator, broker or cache was left running afterwards. |

### Why `check_no_leaks.sh` exists

On 2026-09-27 all 21 scripts were run together for the first time. Each one passed on its own — but
together they revealed that every script was **leaving its emulator running**. Five were found
still alive, the oldest for over five hours, while four READMEs claimed each script "starts and
stops its own emulator".

**No single script can catch that.** Only running them together can, and only if something checks
what was left behind. Full write-up in [`99_reference/FINDINGS.md`](../99_reference/FINDINGS.md)
§8b.

### Optional: run the fast check before every push

Not installed by default — it adds ~77 s to each push, which is your call:

```bash
cp .github/scripts/pre-push .git/hooks/pre-push && chmod +x .git/hooks/pre-push
```

Undo with `rm .git/hooks/pre-push`. Skip it once with `git push --no-verify`.

---

## 4. Why this is switched off by default

Pushing the workflow here on 2026-09-27 failed in 3 seconds:

> **GitHub Actions hosted runners are disabled for this repository. For more information please
> contact your GitHub Enterprise Administrator.**

| | |
|---|---|
| Actions enabled on the repo? | **yes** — but that is misleading; it does not mean anything can run |
| GitHub-**hosted** runners? | **disabled by enterprise policy** |
| Self-hosted runners registered? | **none** |

Nothing in this repo can fix that — it needs whoever administers GitHub for the organisation. So
the workflow is
set to **manual-only**, because left on `push` it would put a red X on every commit for a reason
that has nothing to do with the code.

**That is exactly why the logic lives in `scripts/` and not inside the workflow file.** All of it
runs on your laptop, unchanged, with no GitHub at all — and a CI-only script is one you can never
test.
