# Tuning the comparison for your manual

Run the script on two real editions and adjust `config.json` until the report shows only real changes.

| Symptom | Fix |
|---|---|
| Warning "Few headings detected" or one giant section | Change `heading_regex` to match how the manual numbers headings (e.g. `^Art\\.\\s*\\d+` for articles, `^[A-Z]\\.\\d+` for "A.1"). |
| Every page shows a change in a header/footer | Add the pattern to `noise_regexes` (full-line match) or lower `repeat_line_threshold` (e.g. 0.3). |
| A date or version stamp changes every month | Add a regex to `strip_regexes` (removed from inside lines). |
| Tables produce noisy diffs | Set `"unit": "line"` for this document, or extract tables separately. |
| Renumbering creates many add/remove pairs | Expected when numbers shift and text also changed; renames with identical bodies are detected automatically. |
| AI payload too large | Lower `ai_max_chars_per_change` or `ai_max_total_chars`; the full report always keeps everything. |

Test quickly: `python3 pdf_diff.py snapshot manual.pdf -o test.snap.json.gz --config config.json` prints the page and section count.
