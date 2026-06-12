# Original ARE Authority

Verified original ARE source path:

`/home/LuciusPrime/original_are.pyiginal_are.py/are.py`

## Core Record Format

```python
{"ts": int(time.time()), "sha": hashlib.sha256(text.encode()).hexdigest()[:10], "text": text[:8000]}
```

## Original ARE Behavior

- Append-only JSONL memory records.
- Timestamped memory item.
- Short hash/sha field.
- Preserved text field.
- `last_n(n)` chronological recall.
- External memory authority.
- The model reads the past but does not own it.

## Principle

The model does not own the past.

## Bridge Alignment

`original_are_bridge.py` preserves the same `{ts, sha, text}` format and reads recent records oldest-to-newest.

## Runtime Authority

`claire_runtime.py` defaults to original ARE when no SQLite test store is injected.

## Warning

Do not replace original ARE with vector search, SQLite, model memory, or Veritas logs. Those may exist as governed subsystems, but they are not the default CLAIRE memory authority.
