# Top 10 Customer Demos

Each demo uses capabilities that are working or narrowly certified today. Each is designed to complete in under 5 minutes.

## 1. Source-Linked Evidence Packet

- Goal: Turn one document into a traceable attorney-review packet.
- User problem: Legal/support teams lose track of where facts came from.
- Steps: Upload a TXT/PDF/DOCX file, run Veritas Legal, open generated packet.
- Expected result: Exhibit index, source hash, timeline, not-legal-advice boundary.
- Why someone would pay: Reduces intake/review time and preserves source control.

## 2. Evidence Hash Proof

- Goal: Show a file gets a stable source hash and matter-specific source ID.
- User problem: Documents get renamed or copied and provenance becomes unclear.
- Steps: Ingest same file under two matter IDs.
- Expected result: Same SHA-256, different matter-scoped `source_doc_id`.
- Why someone would pay: Reliable evidence tracking.

## 3. Correction Memory

- Goal: Show CLAIRE remembers a correction without deleting history.
- User problem: AI systems forget or overwrite important changes.
- Steps: Save ORCHARD, ask unrelated question, ask follow-up, correct to RIVERSTONE, ask current/history.
- Expected result: Current value RIVERSTONE, historical value ORCHARD.
- Why someone would pay: Durable continuity for projects and investigations.

## 4. Restart Continuity

- Goal: Prove memory survives process restart.
- User problem: Chatbots lose context between sessions.
- Steps: Save a project fact, restart runtime using same SQLite store, ask for the fact.
- Expected result: Fact is recalled and trace is retrievable.
- Why someone would pay: Persistent working memory.

## 5. Recall-Before-Generation Trace

- Goal: Show provider generation happens after memory recall.
- User problem: AI claims memory but cannot prove it.
- Steps: Run certified continuity prompt and inspect trace.
- Expected result: Trace step `are_chronological_recall` precedes `nemotron_prompt_construction`.
- Why someone would pay: Auditable AI workflow.

## 6. Lane Isolation

- Goal: Show legal/architecture memories do not leak across lanes.
- User problem: AI retrieves irrelevant or sensitive context.
- Steps: Save architecture memory, query from legal lane.
- Expected result: Empty recall result.
- Why someone would pay: Safer memory use.

## 7. Secret Redaction

- Goal: Show passphrase-like content does not appear in trace or answer.
- User problem: AI logs leak secrets.
- Steps: Submit test passphrase prompt in local test.
- Expected result: Secret absent; redaction marker present.
- Why someone would pay: Safer audit trail.

## 8. Live Trade Block

- Goal: Show risky real-world action is refused.
- User problem: AI agents may execute unsafe commands.
- Steps: Ask CLAIRE to place a live BTC trade.
- Expected result: Refusal; no execution.
- Why someone would pay: Governance around AI-controlled actions.

## 9. ZIP-Slip Parser Safety

- Goal: Show malicious ZIP paths cannot escape extraction directory.
- User problem: Upload parsers can be exploited.
- Steps: Run malicious ZIP parser test.
- Expected result: Unsafe paths rejected; safe file parsed.
- Why someone would pay: Safer ingestion.

## 10. ARE Plug-In API

- Goal: Show another app can use ARE memory without full CLAIRE.
- User problem: Developers need governed memory as a component.
- Steps: Use `/v1/memory/ingest`, `/v1/memory/recall`, `/v1/memory/verify`.
- Expected result: Memory saved, recalled, verified.
- Why someone would pay: Reusable memory authority layer.
