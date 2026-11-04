#!/usr/bin/env python3
"""
NON-PRODUCTION SAMPLE CODE - FOR TESTING ONLY - NO SUPPORT. Provided "AS IS" under the MIT License.

pdf_diff.py - deterministic change detection for large, versioned PDF manuals.

No AI is used here. The engine:
  1. extracts text page by page (PyMuPDF if installed, else pypdf),
  2. removes noise (running headers/footers, page numbers, configurable patterns),
  3. splits the text into sections at headings,
  4. fingerprints every section (SHA-256),
  5. diffs only the sections whose fingerprint changed,
  6. writes a structured report (JSON), a readable report (Markdown) and a
     compact payload sized for an AI summarizer.

Commands
  snapshot <pdf> -o snap.json.gz [--config cfg.json]
  compare  <old.pdf|old.snap.json.gz> <new.pdf|new.snap.json.gz>
           [-o report.json] [--md report.md] [--ai-payload ai.json]
           [--save-snapshot new.snap.json.gz] [--config cfg.json]

Exit codes: 0 = no changes, 1 = changes found, 2 = error.
"""
from __future__ import annotations

import argparse, datetime as dt, difflib, gzip, hashlib, json, os, re, sys, unicodedata
from collections import Counter

ENGINE_VERSION = "1.0.0"

DEFAULT_CONFIG = {
    # A line that matches this starts a new section. Default: numbered headings
    # such as "4", "4.2", "4.2.1 Title", "Chapter 3", "Section 12", "Annex A".
    "heading_regex": r"^((\d{1,3}(\.\d{1,3}){0,5}\.?)|(chapter|section|cap[ií]tulo|se[cç][aã]o|annex|anexo|appendix|ap[eê]ndice)\s+[\dA-Z]+)\s+\S",
    "heading_max_len": 150,
    # Lines that appear on more than this share of pages are treated as headers/footers.
    "repeat_line_threshold": 0.5,
    # Lines that are always noise (full-line match, case-insensitive).
    "noise_regexes": [
        r"(page|p[aá]gina|p\.)?\s*\d{1,4}(\s*(of|de|/)\s*\d{1,4})?",
        r"[ivxlcdm]{1,6}",
    ],
    # Text fragments removed from every line before comparing (e.g. print dates).
    "strip_regexes": [],
    # Ignore changes that only differ in case, spacing or punctuation.
    "ignore_cosmetic": True,
    # Comparison unit: "sentence" (robust to re-flowed text) or "line".
    "unit": "sentence",
    # Size limits for the AI payload.
    "ai_max_chars_per_change": 1500,
    "ai_max_total_chars": 60000,
}


# ----------------------------------------------------------------- extraction
def _pages_text(pdf_path: str) -> list[str]:
    try:
        import fitz  # PyMuPDF (fast; AGPL/commercial licence)
        with fitz.open(pdf_path) as doc:
            return [p.get_text("text") for p in doc]
    except ImportError:
        pass
    try:
        from pypdf import PdfReader  # BSD licence, slower
    except ImportError:
        sys.exit("ERROR: install PyMuPDF or pypdf")
    reader = PdfReader(pdf_path)
    return [(p.extract_text() or "") for p in reader.pages]


def _clean(line: str, strip_res) -> str:
    line = unicodedata.normalize("NFKC", line)
    line = line.replace("\u00ad", "")  # soft hyphen
    for rx in strip_res:
        line = rx.sub("", line)
    return re.sub(r"\s+", " ", line).strip()


_SENT = re.compile(r"(?<=[.!?;:])\s+(?=[\"'(\[]?[A-Z0-9\u00C0-\u00DD])")
_BULLET = re.compile(r"^([\u2022\u25aa\u25cf\u2013\-*]|\(?[a-z0-9]{1,3}[.)])\s+")


def _units(raw, cfg):
    """Re-flow wrapped lines into sentences so a changed word does not shift
    every following line break. Each sentence keeps the page it starts on.
    Returns [[page, sentence], ...]."""
    if cfg.get("unit") == "line":
        return [[p, t] for p, t in raw]
    out, buf, marks = [], "", []          # marks: (char_offset, page)

    def flush():
        nonlocal buf, marks
        pos = 0
        for part in _SENT.split(buf):
            start = buf.find(part, pos)
            pos = start + len(part)
            pg = [p for off, p in marks if off <= start]
            if part.strip():
                out.append([pg[-1] if pg else marks[0][1], part.strip()])
        buf, marks = "", []

    for p, line in raw:
        if _BULLET.match(line) and buf:
            flush()
        if buf.endswith("-") and line[:1].islower():
            marks.append((len(buf) - 1, p)); buf = buf[:-1] + line
        else:
            if buf:
                buf += " "
            marks.append((len(buf), p)); buf += line
        if len(buf) > 20000:
            flush()
    if buf:
        flush()
    return out


