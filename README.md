# Cowork PDF Change Monitor

> [!WARNING]
> **NON-PRODUCTION CODE — FOR TESTING ONLY — NO SUPPORT.**
> This is a personal sample/prototype. It is provided "AS IS", without warranty of any kind
> (see [LICENSE](LICENSE)). It has not been security-reviewed or hardened, is not an official
> product of any company, and no support, maintenance or response to issues is offered
> (see [SUPPORT.md](SUPPORT.md)). Always verify results against the source documents before
> acting on them. Do not use it with confidential documents unless your organization's
> policies allow it.

A **Cowork skill** that detects whether a large PDF manual (tested with 1,200 pages) changed
between monthly editions, **locates every change by section and page**, and uses AI **only**
to summarize the final, compact change list.

## Why
Publishers often reissue long instruction manuals without saying what changed. Reading 1,200
pages every month is not practical, and sending both editions to an AI model is expensive and
hard to audit. This skill does all detection with deterministic Python and gives the AI only
the differences.

## How it works
```
new PDF ─► extract text per page (PyMuPDF if installed, else pypdf)
        ─► remove noise (running headers/footers, page numbers, date stamps)
        ─► re-flow lines into sentences (one inserted word does not shift every line)
        ─► split into sections at headings ─► SHA-256 per section
        ─► same fingerprint as baseline?  ── yes ─► "No changes" (exit 0, no AI call)
                                           └─ no ─► diff only changed sections
                                                   ─► report.json · report.md · ai_payload.json
                                                   ─► AI summary (the only AI step)
```
- Detects inserted / deleted / modified text, added / removed sections and renamed headings.
- Ignores cosmetic-only changes (case, spacing, punctuation) by default.
- Keeps a compact snapshot (`.snap.json.gz`) as the baseline, so each month only the new PDF is processed.

## Repository layout
```
skills/pdf-change-monitor/
  SKILL.md                    Cowork skill definition (workflow + guardrails)
  scripts/pdf_diff.py         Deterministic engine (snapshot / compare / reports)
  references/config.json      Heading regex, noise filters, AI payload limits
  references/summary-prompt.md  The single AI prompt
  references/tuning.md        How to tune for your manual
docs/DEPLOY-COWORK.md         Step-by-step install and automation
tests/make_sample_pdfs.py     Regenerates sample editions (needs reportlab)
tests/samples/                v1.pdf, v1b.pdf (same content, new date), v2.pdf (6 planted changes)
tests/run_tests.py            Smoke tests
```

## Install in Cowork
1. Copy `skills/pdf-change-monitor/` to your OneDrive at `Documents/Cowork/skills/pdf-change-monitor/`.
2. Start a new Cowork session and confirm with "show my skills".
3. Attach last month's PDF: *"Create a baseline for this PDF as tax-manual."*
4. Attach the new PDF: *"Check this new edition of tax-manual for changes."*

Full guide, tuning and automation: [docs/DEPLOY-COWORK.md](docs/DEPLOY-COWORK.md).

## Use the engine standalone (no Cowork)
```bash
pip install pypdf
python skills/pdf-change-monitor/scripts/pdf_diff.py snapshot old.pdf -o old.snap.json.gz
python skills/pdf-change-monitor/scripts/pdf_diff.py compare old.snap.json.gz new.pdf \
       -o report.json --md report.md --ai-payload ai_payload.json
echo $?   # 0 = no changes, 1 = changes found, 2 = error
```
Then give `ai_payload.json` to any AI model with `references/summary-prompt.md`.

## Test
```bash
pip install pypdf
python tests/run_tests.py      # expects: OK - all tests passed
```
| Test | Result in our runs |
|---|---|
| Same content, new print date in header | No changes (exit 0) |
| 6 planted changes + 1 cosmetic-only change | All 6 found with correct section and page; cosmetic ignored |
| 1,202-page document, pypdf | ≈35 s per edition |

## Known limitations
- Heading detection is regex-based; tune `heading_regex` for your manual (a warning appears when few headings are found).
- Tables, images and scanned (image-only) PDFs are not compared; scanned PDFs need OCR first.
- When a heading is renumbered **and** its text changes, it is reported as one section removed + one added.
- Page numbers of changes are the page where the sentence starts.
- PyMuPDF is optional and faster but AGPL-licensed; the default dependency is pypdf (BSD).

## License
[MIT](LICENSE) — provided "AS IS", without warranty. No support (see [SUPPORT.md](SUPPORT.md)).
