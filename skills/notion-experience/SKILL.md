---
name: notion-experience
description: Extract reusable trading lessons from synced Notion notes.
stage: m2
---

Use this skill when analyzing notes imported from Notion.

Rules:
- Preserve evidence from the original note.
- Separate facts, interpretation, and reusable lessons.
- Extract conditions that would make the lesson valid or invalid.
- Do not convert a lesson into an unconditional buy or sell instruction.

Output fields:
- theme
- lesson
- evidence
- validation_condition
- invalid_condition
- confidence