def _cosmetic_key(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.lower())


def build_snapshot(pdf_path: str, cfg: dict) -> dict:
    strip_res = [re.compile(r, re.I) for r in cfg["strip_regexes"]]
    noise_res = [re.compile(r"^(?:%s)$" % r, re.I) for r in cfg["noise_regexes"]]
    heading_re = re.compile(cfg["heading_regex"], re.I)

    raw_pages = _pages_text(pdf_path)
    pages = [[c for c in (_clean(l, strip_res) for l in p.splitlines()) if c] for p in raw_pages]

    # Running headers/footers: lines in the top/bottom 3 of a page that repeat on many
    # pages (digits masked so "Page 3" == "Page 4"). Headings are never treated as noise.
    mask = lambda s: re.sub(r"\d+", "#", s)
    is_heading = lambda l: bool(heading_re.match(l)) and len(l) <= cfg["heading_max_len"]
    edge = lambda p: p[:3] + p[-3:] if len(p) > 6 else p
    freq = Counter(m for p in pages for m in {mask(l) for l in edge(p) if not is_heading(l)})
    limit = max(3, len(pages) * cfg["repeat_line_threshold"])
    repeated = {m for m, c in freq.items() if c > limit}

    sections, counts = [], Counter()
    cur = {"title": "(front matter)", "raw": []}
    for pno, lines in enumerate(pages, 1):
        edges = set(edge(lines))
        for l in lines:
            if (l in edges and mask(l) in repeated) or any(r.match(l) for r in noise_res):
                continue
            if is_heading(l):
                if cur["raw"] or cur["title"] != "(front matter)":
                    sections.append(cur)
                cur = {"title": l, "raw": []}
                continue
            cur["raw"].append((pno, l))
    sections.append(cur)
    for s in sections:
        s["lines"] = [[s["raw"][0][0] if s["raw"] else 0, s["title"]]] if s["title"] != "(front matter)" else []
        s["lines"] += _units(s["raw"], cfg)

    out = []
    for s in sections:
        counts[s["title"]] += 1
        key = s["title"] if counts[s["title"]] == 1 else f'{s["title"]} #{counts[s["title"]]}'
        body = "\n".join(t for _, t in s["lines"])
        pg = [p for p, _ in s["lines"]] or [0]
        out.append({
            "key": key, "title": s["title"], "first_page": min(pg), "last_page": max(pg),
            "hash": hashlib.sha256(body.encode()).hexdigest(),
            "body_hash": hashlib.sha256("\n".join(t for _, t in s["lines"][1:]).encode()).hexdigest(),
            "lines": s["lines"],
        })

    with open(pdf_path, "rb") as fh:
        file_hash = hashlib.sha256(fh.read()).hexdigest()
    text_hash = hashlib.sha256("\n".join(s["hash"] for s in out).encode()).hexdigest()
    return {
        "engine_version": ENGINE_VERSION,
        "source_file": os.path.basename(pdf_path),
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "page_count": len(pages), "section_count": len(out),
        "file_sha256": file_hash, "text_sha256": text_hash,
        "warnings": (["Few headings detected - tune heading_regex in the config"]
                     if len(out) < max(5, len(pages) / 50) else []),
        "sections": out,
    }


def save_snapshot(snap: dict, path: str) -> None:
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "wt", encoding="utf-8") as fh:
        json.dump(snap, fh, ensure_ascii=False)


def load_any(path: str, cfg: dict) -> dict:
    if path.lower().endswith(".pdf"):
        return build_snapshot(path, cfg)
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


# ------------------------------------------------------------------ compare
def _word_diff(a: str, b: str) -> str:
    aw, bw = a.split(), b.split()
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, aw, bw, autojunk=False).get_opcodes():
        if tag == "equal":
            out.append(" ".join(aw[i1:i2]))
        if tag in ("delete", "replace"):
            out.append("[-" + " ".join(aw[i1:i2]) + "-]")
        if tag in ("insert", "replace"):
            out.append("{+" + " ".join(bw[j1:j2]) + "+}")
    return " ".join(out)


