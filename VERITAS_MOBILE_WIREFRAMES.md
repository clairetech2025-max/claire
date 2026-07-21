# Veritas Mobile Wireframes

Design target: modern Android phone, one-handed use, no developer knowledge.

Primary rule: first screen shows useful legal/evidence actions, not system internals.

## Global Mobile Shell

### Top Bar

```text
Veritas
[current case name or "No case open"]
```

Visible controls:

- Back
- Case switcher
- Advanced menu behind `...`

Hidden by default:

- JSON
- trace
- hashes
- API paths
- diagnostics
- Python/Docker/Git/configuration

### Bottom Navigation

```text
Home | Case | Search | Ask | Reports
```

Thumb-accessible, always visible except during full-screen upload progress.

## Home Screen

Purpose: let a first-time user start useful work immediately.

Wireframe:

```text
Veritas
Legal case intelligence

[ New Case          ]
[ Open Case         ]
[ Upload Evidence   ]
[ Search Evidence   ]
[ Build Timeline    ]
[ Generate Report   ]
[ Ask Veritas       ]

Recent Cases
[ Smith v Agency        > ]
[ Permit Revocation     > ]
```

Button behavior:

- `New Case`: creates a case with simple name prompt.
- `Open Case`: shows recent and saved cases.
- `Upload Evidence`: opens file picker and assigns upload to active/new case.
- `Search Evidence`: opens natural language search.
- `Build Timeline`: opens one-tap timeline builder.
- `Generate Report`: opens report choices.
- `Ask Veritas`: opens chat.

No dashboard metrics on first screen. No dense panels.

## New Case Screen

```text
New Case

Case name
[_____________________]

Optional note
[_____________________]

[ Create Case ]
```

After create:

```text
Case created

[ Upload Evidence ]
[ Ask Veritas what to upload ]
```

## Open Case Screen

```text
Open Case

[ Search cases... ]

[ Smith v Agency        ]
  14 docs | updated today

[ Permit Revocation     ]
  38 docs | updated July 10
```

Tap a case to open dashboard.

## Upload Evidence Screen

```text
Upload Evidence

Case: Smith v Agency

[ Choose Files ]
[ Choose Folder ]
[ Take Photo ]

Supported:
PDF, DOCX, TXT, CSV, JSON, images when OCR is available

[ Start Upload ]
```

During processing:

```text
Processing evidence

3 of 12 files complete

Current:
permit_notice.pdf

[ Keep working in case ]
```

After upload:

```text
Upload complete

12 documents added
12 source hashes created
8 dates found
15 people/orgs found

[ View Documents ]
[ Build Timeline ]
[ Ask Veritas ]
```

## Case Dashboard

Purpose: one-handed case control center.

Wireframe:

```text
Smith v Agency
Evidence workspace

[ Upload Evidence ]

[ Documents  12 > ]
[ People     15 > ]
[ Timeline    8 > ]
[ Evidence   12 > ]
[ Events      8 > ]
[ Search        > ]
[ Reports       > ]

Recent Activity
- permit_notice.pdf added
- 2013 event found
- 2 possible contradictions
```

All cards are full-width tap targets.

## Documents Screen

```text
Documents

[ Search documents... ]

[ permit_notice.pdf     > ]
  4 dates | 3 people

[ hearing_notes.docx    > ]
  2 dates | 5 people

[ email_export.txt      > ]
  12 dates | 8 people
```

Sort options hidden behind simple menu:

- Newest
- Oldest
- Most dates
- Most people

## Document View

Default view hides technical detail.

```text
permit_notice.pdf

Summary
This document appears to describe a permit notice and related dates.

Date
March 15, 2013

People
Sean James
Steven Roth

Organizations
California State Parks

Statutes / Rules
CCR 4331

Timeline Links
[ March 15, 2013 notice event > ]

Related Evidence
[ hearing_notes.docx > ]
[ email_export.txt   > ]

[ Ask about this document ]
[ Add to Report ]
```

Technical detail collapsed:

```text
[ Show Technical Details ]

SHA-256
source_doc_id
ARE event SHA
Parser details
Trace file
```

## People Screen

```text
People

[ Search people... ]

[ Sean James      > ]
  mentioned in 7 documents

[ Steven Roth     > ]
  mentioned in 12 documents
```

Person detail:

```text
Sean James

Mentions
7 documents
4 timeline events

[ View documents ]
[ View timeline events ]
[ Ask about this person ]
```

## Evidence Screen

```text
Evidence

[ Strongest Evidence ]
[ Missing Proof ]
[ Contradictions ]
[ Source Index ]

Recent Evidence
[ permit_notice.pdf > ]
[ hearing_notes.docx > ]
```

## Search Screen

Natural language first.

```text
Search Evidence

[ Show every mention of Sean James. ]

Try:
"What happened in 2013?"
"Find every reference to CCR 4331."
"Show contradictions."

[ Search ]
```

Results:

```text
Results for Sean James

[ permit_notice.pdf > ]
  Sean James appears near the permit notice date.

[ hearing_notes.docx > ]
  Sean James appears in hearing notes.

[ View as Timeline ]
[ Ask Veritas about results ]
```

## Timeline Screen

```text
Timeline

[ Build / Refresh Timeline ]

2013

Mar 15
[ Permit notice event > ]

Apr 02
[ Hearing note event > ]

2014

Jan 09
[ Follow-up letter > ]
```

Timeline event detail:

```text
Permit notice event
March 15, 2013

What happened
Permit notice appears in uploaded evidence.

Supporting documents
[ permit_notice.pdf > ]

People
Sean James

Source citations
permit_notice.pdf
Page 1 if available

[ Ask about this event ]
[ Add to Report ]
```

## Reports Screen

```text
Reports

Generate:

[ Evidence Packet ]
[ Timeline ]
[ Witness List ]
[ Document Index ]
[ Case Summary ]

Saved Reports
[ Case Summary - Today > ]
```

Report progress:

```text
Generating Evidence Packet

Including:
Documents
Timeline
Source citations
Redaction notice

[ Done ]
```

## Ask Veritas Screen

```text
Ask Veritas

Ask about this case.

[ What is my strongest evidence?      ]
[ What documents contradict each other?]
[ What happened before the permit was revoked?]
[ Which exhibits support retaliation? ]

[ Type your question...              ]
[ Send ]
```

Answer card:

```text
Veritas

Your strongest evidence appears to be...

Supported by:
[ permit_notice.pdf > ]
[ hearing_notes.docx > ]

Limits:
This is evidence organization, not legal advice.

[ Add answer to report ]
[ Show sources ]
```

## Advanced Menu

Hidden behind `...`.

```text
Advanced

[ Technical Details ]
[ Source Hashes ]
[ Trace / Ledger ]
[ Export Raw Metadata ]
[ Diagnostics ]
```

Advanced is not shown during normal first-time use.
