import ast
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

from adiona.contracts import BRIDGES, default_policy, validate_policy

ROOT = Path(__file__).resolve().parents[1]


class GovernanceTests(unittest.TestCase):
    def test_policy_example_matches_runtime(self):
        p = json.loads((ROOT / "governance/sandbox_policy.json").read_text())
        validate_policy(p)
        self.assertEqual(p, default_policy())

    def test_registry_matches_runtime_bridges(self):
        r = json.loads((ROOT / "governance/warrant_transition_registry.json").read_text())
        self.assertEqual([[x["source"], x["target"]] for x in r["bridges"]], BRIDGES)
        self.assertTrue(r["execution_is_separate"])

    def test_every_declared_invariant_names_existing_tests(self):
        names = set()
        for path in (ROOT / "tests").glob("test_*.py"):
            tree = ast.parse(path.read_text())
            names.update(node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"))
        spec = json.loads((ROOT / "governance/invariants.json").read_text())
        identifiers = set()
        for invariant in spec["invariants"]:
            self.assertNotIn(invariant["id"], identifiers)
            identifiers.add(invariant["id"])
            self.assertTrue(invariant["tests"])
            self.assertTrue(set(invariant["tests"]) <= names, invariant)

    def test_constitution_draft_keeps_seven_planes_nonsequential(self):
        c = json.loads((ROOT / "governance/constitution.json").read_text())
        self.assertEqual(c["status"], "DRAFT_NOT_RATIFIED")
        self.assertEqual(c["planes"], ["Purpose", "Epistemic", "Normative", "Strategic", "Decision", "Execution", "Temporal"])
        self.assertFalse(c["planes_are_mandatory_sequential_steps"])
        self.assertFalse(c["production_cleared"])
        self.assertFalse(c["external_side_effects_allowed"])

    def test_runtime_has_no_external_execution_imports(self):
        forbidden = {"subprocess", "socket", "requests", "http", "urllib", "httpx", "ftplib", "smtplib", "importlib"}
        for path in (ROOT / "adiona").glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Import):
                    imports = {alias.name.split(".")[0] for alias in node.names}
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    imports = {(node.module or "").split(".")[0]}
                else:
                    continue
                self.assertFalse(imports & forbidden, f"{path}: {imports}")
        # This checks declared direct imports, not a complete information-flow proof.

    def test_workflow_pins_actions_and_has_no_privileged_trigger(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        references = re.findall(r"uses:\s+[^@\s]+@([^\s]+)", workflow)
        self.assertGreaterEqual(len(references), 2)
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in references))
        self.assertNotIn("pull_request_target", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertIn("persist-credentials: false", workflow)

    def test_source_artifacts_are_not_distributed(self):
        manifest = json.loads((ROOT / "governance/source_manifest.json").read_text())
        self.assertFalse(manifest["source_files_distributed"])
        self.assertFalse(manifest["ERBA_frozen_files_modified"])
        for entry in manifest["inputs"]:
            self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$")
            self.assertFalse(entry["included_in_repository"])
        for suffix in ("*.docx", "*.pdf", "*.zip"):
            self.assertEqual(list(ROOT.rglob(suffix)), [])


class CLITests(unittest.TestCase):
    def run_cli(self, command):
        return subprocess.run([sys.executable, "-m", "adiona", command], cwd=ROOT,
                              capture_output=True, text=True, timeout=20, check=False)

    def test_status_reports_limits(self):
        result = self.run_cli("status")
        self.assertEqual(result.returncode, 0, result.stderr)
        status = json.loads(result.stdout)
        self.assertFalse(status["production_cleared"])
        self.assertEqual(status["models_evaluated"], 0)

    def test_deployment_check_is_closed(self):
        result = self.run_cli("deployment-check")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(json.loads(result.stdout)["external_side_effects_allowed"])

    def test_demo_returns_home_under_fresh_authority(self):
        result = self.run_cli("demo")
        self.assertEqual(result.returncode, 0, result.stderr)
        demo = json.loads(result.stdout)
        self.assertEqual(demo["state"]["status"], "home")
        self.assertEqual(demo["state"]["message"], "Welcome home.")
        self.assertEqual(demo["revision"], 2)
        self.assertEqual(demo["replayed_capability"], "DENIED")
        self.assertEqual(demo["old_approval_for_recovery"], "DENIED")
        self.assertTrue(demo["history_verified_against_retained_head"])
        self.assertFalse(demo["cognitive_independence_demonstrated"])
