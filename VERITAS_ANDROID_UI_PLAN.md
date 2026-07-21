# Veritas Android UI Plan

## Product Position

Veritas mobile is a case-evidence workspace for non-technical users.

It should feel like:

- case folder;
- evidence notebook;
- source-linked search;
- guided review assistant.

It should not feel like:

- developer dashboard;
- terminal;
- database browser;
- AI lab demo;
- JSON inspector.

## Design Rules

### Mobile First

- Minimum body text: 16px.
- Main headings: 22-28px.
- Buttons: full-width, at least 48px tall.
- Inputs: full-width.
- No horizontal scrolling.
- No dense tables on first screen.
- No tiny monospace walls.
- Use cards and bottom navigation.

### One-Handed Use

Primary actions go near the lower half of the screen.

Use bottom navigation:

```text
Home | Case | Search | Ask | Reports
```

Use large stacked buttons on home/dashboard.

### Plain English

Use:

- Documents
- People
- Timeline
- Evidence
- Reports
- Ask Veritas
- Source
- Date found
- Related evidence

Avoid:

- parser output
- JSONL
- source_doc_id on normal screen
- ARE event SHA on normal screen
- endpoint
- trace payload
- ingestion vector
- deterministic core

## Information Architecture

```text
Home
  New Case
  Open Case
  Upload Evidence
  Search Evidence
  Build Timeline
  Generate Report
  Ask Veritas

Case
  Documents
  People
  Timeline
  Evidence
  Events
  Search
  Reports

Document
  Summary
  Date
  People
  Organizations
  Statutes
  Timeline links
  Related evidence
  Ask about this document

Search
  Natural language query
  Results
  Filters

Timeline
  Chronological events
  Event detail
  Supporting documents

Reports
  Evidence packet
  Timeline
  Witness list
  Document index
  Case summary

Ask
  Suggested prompts
  Chat
  Source-linked answers

Advanced
  Hashes
  Trace / Ledger
  Raw metadata
  Diagnostics
```

## Screen Components

### Primary Button

Use for major actions:

- New Case
- Upload Evidence
- Build Timeline
- Generate Report

Style:

- full width;
- high contrast;
- short label;
- optional icon.

### Section Card

Used on dashboard:

```text
[ Documents 12 > ]
```

Never nest cards inside cards.

### Evidence Result Card

```text
permit_notice.pdf
Mentions Sean James near March 15, 2013.

[ Open ]
```

### Source Link

Every answer should include simple source cards:

```text
Supported by
[ permit_notice.pdf > ]
```

Technical IDs hidden unless Advanced is opened.

## Data Display Rules

### Hashes

Default:

```text
Source verified
```

Advanced:

```text
SHA-256: abc123...
source_doc_id: src_...
ARE event SHA: ...
```

### Trace

Default:

```text
Answer based on 3 documents.
```

Advanced:

```text
Trace ID
ARE event SHA
Parser record
Metadata path
```

### Contradictions

Default:

```text
Possible contradiction found
```

Tap detail:

```text
Document A says date X.
Document B says date Y.
Review both before relying on this.
```

## Search UX

Search input placeholder:

```text
Ask about people, dates, rules, or contradictions.
```

Examples:

- Show every mention of Sean James.
- What happened in 2013?
- Find every reference to CCR 4331.
- Show contradictions.

Search results grouped by:

- Documents
- Timeline events
- People
- Possible contradictions

## Ask Veritas UX

Suggested prompts appear as tap chips:

```text
[ Strongest evidence? ]
[ Contradictions? ]
[ What happened before revocation? ]
[ Exhibits supporting retaliation? ]
```

Answer format:

```text
Short answer

Evidence supporting this
[ source card ]
[ source card ]

Limits
This is evidence organization, not legal advice.
```

## Advanced Menu

Advanced is available but never on the default path.

Location:

Top-right `...`

Sections:

- Source hashes
- Trace / ledger
- Raw metadata
- Diagnostics
- Export technical bundle

Warning:

```text
Advanced details are for technical review.
```

## MVP Implementation Order

### Step 1: Mobile Shell

- bottom nav;
- home screen;
- case dashboard;
- large buttons;
- hide developer controls.

### Step 2: Upload Flow

- file picker;
- upload progress;
- upload complete summary;
- error states.

### Step 3: Document View

- summary;
- dates;
- people;
- orgs;
- statutes;
- related timeline/evidence.

### Step 4: Search

- natural language input;
- result cards;
- source links.

### Step 5: Timeline

- chronological list;
- event detail;
- supporting documents.

### Step 6: Reports

- report type picker;
- generation status;
- saved report list.

### Step 7: Ask Veritas

- chat screen;
- suggested prompts;
- source-linked answers.

### Step 8: Advanced Menu

- hashes;
- trace;
- diagnostics;
- raw export.

## Acceptance Criteria

A first-time Android user can:

1. Create a case.
2. Upload a document.
3. See the document summary.
4. Search for a person/date/rule.
5. Build a timeline.
6. Generate a report.
7. Ask Veritas a question.

All without seeing:

- JSON;
- API names;
- Docker;
- Python;
- terminal commands;
- trace logs;
- hashes unless requested;
- internal configuration.

## Commercial Readiness Rule

If Steve cannot understand the screen in 30 seconds on his phone, the screen is not ready.
