# Governance and security

> **Domain 1 — Designing Data Processing Systems (22%)** — the largest single design domain ·
> Success Guide pp. 1–17 · Ultimate §1.1–1.6, §2.1

| service | covers | state |
|---|---|---|
| [`01_sensitive_data/`](01_sensitive_data/) | **de-identification transforms**, infoTypes, likelihood | ✅ built |
| [`02_iam/`](02_iam/) | additive inheritance, least privilege, service accounts, org policies | 📝 documented |
| [`03_encryption/`](03_encryption/) | GMEK/CMEK/CSEK, KMS separation of duties, Secret Manager | 📝 documented |
| [`04_knowledge_catalog/`](04_knowledge_catalog/) | Knowledge Catalog (formerly Dataplex) entries/aspects, profiling vs AutoDQ, **policy tags** | 📝 documented |
| [`05_networking/`](05_networking/) | Private Google Access, PSA/PSC, **VPC SC vs exfiltration** | 📝 documented |

---

## The facts this domain keeps testing

**IAM inheritance is additive and cannot be revoked lower down.** Grant Viewer at the folder and
Editor at the project, and the user has Editor there. There is no "deny at a lower level" in basic
IAM — the tool for restriction is **Organization Policy**, or IAM **deny policies**, not a narrower
grant further down.

**Attach service accounts; do not download keys.** A key file is a credential that does not expire,
cannot be rotated by the platform, and ends up in a repository. Attach the account to the compute
resource, or use impersonation.

**The three encryption tiers, and where each one bites:**

| tier | key managed by | stored in | the catch |
|---|---|---|---|
| **GMEK** (default) | Google | Google | nothing to do — and nothing to prove |
| **CMEK** | you, via Cloud KMS | KMS / HSM | **the service agent needs `cryptoKeyEncrypterDecrypter` on the key**, or the service silently cannot write |
| **CSEK** | you, entirely | **you** | lose the key, lose the data. No recovery. |

That CMEK service-agent grant is the classic exam trap: the key exists, the config looks right, and
the service still cannot use it.

**Cloud KMS or Secret Manager?** KMS manages **keys that encrypt data**; Secret Manager stores
**secret strings** — API keys, passwords, connection strings — with versioning, delivered to the
application at runtime. A connection string does not belong in KMS.

**Data residency is an Organization Policy**, not a code decision:
`constraints/gcp.resourceLocations` restricts where resources may be created. "Data must remain in
the EU" is an org policy answer.

## Naming

Two services in this domain were renamed, and the API names did not follow:

| now | formerly | API |
|---|---|---|
| **Sensitive Data Protection** | Cloud DLP | still the *Cloud DLP API* |
| **Knowledge Catalog** | Dataplex Universal Catalog → Data Catalog | unchanged |

Data Catalog is **deprecated**, and it is not a clean rename — it used *tags*, its successors use
*aspects*. See [`99_reference/SERVICE_NAMES.md`](../99_reference/SERVICE_NAMES.md).

## What can and cannot run here

Almost all of this domain is **📝 write-only**: IAM, org policies, KMS, VPC Service Controls and
Knowledge Catalog have no local emulator and are configuration rather than computation.

The exception is [`01_sensitive_data/`](01_sensitive_data/). **De-identification transforms are
algorithms**, so they run — and running them produces the finding that matters most in this domain:

> Pseudonymising 50,000 identifiers preserved **100% of their uniqueness**. Hashing makes a value
> unreadable; it does not make a person unfindable. Only generalisation does that, and it costs
> you the resolution you were analysing.