def compare(old: dict, new: dict, cfg: dict) -> dict:
    report = {
        "engine_version": ENGINE_VERSION,
        "old": {k: old[k] for k in ("source_file", "page_count", "section_count", "file_sha256", "text_sha256")},
        "new": {k: new[k] for k in ("source_file", "page_count", "section_count", "file_sha256", "text_sha256")},
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "warnings": list(dict.fromkeys(old.get("warnings", []) + new.get("warnings", []))),
    }
    if old["text_sha256"] == new["text_sha256"]:
        report.update(changed=False, file_identical=old["file_sha256"] == new["file_sha256"],
                      stats={"sections_added": 0, "sections_removed": 0, "sections_modified": 0,
                             "sections_renamed": 0, "change_blocks": 0}, changes=[])
        return report

    o = {s["key"]: s for s in old["sections"]}
    n = {s["key"]: s for s in new["sections"]}
    changes = []

    added = [k for k in n if k not in o]
    removed = [k for k in o if k not in n]
    # renamed / renumbered: same body, different heading
    by_body = {o[k]["body_hash"]: k for k in removed}
    for k in list(added):
        ok = by_body.get(n[k]["body_hash"])
        if ok and ok in removed:
            changes.append({"section": k, "type": "section_renamed", "old_title": o[ok]["title"],
                            "new_title": n[k]["title"], "old_pages": [o[ok]["first_page"], o[ok]["last_page"]],
                            "new_pages": [n[k]["first_page"], n[k]["last_page"]]})
            added.remove(k); removed.remove(ok)

    for k in added:
        s = n[k]
        changes.append({"section": k, "type": "section_added", "new_pages": [s["first_page"], s["last_page"]],
                        "new_text": "\n".join(t for _, t in s["lines"])})
    for k in removed:
        s = o[k]
        changes.append({"section": k, "type": "section_removed", "old_pages": [s["first_page"], s["last_page"]],
                        "old_text": "\n".join(t for _, t in s["lines"])})

    modified = 0
    for k in n:
        if k not in o or o[k]["hash"] == n[k]["hash"]:
            continue
        a, b = o[k]["lines"], n[k]["lines"]
        at, bt = [t for _, t in a], [t for _, t in b]
        blocks = []
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, at, bt, autojunk=False).get_opcodes():
            if tag == "equal":
                continue
            ot, nt = "\n".join(at[i1:i2]), "\n".join(bt[j1:j2])
            if cfg["ignore_cosmetic"] and _cosmetic_key(ot) == _cosmetic_key(nt):
                continue
            blocks.append({
                "section": k, "type": {"replace": "modified", "delete": "deleted", "insert": "inserted"}[tag],
                "old_page": a[i1][0] if i1 < len(a) else (a[-1][0] if a else None),
                "new_page": b[j1][0] if j1 < len(b) else (b[-1][0] if b else None),
                "old_text": ot, "new_text": nt,
                "word_diff": _word_diff(ot, nt) if tag == "replace" else None,
            })
        if blocks:
            modified += 1
            changes.extend(blocks)

    order = {s["key"]: i for i, s in enumerate(new["sections"])}
    order.update({s["key"]: i + 0.5 for i, s in enumerate(old["sections"]) if s["key"] not in order})
    changes.sort(key=lambda c: order.get(c["section"], 1e9))
    for i, c in enumerate(changes, 1):
        c["id"] = i

    t = Counter(c["type"] for c in changes)
    report.update(changed=bool(changes), file_identical=False, stats={
        "sections_added": t["section_added"], "sections_removed": t["section_removed"],
        "sections_modified": modified, "sections_renamed": t["section_renamed"],
        "change_blocks": len(changes)}, changes=changes)
    return report


# ------------------------------------------------------------------ outputs
def _cut(s, n):
    if s is None:
        return None
    return s if len(s) <= n else s[:n] + f" …[+{len(s) - n} chars]"


