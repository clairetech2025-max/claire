# First Revenue Plan

Constraint: use only capabilities certified today. Do not rely on future provider/tool features.

## Fastest Sellable Offer

Offer: **Local Evidence Organization Pilot**

Deliverable:

- source document index;
- source hashes and `source_doc_id`;
- extracted dates/entities;
- simple timeline;
- attorney-review packet in Markdown/PDF;
- traceable metadata showing ARE event references;
- clear boundary that this is evidence organization, not legal advice.

## Top Three Customer Types

### 1. Small Law Offices / Paralegal Teams

Immediate need:

- organize client documents;
- build first-pass timelines;
- prepare review packets;
- preserve source links.

Why CLAIRE fits today:

- Veritas Legal evidence engine is working for local files;
- source hashing and metadata are certified;
- outputs are review support, not unauthorized legal advice.

### 2. Investigators / Compliance Reviewers

Immediate need:

- track evidence provenance;
- prove what was reviewed;
- distinguish source material from analysis.

Why CLAIRE fits today:

- source hash + ARE event references create an audit-friendly chain;
- packet output is useful even without a live LLM provider.

### 3. AI/Software Teams Needing Governed Memory

Immediate need:

- add memory to an app without trusting the model as memory authority;
- verify memory integrity;
- prevent cross-lane leakage.

Why CLAIRE fits today:

- `claire_are` API/SDK is usable as a standalone governed memory component;
- ingest/recall/verify/audit tests pass.

## Suggested First Paid Pilot

Scope:

- one customer;
- one local folder of documents;
- 1-2 hour setup/review session;
- deliver one evidence packet and source index;
- no cloud hosting;
- no private data retained after delivery unless contracted.

Pricing hypothesis:

- fixed pilot fee, not subscription;
- sell outcome: “organized evidence packet with source hashes and timeline.”

## What Not To Sell Yet

- fully autonomous CLAIRE assistant;
- live provider-backed general chatbot unless provider is configured and tested;
- legal advice;
- court filing;
- live trading;
- enterprise RBAC/security claims;
- all-file-type universal parser claims.

## Fastest Path To First Paying Customer

1. Pick one narrow buyer: small law office or investigator.
2. Offer fixed-scope document organization pilot.
3. Use only local Veritas + ARE certified path.
4. Deliver packet, source index, and trace metadata.
5. Ask for paid follow-up to improve parser/file coverage based on their real needs.

## Five Highest-Priority Engineering Tasks

1. Certify one real provider path end-to-end.
2. Add customer-safe export bundle for Veritas output.
3. Build direct GUI happy-path test for upload -> Veritas run -> packet download.
4. Certify PDF/DOCX with realistic customer-like samples.
5. Add a clean README/runbook for the paid pilot workflow.
