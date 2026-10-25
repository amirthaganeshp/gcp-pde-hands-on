# Encryption and key management

> **Domain 1 — Designing Data Processing Systems (22%)** · Success Guide p. 11 · Ultimate §1.2
> 📝 **Write-only** — KMS is a managed service; nothing here was executed.

---

## 1. What it is

**Everything on Google Cloud is encrypted at rest and in transit by default, with no action from
you.** The exam question is never *whether* to encrypt — it is **who controls the key**.

| | key managed by | key stored in | overhead | use when |
|---|---|---|---|---|
| **GMEK** (default) | **Google** | Google | **zero** | no specific compliance mandate on key ownership |
| **CMEK** | **you**, via Cloud KMS | Cloud KMS / Cloud HSM | moderate — you own rotation, destruction, access | HIPAA, PCI-DSS and similar, where the customer must control the key lifecycle |
| **CSEK** | **you**, supplied per request | **outside GCP entirely** | high — **lose the key and the data is unrecoverable** | extreme requirements where no key material may live at the provider |

## 2. The support boundary — a favourite exam fact

**CSEK is supported by very few services** — principally **Cloud Storage** and **Compute Engine
persistent disks**.

> For the managed analytics services — **BigQuery, Dataflow, Dataproc, Spanner** — **CSEK does not
> exist. If you need customer-controlled keys there, the answer is CMEK.**

## 3. Cloud KMS components

| component | what it is |
|---|---|
| **Key ring** | A logical group of keys. **Regional, and cannot be deleted once created.** |
| **Key** | The cryptographic key, with versions. |
| **Key version** | What actually encrypts. Rotation creates a new one; old versions stay for decryption. |
| **Cloud HSM** | Hardware security module backing (FIPS 140-2 Level 3). |
| **Cloud EKM** | Key held by an **external** partner, outside Google entirely. |

## 4. Separation of duties

Least privilege applies to the keys themselves: **the person who administers keys should not be the
person who uses them to decrypt data.**

| role | can | cannot |
|---|---|---|
| `roles/cloudkms.admin` | manage key rings, keys, IAM on them | **encrypt or decrypt** |
| `roles/cloudkms.cryptoKeyEncrypterDecrypter` | encrypt and decrypt with the key | manage keys |

## 5. The CMEK trap worth memorising

**A service cannot use your key unless its own service agent is granted access to it.**

> When enabling CMEK on BigQuery or Cloud Storage, grant that service's **service agent**
> `roles/cloudkms.cryptoKeyEncrypterDecrypter` **on the key**. Miss this and writes fail with a
> permission error that looks like an IAM problem on the *data*, not the key.

This is the single most-tested detail in this topic.

## 6. Secret Manager vs Cloud KMS

Constantly confused, and genuinely different:

| | **Cloud KMS** | **Secret Manager** |
|---|---|---|
| holds | **keys** that encrypt large payloads | **the secret string itself** |
| for | a BigQuery table, a bucket, a disk | API keys, DB passwords, TLS certs, connection strings |
| serves | encrypt/decrypt operations | the value, to your app or pipeline at runtime |
| versioning | key versions | secret versions |

> **KMS protects data. Secret Manager stores credentials.** If the scenario says "database
> password" or "API key", it is Secret Manager — never KMS, and never a file in the repo.

## 7. Nuances — the part worth reading

**Rotation does not re-encrypt existing data.** A new key version encrypts *new* writes; old data
stays readable via the old version. Genuinely re-keying means rewriting the data.

**Destroying a key destroys the data.** There is a scheduled-destruction delay precisely because
the operation is unrecoverable. With CSEK the same is true immediately and without a safety net —
Google does not hold a copy.

**Key rings are regional and permanent.** Plan the location; you cannot tidy them up later.

**CMEK adds an availability dependency.** If the key is unavailable — wrong region, revoked
permission, disabled version — the *data service* fails. You have taken on an operational
responsibility, which is the real cost of "moderate overhead".

## 8. What was actually run

**Nothing.** Everything here requires a real project and real keys. The adjacent, genuinely
measurable topic is de-identification, in [`../01_sensitive_data/`](../01_sensitive_data/) —
**encryption protects data at rest from outsiders; de-identification changes what the data says
about a person.** They are not substitutes, which is why they are separate folders.
