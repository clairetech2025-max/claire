# Veritas Legal

Veritas Legal is a local evidence organization prototype.

It does not provide legal advice. It does not file anything. It does not contact courts. It organizes local evidence so a human can review source files, dates, entities, hashes, trace records, and timelines.

## What It Does

- reads local TXT, MD, LOG, CSV, JSON, JSONL, DOCX, and optional PDF files
- blocks very large files in the prototype parser
- hashes source files
- redacts secret-like strings before evidence records are written
- extracts simple date references
- extracts simple possible names/entities
- writes a source manifest
- writes evidence records as JSONL
- writes a trace log
- builds a basic timeline
- lets Claire explain the run in plain English

## Run A Demo

```bash
tmp=$(mktemp -d)
printf 'On 2024-05-01 Steven Roth met Claire Systems about evidence. The regulation issue was enforcement beyond the text.\n' > "$tmp/sample.txt"
python3 -m veritas_legal --state-dir "$tmp/state" --claire-explains "$tmp/sample.txt"
```

## Run On A Folder

```bash
python3 -m veritas_legal --state-dir ./veritas_legal_state --claire-explains /path/to/evidence_folder
```

## Output Files

Inside the selected state directory:

- `source_manifest.jsonl`
- `evidence_records.jsonl`
- `trace.jsonl`

## Test

```bash
python3 -m unittest tests.test_veritas_legal
```

## Boundary

This is evidence organization software only. A qualified attorney must verify legal arguments, citations, deadlines, procedural rules, and filing strategy.
