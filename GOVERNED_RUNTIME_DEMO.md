# Governed Runtime Demo

This demo proves the sentence:

`Memory-bearing AI agents need identity, authority, recall control, tool control, secret protection, validation, and traceability before they act.`

## Product

Handshake Broker by Claire Systems is the demo identity-and-authority broker for CLAIRE.

It issues short-lived authority capsules bound to:

- user id
- role
- session id
- lane
- request hash
- allowed memory scopes
- allowed tools
- risk level
- purpose
- issued and expiry time

## Underlying Protocol

C3RP provides request orientation and lane routing before memory recall and tool access.

## Gyro Rule

CLAIRE orients before generation across these axes:

- intent
- lane
- authority
- risk
- memory eligibility
- source provenance
- continuity
- output boundary

No model generation occurs when the Gyro bearing is unstable. The runtime records the bearing in Trace and routes to Loopback instead.

## Loopback Rule

Loopback stops generic, drifting, or unsupported answers.

Triggers include:

- low confidence
- unclear lane
- missing source authority
- memory conflict
- high-risk legal, financial, medical, or technical claims
- answer drift from the original prompt
- generic filler response
- inability to explain why the answer follows from the input

Loopback re-anchors to the original user request and either asks one clarifying question, gives a narrow bounded answer, or refuses the action.

## Diode Rule

Authority flows forward as a signed capsule.

Secrets do not flow backward into:

- chat response
- model prompt
- memory
- trace
- logs
- debug output

Secret-like text is replaced with `[REDACTED_BY_DIODE]`.

## ARE Rule

ARE remains the chronological memory authority.

The model does not own the past. Trace logs, Veritas logs, CourtListener data, and model context are not CLAIRE memory authorities.

ARE recall is scoped by:

- lane
- user id
- authority capsule id
- allowed memory scopes
- relevance filter

Old memory records without a scope default to `PUBLIC`.

## Sentinel Rule

Sentinel validates the response before final output. Normal answers must not expose lane, risk, trace id, internal gates, answer basis, validation notes, or raw memory records.

## Trace Rule

Trace records decisions, hashes, capsule id, scopes, tools, and validation metadata.

Trace must not record secrets, raw passphrases, API keys, bearer tokens, private keys, or raw authority tokens.

Trace also records:

- Gyro bearing
- Loopback trigger state
- Loopback reason
- Answer mode: `direct`, `bounded`, `clarify`, or `refuse`

## Run Commands

```bash
python3 -m py_compile handshake_broker.py diode_protocol.py authority_capsule.py claire_runtime.py
python3 demo_governed_runtime.py
python3 test_governed_runtime.py
python3 validate_claire_runtime.py
```

If pytest is installed:

```bash
python3 -m pytest -q
```

If pytest is unavailable, `validate_claire_runtime.py` runs the governed runtime scenarios directly.

## Expected Demo Output

`demo_governed_runtime.py` prints PASS/FAIL for:

1. Guest general question.
2. Guest private memory denial.
3. Trusted owner private memory recall.
4. Horse hoof routing.
5. Veritas authority gate.
6. Live BTC trade block.
7. Passphrase redaction.
8. Court certainty caution.
9. NVIDIA engineer explanation with no internal gate leak.
10. Debug internals blocked for guest.

Expected final line:

```text
Governed runtime demo result: 10/10 PASS
```

## Current Limitations

- Trusted device mode is demo metadata, not production identity.
- HMAC capsules are demo-safe proof objects, not a replacement for hardware-backed identity.
- Live trading step-up is intentionally not implemented in normal chat.
- Legal filing automation is intentionally not implemented in normal chat.
- Policy loading is currently code-backed with `claire_policy.yaml` as the readable contract.

## Production Note

Production Handshake Broker should use WebAuthn/FIDO2/passkeys or hardware-backed device signing.

The production signer should be backed by managed secret storage or hardware security modules, not an ephemeral demo key.
