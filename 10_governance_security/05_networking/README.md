# Network security for data — Private Access and VPC Service Controls

> **Domain 1 — Designing Data Processing Systems (22%)** · Success Guide §11.4 · Ultimate §1.4
> 📝 **Write-only** — network configuration; nothing to run locally.

---

## 1. What it is

**IAM answers "who may access this?". The network layer answers "from where?" — and, crucially,
"where may the data go?"**

Those are different questions, and the exam's favourite scenario is one IAM cannot solve: a user
with entirely legitimate credentials copying a table somewhere it should never go.

## 2. The three controls

| control | problem it solves |
|---|---|
| **Private Google Access** | VMs **without external IPs** still need to reach Google APIs. |
| **Private Service Connect / PSA** | Reach a managed service (Cloud SQL, published services) over **private IP**, no public exposure. |
| **VPC Service Controls (VPC SC)** | **Stop data leaving a perimeter**, even for a correctly-authenticated user. |

## 3. Private Google Access

A VM with no external IP cannot, by default, reach `bigquery.googleapis.com`. Enabling **Private
Google Access on the subnet** lets it reach Google APIs over Google's internal network — no public
IP, no NAT, no internet path.

**Variants worth knowing:**

| | for |
|---|---|
| **Private Google Access** | VMs in a subnet reaching Google APIs |
| **Private Service Connect** | a private endpoint **inside your VPC** for a Google or third-party service |
| **Private Services Access (PSA)** | VPC peering to Google's managed network — **how Cloud SQL gets a private IP** |

## 4. VPC Service Controls — the important one

**VPC SC draws a perimeter around managed services** (BigQuery, GCS, Pub/Sub…) and blocks data
movement across it, **independently of IAM**.

> **This is the answer to data exfiltration.** A user with `bigquery.dataViewer` can legitimately
> read a table and copy it into their own project. IAM permitted it. **VPC SC is the only control
> that stops it**, because the destination is outside the perimeter.

| concept | what it is |
|---|---|
| **Perimeter** | The set of projects and services inside the boundary. |
| **Access level** | Conditions that permit entry — IP range, device posture, identity. |
| **Ingress / egress rule** | Explicit exceptions for traffic in or out. |
| **Dry-run mode** | **Log violations without enforcing.** How you deploy this without an outage. |

**Always dry-run first.** A perimeter dropped onto a live estate breaks pipelines in ways that are
hard to attribute, because the failures surface as permission errors in unrelated places.

## 5. How this shows up in pipelines

| service | the network detail |
|---|---|
| **Dataflow** | `--no_use_public_ips` + Private Google Access; **worker-to-worker needs TCP 12345–12346** unless using service-side shuffle |
| **Dataproc** | nodes need **internal ingress on all TCP/UDP**, or cluster creation times out |
| **Cloud SQL** | **Private IP via PSA** — no public IP exposed at all |
| **Composer** | private environments keep the GKE cluster and web server off the internet |
| **Datastream** | needs a reachable source — VPC peering, VPN, Interconnect or SSH tunnel |

## 6. Nuances — the part worth reading

**IAM and VPC SC are complementary, not alternatives.** IAM grants the permission; VPC SC bounds
where it can be exercised. Both must allow an action for it to succeed — which is also why
debugging a denial means checking both.

**VPC SC protects *services*, not VMs.** It is a perimeter around API surfaces like BigQuery and
GCS, not a firewall. Firewall rules and VPC SC solve unrelated problems.

**A perimeter breaks legitimate integrations by design.** Partner access, a SaaS tool, a CI system
outside the perimeter — each needs an explicit ingress/egress rule or an access level. That
friction *is* the control working.

**Data residency is an Organization Policy, not a network control.** "Data must stay in the EU" is
`constraints/compute.resourceLocations` plus regional datasets — see
[`../02_iam/`](../02_iam/).

## 7. What was actually run

**Nothing.** Networking requires a real VPC. The reason it exists — keeping sensitive data from
leaving — is what [`../01_sensitive_data/`](../01_sensitive_data/) addresses from the data side,
and the two are genuinely different defences: VPC SC stops the table moving; de-identification
changes what the table reveals if it does.
