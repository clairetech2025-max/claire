# Veritas Parser

Veritas Parser is the Claire evidence-intake layer.

It converts local files, folders, and ZIP archives into JSONL chunk records with source lineage and integrity hashes. Those records can then feed ARE recall, trace generation, or buyer-facing evidence reports.

## What It Does

- parses common text and document formats
- optionally extracts PDF, DOCX, ODT, image OCR, audio, and video text when dependencies are installed
- chunks extracted text into memory-safe records
- writes JSONL records with provenance metadata
- records chunk hashes and source file hashes

## Why It Matters

Veritas Parser is not the fastest ARE core. It is the intake/refinery layer before recall.

The practical flow is:

```text
Folder / ZIP / PDF / DOCX
  -> Veritas Parser
  -> chunked evidence records
  -> integrity hashes
  -> ARE recall
  -> traceable Claire response
```

## Commands

Run through the Veritas name:

```bash
venv/bin/python Veritas_parser.py /path/to/files --output-jsonl data/veritas_parser_output.jsonl
```

Run through the Claire parser name:

```bash
venv/bin/python claire_parser.py /path/to/files --output-jsonl data/parser_output.jsonl
```

Clear the output file before a fresh parse:

```bash
venv/bin/python Veritas_parser.py /path/to/files --output-jsonl data/veritas_parser_output.jsonl --clear-output
```

Disable heavy optional extraction:

```bash
venv/bin/python Veritas_parser.py /path/to/files --disable-ocr --disable-media
```

## GitHub Positioning

Use public-safe wording:

> Veritas Parser converts local evidence folders into traceable JSONL memory records for Claire/ARE recall.

Avoid implying that the parser itself proves benchmark speed, legal correctness, complete compliance, or autonomous decision authority.
