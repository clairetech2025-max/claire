# Veritas Steve Acceptance Test

## 1. URL To Open On Phone

Open the CLAIRE/Veritas host in your Android browser and go to:

```text
http://<your-claire-host>/veritas-mobile
```

If testing on the VM directly through a local port, use the same host and port where `claire_gui.py` is running:

```text
http://<vm-host-or-ip>:<port>/veritas-mobile
```

Do not upload the full legal corpus for this acceptance test. Use one small controlled document first.

## 2. First Button To Tap

Tap:

```text
New Case
```

Then enter a short case name, for example:

```text
Mobile Test Case
```

Tap:

```text
Create Case
```

Expected result:

- The Case screen opens.
- You see the case name.
- You see large buttons for Upload Evidence and Ask Veritas.

## 3. Test Document To Use

Start with a small `.txt` file named:

```text
veritas_mobile_smoke_notice.txt
```

Use this safe synthetic text:

```text
On 2013-03-15 Sean James cited CCR 4331 in a Claire Systems notice.
Patrick Tuck reviewed the evidence before the permit was revoked.
```

Supported file types in this slice:

```text
TXT, MD, PY, PDF, DOCX, CSV, JSON, JSONL
```

Do not use photos or scanned image-only PDFs for the first acceptance test. OCR is not certified in the mobile workflow yet.

## 4. Upload And Expected Result

From the Case screen, tap:

```text
Upload Evidence
```

Choose the test file and tap:

```text
Start Upload
```

Expected result:

- The file shows as added.
- The result says a source record was created.
- You should see counts for:
  - dates found
  - people found
  - organizations found
  - rules found

Expected facts from the test file:

- Date: `2013-03-15`
- People: `Sean James`, `Patrick Tuck`
- Organization: `Claire Systems`
- Rule/statute: `CCR 4331`

## 5. Search Test

Tap bottom navigation:

```text
Search
```

Search:

```text
Show every mention of Sean James.
```

Expected result:

- At least one result appears.
- The result links back to the uploaded document.
- The snippet includes `Sean James`.

Then search:

```text
Find every reference to CCR 4331.
```

Expected result:

- At least one result appears.
- The snippet or document metadata includes `CCR 4331`.

## 6. Timeline Test

Tap:

```text
Build Timeline
```

Expected result:

- A timeline event appears for `2013-03-15`.
- The event shows source support.
- Tapping the source opens the document view.

## 7. Ask Veritas Test

Tap bottom navigation:

```text
Ask
```

Ask:

```text
What is my strongest evidence?
```

Expected result:

- Veritas answers from the active case only.
- The answer cites the uploaded document.
- The answer includes an attorney-review/legal-advice boundary.
- It does not pretend to have external legal authority.

## 8. Report Test

Tap bottom navigation:

```text
Reports
```

Tap:

```text
Document Index
```

Expected result:

- A report is saved.
- A preview appears.
- The preview includes the uploaded document and source reference.

## 9. How To Report Confusion Or Failure

Report the exact step where it failed:

- Page URL
- Button tapped
- File type uploaded
- Visible error text
- Whether the phone keyboard covered the button
- Whether any text was too small or clipped
- Whether you saw sideways scrolling
- Screenshot if possible

## Pass Condition

This acceptance test passes when Steve can, from his Android phone:

1. Open `/veritas-mobile`.
2. Create a case.
3. Upload the test document.
4. See extracted facts.
5. Search for `Sean James` or `CCR 4331`.
6. Ask one case question.
7. See source-linked support.
8. Generate the Document Index report.

No terminal or developer explanation should be required.
