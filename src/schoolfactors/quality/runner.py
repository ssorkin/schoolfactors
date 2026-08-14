"""Run all data-quality checks and generate DATA_QUALITY.md."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from schoolfactors.paths import KNOWN_ISSUES_DIR, REPO_ROOT
from schoolfactors.quality.checks import ALL_CHECKS, Finding

REPORT_PATH = REPO_ROOT / "DATA_QUALITY.md"

SEVERITY_ORDER = {"anomaly": 0, "warning": 1, "info": 2}
SEVERITY_MARK = {"anomaly": "🔴", "warning": "🟡", "info": "ℹ️"}


def load_known_issues() -> list[dict]:
    issues = []
    for path in sorted(KNOWN_ISSUES_DIR.glob("*.yaml")):
        issues.append(yaml.safe_load(path.read_text()))
    return issues


def run_checks(report_path: Path = REPORT_PATH) -> list[Finding]:
    findings: list[Finding] = []
    for check in ALL_CHECKS:
        print(f"  running {check.__name__} …")
        findings.extend(check())

    findings.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.check, f.year or 0))
    issues = load_known_issues()

    lines = [
        "# Data Quality Report",
        "",
        f"Generated {date.today().isoformat()} by `sf check`. "
        "This report is a first-class artifact of the pipeline: problems in the source "
        "data are surfaced here and in `known_issues/`, never silently patched.",
        "",
        "## Known issues (documented registry)",
        "",
    ]
    for issue in issues:
        years = ", ".join(str(y) for y in issue.get("years", []))
        lines += [
            f"### {issue['title']}",
            "",
            f"*{issue['kind']}, affects {issue['dataset']} {years}* — id `{issue['id']}`",
            "",
            issue["description"].strip(),
            "",
            f"**Handling:** {issue['handling'].strip()}",
            "",
        ]

    lines += ["## Check findings", ""]
    current = None
    for f in findings:
        if f.check != current:
            current = f.check
            lines += [f"### {f.check}", ""]
        year = f" **{f.year}**" if f.year else ""
        lines.append(f"- {SEVERITY_MARK[f.severity]}{year} {f.message}")
        for ex in f.details.get("examples", []):
            lines.append(f"  - {ex}")
    lines.append("")

    n_anom = sum(1 for f in findings if f.severity == "anomaly")
    n_warn = sum(1 for f in findings if f.severity == "warning")
    print(f"  {len(findings)} findings ({n_anom} anomalies, {n_warn} warnings)")
    report_path.write_text("\n".join(lines))
    print(f"  wrote {report_path.relative_to(REPO_ROOT)}")
    return findings
