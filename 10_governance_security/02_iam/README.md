# IAM and Organization Policies

> **Domain 1 — Designing Data Processing Systems (22%)** · Success Guide pp. 10–13 · Ultimate §1.1
> 📝 **Write-only** — IAM is configuration; there is nothing to execute locally.

---

## 1. What it is

**IAM controls *who* can do *what* to *which* resource. Organization Policies control *how*
resources may be configured at all.** They are different systems and the exam tests the
difference.

## 2. Components

| component | what it is |
|---|---|
| **Principal** (who) | Google account, Google Group, **service account**, or Cloud Identity domain. |
| **Role** (what) | A bundle of permissions. |
| **Policy** | The binding of principals to roles, **attached to a resource**. |
| **Resource hierarchy** | Organization → Folders → Projects → Resources. |

### Role types

| | |
|---|---|
| **Basic** — Owner, Editor, Viewer | **Avoid.** Far too broad, and a wrong answer on the exam by default. |
| **Predefined** — `roles/bigquery.dataViewer` | Google-maintained, fine-grained. **The right answer almost always.** |
| **Custom** | When no predefined role fits precisely. |

## 3. Inheritance — the rule that catches people

**IAM policies inherit top-down and are ADDITIVE.**

> Grant `Viewer` at the folder and `Editor` at the project, and the user has **Editor** on that
> project. **You cannot take away, at a lower level, access granted at a higher one.**

That asymmetry is the whole reason access creeps: a well-meaning grant at the org level cannot be
walked back per-project with IAM alone. (To actually constrain it you need **VPC Service Controls**
or an **Organization Policy** — see below and [`../05_networking/`](../05_networking/).)

**Organization Policies invert the rule:** they also inherit top-down, but **you can override or
create exceptions at a lower level**.

| constraint | effect |
|---|---|
| `constraints/compute.resourceLocations` | restricts where resources may be created — "data stays in the EU" |
| `constraints/iam.allowedPolicyMemberDomains` | only principals from your domain can be added |
| `constraints/compute.vmExternalIpAccess` | blocks public IPs on VMs |

## 4. Least privilege in practice

**The canonical exam scenario:** an analyst must query one sales dataset but must not see HR data
or drop tables.

| | |
|---|---|
| ❌ **Wrong** | `roles/editor` on the project, or `roles/bigquery.admin` |
| ✅ **Right** | `roles/bigquery.dataViewer` **on that dataset**, plus `roles/bigquery.jobUser` on the project to run queries |

**That two-role split is worth memorising.** `dataViewer` grants reading the data;
`jobUser` grants *running a query at all*. Give only the first and the analyst can see nothing
because they cannot start a job.

**Dataset-level isolation** is the standard answer to "several teams in one project": a dataset per
team, Data Editor for leads at their dataset, Data Viewer for members.

## 5. Service accounts — the data-engineering part

**Pipelines should run as service accounts, not as people.** A Dataflow job reading GCS and writing
BigQuery gets its own SA with exactly those two permissions.

> **Do not create service-account keys.** A JSON key does not expire, cannot be rotated by the
> platform, and ends up committed to a repository. **Attach the service account** to the compute
> resource, or use **impersonation** (`--impersonate-service-account=`).

| instead of | do |
|---|---|
| downloading a key for a VM/Dataproc/Dataflow job | **attach the SA** to the resource |
| a key for local development | **`gcloud auth application-default login`** or impersonation |
| a long-lived key for CI | **Workload Identity Federation** |

## 6. Nuances — the part worth reading

**IAM is not row- or column-level security.** It stops at the *resource*. Restricting columns is
**policy tags** ([`../04_knowledge_catalog/`](../04_knowledge_catalog/)); restricting rows is a
**row-level access policy**; restricting a *slice* is an **authorized view**.

**IAM cannot prevent exfiltration.** A user with legitimate `dataViewer` can copy the table
somewhere else. That is what **VPC Service Controls** exists for — and it is why the two appear
together in questions about data leaving a perimeter.

**Groups, not individuals.** Bind roles to Google Groups; manage membership there. Every "how do we
manage this at scale" answer is a group.

## 7. What was actually run

**Nothing.** IAM is configuration on a real organization. What it *protects* is demonstrated next
door in [`../01_sensitive_data/`](../01_sensitive_data/), where pseudonymising 50,000 identifiers
preserved **100.0%** uniqueness — a reminder that access control and de-identification solve
different problems.
