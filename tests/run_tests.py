"""Smoke tests for pdf_diff.py using the bundled sample PDFs.  Run: python tests/run_tests.py"""
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "..", "skills", "pdf-change-monitor", "scripts", "pdf_diff.py")
CFG = os.path.join(HERE, "..", "skills", "pdf-change-monitor", "references", "config.json")
S = lambda f: os.path.join(HERE, "samples", f)


def run(old, new, tmp):
    out = os.path.join(tmp, "r.json")
    rc = subprocess.call([sys.executable, ENGINE, "compare", old, new, "-o", out, "--config", CFG],
                         stdout=subprocess.DEVNULL)
    return rc, json.load(open(out, encoding="utf-8"))


with tempfile.TemporaryDirectory() as tmp:
    rc, r = run(S("v1.pdf"), S("v1b.pdf"), tmp)
    assert rc == 0 and not r["changed"], "v1 vs v1b should have no content changes"
    rc, r = run(S("v1.pdf"), S("v2.pdf"), tmp)
    assert rc == 1 and r["stats"]["change_blocks"] == 6, r["stats"]
    types = sorted(c["type"] for c in r["changes"])
    assert types == ["inserted", "modified", "modified", "section_added", "section_removed", "section_renamed"], types
print("OK - all tests passed")
