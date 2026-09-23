"""Re-run required validation while preserving every frozen v1 file."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports/geometric_v2"


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    results = []
    # The inherited validator writes reports/validation.json and reports/demo.json.
    # Run that exact command on identical source in a temporary copy, then retain
    # its new output separately from v1's immutable validation artifacts.
    with tempfile.TemporaryDirectory(prefix="adiona-v2-validation-") as directory:
        copied = Path(directory) / "project"
        shutil.copytree(ROOT, copied, ignore=shutil.ignore_patterns(".git", "__pycache__", "runs", "reports"))
        started = time.perf_counter()
        command = [sys.executable, "-S", "scripts/validate.py"]
        result = subprocess.run(command, cwd=copied, capture_output=True, text=True)
        (REPORTS / "kernel-validation.log").write_text(result.stdout + result.stderr)
        if (copied / "reports/validation.json").exists():
            shutil.copy2(copied / "reports/validation.json", REPORTS / "kernel-validation.json")
            report = json.loads((REPORTS / "kernel-validation.json").read_text())
        else:
            report = {"passed": False, "tests_run": 0}
        results.append({"suite": "inherited kernel and contract suite", "command": command,
                        "returncode": result.returncode, "tests_run": report["tests_run"],
                        "passed": result.returncode == 0 and report["passed"],
                        "seconds": time.perf_counter() - started, "isolated_copy": True})
    for suite in ("research_tests", "research_tests_v2"):
        started = time.perf_counter()
        command = [sys.executable, "-m", "unittest", "discover", "-s", suite, "-v"]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        log = result.stdout + result.stderr
        (REPORTS / f"{suite}-validation.log").write_text(log)
        import re
        counts = re.findall(r"Ran (\d+) tests? in", log)
        results.append({"suite": suite, "command": command, "returncode": result.returncode,
                        "tests_run": int(counts[-1]) if counts else 0,
                        "passed": result.returncode == 0 and bool(counts) and "\nOK\n" in log,
                        "seconds": time.perf_counter() - started})
    frozen = json.loads((REPORTS / "v1-freeze.json").read_text())
    modified = [name for name, digest in frozen["files"].items()
                if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest]
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "suites": results,
              "tests_run": sum(r["tests_run"] for r in results),
              "frozen_v1_files": len(frozen["files"]), "modified_v1_files": modified,
              "passed": all(r["passed"] for r in results) and not modified,
              "observed_github_ci": False, "independent_governance_review": False,
              "production_cleared": False}
    (REPORTS / "validation-summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
