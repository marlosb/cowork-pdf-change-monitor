# Deploy as a Cowork skill

> ⚠️ Non-production sample for testing only. No support. See the [README](../README.md).

Time: ~10 minutes. No Azure resources needed. Python runs inside the Cowork session.

## 1. Install the skill
1. Open OneDrive → `Documents/Cowork/skills/`.
2. Upload the folder `skills/pdf-change-monitor/` from this repository so you get:
   ```
   Documents/Cowork/skills/pdf-change-monitor/SKILL.md
   Documents/Cowork/skills/pdf-change-monitor/scripts/pdf_diff.py
   Documents/Cowork/skills/pdf-change-monitor/references/config.json
   Documents/Cowork/skills/pdf-change-monitor/references/summary-prompt.md
   Documents/Cowork/skills/pdf-change-monitor/references/tuning.md
   ```
   (Alternative: ask Cowork "install the pdf-change-monitor skill from my output folder" – it publishes the folder for you after an approval card.)
3. Start a new Cowork session. Check with: "show my skills" – `pdf-change-monitor` should be listed.

## 2. Create the baseline (once)
Attach last month's PDF and say:
> Create a baseline for this PDF as **tax-manual** using the PDF change monitor.

The skill saves `Documents/Cowork/pdf-monitor/tax-manual/latest.snap.json.gz`. If it warns
"Few headings detected", tune the heading pattern (step 4).

## 3. Monthly check (manual test)
Attach the new PDF and say:
> Check this new edition of tax-manual for changes.

You get: a verdict, the counts table, the top changes with section/page citations and a
file `tax-manual_changes_<date>.md` (AI summary + full deterministic report). The baseline
advances automatically. To compare two PDFs ad hoc, attach both and say "compare these two editions".

## 4. Tune for your manual (recommended before going live)
Attach two real editions and say:
> Run the PDF change monitor on these two editions and show me the raw stats and warnings.

If headings or noise are wrong, copy `references/config.json` to
`Documents/Cowork/pdf-monitor/tax-manual/config.json` and edit it (see `tuning.md`).
The per-document config always wins over the default.

## 5. Automate
Ask Cowork, in a session:
> Every time an email from <publisher address> with a PDF attachment arrives, run the pdf-change-monitor skill for tax-manual and email me the summary with the report attached.

or, if the PDF is dropped in a folder on a fixed day:
> On the 5th of every month at 09:00, run the pdf-change-monitor skill for tax-manual on the newest PDF in <folder> and email me the result.

Cowork creates the event trigger / scheduled task. **Test once:** forward a past edition
email to yourself and confirm the run finds the attachment. If the triggered run cannot read
the attachment, keep the monthly reminder and attach the PDF manually (step 3).

## Limits
- One extraction of 1,200 pages ≈ 30–70 s in the session.
- Baseline and reports live in your OneDrive Cowork folder; nothing leaves your tenant.
