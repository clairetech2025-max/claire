# Veritas User Flow

Goal: Steve can pick up an Android phone, upload documents, and understand how to use Veritas without explanation.

## First-Time Flow

### 1. Open Veritas

User sees only large action buttons:

1. New Case
2. Open Case
3. Upload Evidence
4. Search Evidence
5. Build Timeline
6. Generate Report
7. Ask Veritas

Expected user decision:

- If no case exists, tap `New Case`.
- If a case exists, tap `Open Case`.
- If unsure, tap `Upload Evidence`; app prompts for case selection.

### 2. Create Case

User taps:

```text
New Case
```

User enters:

```text
Case name: Permit Revocation
```

System creates local case workspace.

Next screen offers:

```text
[ Upload Evidence ]
[ Ask Veritas what to upload ]
```

### 3. Upload Evidence

User taps:

```text
Upload Evidence
```

User chooses files from phone storage, cloud-synced folder, or camera/photo import.

System performs:

- save local copy;
- identify file;
- extract text when supported;
- calculate source hash;
- assign source document ID;
- extract dates;
- extract people/organizations;
- create evidence record;
- create provenance metadata;
- link evidence to case.

User sees plain progress:

```text
Processing evidence
3 of 12 files complete
```

User never sees JSON, APIs, Python, Docker, or internal trace unless Advanced is opened.

### 4. Upload Complete

System shows:

```text
12 documents added
12 source hashes created
8 dates found
15 people/orgs found
```

Primary next actions:

- View Documents
- Build Timeline
- Ask Veritas

### 5. Case Dashboard

User lands on:

```text
Documents
People
Timeline
Evidence
Events
Search
Reports
```

Every section is one tap.

## Core Workflows

## Workflow A: Understand Uploaded Documents

1. Open case.
2. Tap `Documents`.
3. Tap document.
4. Read summary, dates, people, organizations, statutes.
5. Tap `Ask about this document`.

Expected result:

User understands what the document is, who appears in it, what dates matter, and where it fits.

## Workflow B: Search Evidence

1. Open case.
2. Tap `Search`.
3. Type natural question:

```text
Show every mention of Sean James.
```

4. Tap result.

Expected result:

Search returns matching documents and snippets with source links.

No Boolean search syntax required.

## Workflow C: Build Timeline

1. Open case.
2. Tap `Build Timeline`.
3. Tap `Build / Refresh Timeline`.
4. Scroll chronological events.
5. Tap event for supporting documents.

Expected result:

User sees case events in order and can open source documents behind each event.

## Workflow D: Generate Report

1. Open case.
2. Tap `Generate Report`.
3. Pick report type:

- Evidence Packet
- Timeline
- Witness List
- Document Index
- Case Summary

4. Tap `Generate`.
5. Open saved report.

Expected result:

User receives a reviewable report with source citations and legal-advice boundary.

## Workflow E: Ask Veritas

1. Open case.
2. Tap `Ask Veritas`.
3. Use suggested prompt or type one:

```text
What is my strongest evidence?
```

4. Read answer.
5. Tap source documents.

Expected result:

Veritas answers from case evidence and shows support documents.

## Error Flows

## Unsupported File

Message:

```text
This file type is not supported yet.
Try PDF, DOCX, TXT, CSV, JSON, or JSONL.
```

Action:

```text
[ Choose another file ]
```

## No Text Found

Message:

```text
I could not read text from this file.
It may be scanned or an image.
```

Action:

```text
[ Keep file as evidence ]
[ Try OCR if available ]
```

## No Timeline Dates Found

Message:

```text
No clear dates were found yet.
You can still search and review documents.
```

Action:

```text
[ Search Evidence ]
[ Ask Veritas ]
```

## No Search Results

Message:

```text
No matching evidence found.
Try a person, date, rule number, or exact phrase.
```

Suggestions:

- Sean James
- 2013
- CCR 4331
- permit revoked

## User Success Definition

Within five minutes, a first-time user should be able to:

1. Create or open a case.
2. Upload at least one document.
3. See extracted document facts.
4. Search for a person/date/rule.
5. Generate a basic report or timeline.
6. Ask Veritas one case question and see source-linked support.
