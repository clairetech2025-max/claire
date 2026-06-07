# Claire Writer Mode

Claire Writer Mode is a separate local writing workspace. It sits beside the public Claire runtime and does not change Claire services, routes, memory, GUI, ARE, Sentinel, Gyro, Diode, or Go behavior.

## Purpose

Use Writer Mode to capture raw story material, organize it into lanes, generate local markdown drafts, create partner-facing briefs, and export local PDFs for human review.

## Safety Rules

- Raw transcripts stay separate from drafts.
- Do not invent facts.
- Do not add people, dates, places, or events unless present in source material.
- Preserve Steve's voice.
- Every draft is a draft for human review.
- Nothing is published automatically.
- Nothing is emailed automatically.
- Nothing is uploaded automatically.
- PDFs are local files only.

## Commands

```bash
python writer_mode/claire_writer.py init
python writer_mode/claire_writer.py status
python writer_mode/claire_writer.py lanes
python writer_mode/claire_writer.py capture --lane claire_origin
python writer_mode/claire_writer.py import-text path/to/file.txt --lane network_engineer_foundation
python writer_mode/claire_writer.py draft --lane network_engineer_foundation --title "From T1 Lines to Claire"
python writer_mode/claire_writer.py brief --topic "ARE Gyro Diode Sentinel" --title "Claire Architecture Brief"
python writer_mode/claire_writer.py pdf writer_mode/briefs/example.md
python writer_mode/claire_writer.py list-drafts
python writer_mode/claire_writer.py list-pdfs
```

## Providers

Default provider is local scaffold mode.

```bash
export CLAIRE_WRITER_PROVIDER=local_scaffold
export CLAIRE_WRITER_MODEL=
export CLAIRE_WRITER_API_KEY=
export CLAIRE_WRITER_URL=
```

Supported provider names:

- `local_scaffold`
- `openai`
- `gemini`
- `claude`
- `local_http`
- `azure_headmaster`

No API keys are hard-coded.

## Output Locations

- Raw transcripts: `writer_mode/transcripts/`
- Draft chapters: `writer_mode/drafts/`
- Briefs: `writer_mode/briefs/`
- PDFs: `writer_mode/pdfs/`
- Logs: `writer_mode/logs/writer_log.jsonl`

## Craft Standard

Writer Mode should aim for serious prose: direct sentences, concrete detail, pressure, clean rhythm, strong pacing, and technical clarity. It should learn from the craft values associated with great fiction and technical writers without copying or imitating any living or dead author's protected expression.
