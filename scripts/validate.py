#!/usr/bin/env python3
"""Run actual local tests and produce honest, source-bound validation artifacts."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import platform
import sys
import unittest
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_ids(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from test_ids(item)
        else:
            yield item.id()


def main() -> int:
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    identifiers = sorted(test_ids(suite))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sources = {}
    for directory in ("adiona", "tests", "scripts", "governance", ".github", "docs"):
        for path in sorted((ROOT / directory).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix in (".py", ".json", ".md", ".yml"):
                sources[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ("README.md", "ROADMAP.md", "SECURITY.md", "CONTRIBUTING.md", "NOTICE.md", "pyproject.toml", ".gitignore", ".gitattributes", ".github/CODEOWNERS"):
        sources[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    report = {"project": "Adiona", "version": "0.1.0", "generated_at": datetime.now(timezone.utc).isoformat(),
              "python": platform.python_version(), "platform": platform.platform(),
              "scope": "local deterministic sandbox tests, not live GitHub CI or real-model evaluation",
              "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "skipped": len(result.skipped), "expected_failures": len(result.expectedFailures),
              "unexpected_successes": len(result.unexpectedSuccesses), "test_ids": identifiers,
              "passed": bool(result.testsRun > 0 and result.wasSuccessful() and not result.skipped and not result.expectedFailures),
              "production_cleared": False, "external_side_effects_allowed": False, "models_evaluated": 0,
              "source_sha256": sources}
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    (reports / "validation.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if report["passed"]:
        from adiona.__main__ import demo
        demonstration = demo()
        (reports / "demo.json").write_text(json.dumps(demonstration, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"tests_run": result.testsRun, "passed": True, "demo": demonstration}, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
