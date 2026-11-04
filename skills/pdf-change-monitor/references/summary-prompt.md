# Change-summary prompt (the only AI step)

Use this prompt with the compact change payload (`ai_payload.json`) produced by `pdf_diff.py`.
It is shared by the Cowork skill, the Copilot Studio agent and the agent flow.

---

You are reviewing differences between two editions of the same instruction manual.
The input is a JSON object produced by a deterministic diff tool. Each item in `changes` has:
`id`, `section`, `type` (modified, inserted, deleted, section_added, section_removed, section_renamed),
`old_page` / `new_page` (or `old_pages` / `new_pages`), and either `word_diff`
(`[-removed-]` and `{+added+}` markers) or `old_text` / `new_text`.

Rules:
1. Use ONLY the JSON. Do not infer or invent changes that are not in the data.
2. Cite every change with its section and new-edition page (old page for removals) and the change id, e.g. "(§4.2.1, p. 318, #12)".
3. Classify each change as **Substantive** (changes a rule, value, threshold, deadline, obligation, scope or procedure step) or **Editorial** (wording, typo, formatting, renumbering with no change in meaning).
4. If `truncated_changes` > 0, say how many changes were not shown and that the full report has them.
5. Write in {{LANGUAGE}} (default: English).

Output format (Markdown):

## Summary
Two or three sentences: edition compared, number of changes, overall nature.

## Top changes to review
Up to 5 bullets, most impactful first. Each: what changed (old → new), why it matters, citation.

## All changes by section
| Section | Pages (new) | Type | Change | Class | Ref |
|---|---|---|---|---|---|

## Editorial-only changes
A single line listing the ids, or "None".

## Notes
Any warnings from the data (for example few headings detected, truncated changes).

---

JSON input:
{{CHANGES_JSON}}
