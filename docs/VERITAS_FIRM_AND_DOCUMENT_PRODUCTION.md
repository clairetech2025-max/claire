# Veritas Firm and Document Production

This document records the current state of firm identity and document production in Veritas Legal.

## What already exists

### Court and matter presets

`web/services/legal_intel.py` already contains:
- court profile presets
- filing templates
- a court-profile report helper
- a matter template / packet builder
- exhibit indexing
- anomaly detection
- billing estimation

### Production formats

Existing code can produce:
- Markdown packet output
- DOCX packet output
- PDF packet output

Implemented entry points:
- `/draft`
- `/export_packet`
- `/export_packet_docx`
- `/export_packet_pdf`

### Current strengths

- source citations are preserved in packet content
- matter and court profile metadata are surfaced
- exhibit indices are built from loaded records
- packet generation includes a sensitivity scan
- generated work is explicitly framed as review material, not filed work

## What is missing or incomplete

- persistent firm profile storage
- persistent staff directory
- role-based authority fields
- document responsibility fields such as prepared/reviewed/approved/signed/filed
- branded templates per office or court
- a governed finalization workflow that prevents unauthorized signing or filing claims
- a full attorney/paralegal/reviewer permissions system

## Current document-production judgment

The code can already create useful drafting packets. It is not yet a complete production system for a firm because the firm identity, staff authority, and finalization controls are not fully modeled as durable product primitives.