def ai_payload(report: dict, cfg: dict) -> dict:
    per, total = cfg["ai_max_chars_per_change"], cfg["ai_max_total_chars"]
    items, used, dropped = [], 0, 0
    for c in report["changes"]:
        item = {k: v for k, v in c.items() if v is not None}
        for f in ("old_text", "new_text", "word_diff"):
            if f in item:
                item[f] = _cut(item[f], per)
        if "word_diff" in item:  # word diff carries both sides; avoid sending text twice
            item.pop("old_text", None); item.pop("new_text", None)
        size = len(json.dumps(item, ensure_ascii=False))
        if used + size > total:
            dropped += 1
            continue
        used += size
        items.append(item)
    return {"old": report["old"]["source_file"], "new": report["new"]["source_file"],
            "pages_old": report["old"]["page_count"], "pages_new": report["new"]["page_count"],
            "stats": report["stats"], "truncated_changes": dropped, "changes": items}


def to_markdown(report: dict) -> str:
    st = report["stats"]
    L = [f"# Change report: {report['old']['source_file']} → {report['new']['source_file']}", "",
         f"Generated {report['generated_utc']} · engine {report['engine_version']}", ""]
    if not report["changed"]:
        L.append("**No content changes detected.**" + (" Files are byte-identical." if report["file_identical"]
                 else " The file differs only in metadata or layout."))
        return "\n".join(L) + "\n"
    L += ["| Metric | Value |", "|---|---|",
          f"| Pages (old → new) | {report['old']['page_count']} → {report['new']['page_count']} |",
          f"| Sections modified | {st['sections_modified']} |", f"| Sections added | {st['sections_added']} |",
          f"| Sections removed | {st['sections_removed']} |", f"| Sections renamed | {st['sections_renamed']} |",
          f"| Change blocks | {st['change_blocks']} |", ""]
    for w in report["warnings"]:
        L.append(f"> ⚠️ {w}")
    cur = None
    for c in report["changes"]:
        if c["section"] != cur:
            cur = c["section"]
            L += ["", f"## {cur}"]
        pages = f"old p.{c.get('old_page') or c.get('old_pages')} → new p.{c.get('new_page') or c.get('new_pages')}"
        L.append(f"\n**#{c['id']} {c['type']}** ({pages})\n")
        if c["type"] == "section_renamed":
            L.append(f"`{c['old_title']}` → `{c['new_title']}`")
        elif c.get("word_diff"):
            L.append("```diff\n" + _cut(c["word_diff"], 3000) + "\n```")
        else:
            if c.get("old_text"):
                L.append("```diff\n" + "\n".join("- " + x for x in _cut(c["old_text"], 3000).splitlines()) + "\n```")
            if c.get("new_text"):
                L.append("```diff\n" + "\n".join("+ " + x for x in _cut(c["new_text"], 3000).splitlines()) + "\n```")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------- CLI
def load_config(path: str | None) -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if path:
        with open(path, encoding="utf-8") as fh:
            cfg.update({k: v for k, v in json.load(fh).items() if not k.startswith("_")})
    return cfg


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot"); s.add_argument("pdf"); s.add_argument("-o", "--out", required=True)
    s.add_argument("--config")
    c = sub.add_parser("compare"); c.add_argument("old"); c.add_argument("new")
    c.add_argument("-o", "--out", default="changes.json"); c.add_argument("--md")
    c.add_argument("--ai-payload"); c.add_argument("--save-snapshot"); c.add_argument("--config")
    a = ap.parse_args(argv)
    try:
        cfg = load_config(a.config)
        if a.cmd == "snapshot":
            snap = build_snapshot(a.pdf, cfg)
            save_snapshot(snap, a.out)
            print(json.dumps({"pages": snap["page_count"], "sections": snap["section_count"],
                              "text_sha256": snap["text_sha256"], "warnings": snap["warnings"]}))
            return 0
        old, new = load_any(a.old, cfg), load_any(a.new, cfg)
        if a.save_snapshot:
            save_snapshot(new, a.save_snapshot)
        rep = compare(old, new, cfg)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, ensure_ascii=False, indent=2)
        if a.md:
            with open(a.md, "w", encoding="utf-8") as fh:
                fh.write(to_markdown(rep))
        if a.ai_payload:
            with open(a.ai_payload, "w", encoding="utf-8") as fh:
                json.dump(ai_payload(rep, cfg), fh, ensure_ascii=False, indent=2)
        print(json.dumps({"changed": rep["changed"], **rep["stats"], "warnings": rep["warnings"]}))
        return 1 if rep["changed"] else 0
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
