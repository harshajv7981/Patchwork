import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.sandbox_service import (
    _check_security,
    _parse_bandit,
    _parse_gitleaks,
    _parse_pip_audit,
    _parse_semgrep,
)

BANDIT = json.dumps({"results": [{
    "filename": "app.py", "line_number": 3, "test_id": "B602",
    "issue_severity": "HIGH", "issue_text": "subprocess call with shell=True",
}]})
SEMGREP = json.dumps({"results": [{
    "path": "app.py", "start": {"line": 5}, "check_id": "opt.semgrep.python.lang.security.eval",
    "extra": {"severity": "WARNING", "message": "eval is dangerous"},
}]})
GITLEAKS = json.dumps([{
    "File": "config.py", "StartLine": 1, "RuleID": "aws-access-token",
    "Description": "AWS key", "Secret": "AKIAREALSECRET", "Match": "key = AKIAREALSECRET",
}])
PIP_AUDIT = json.dumps({"dependencies": [
    {"name": "jinja2", "version": "2.10", "vulns": [{"id": "PYSEC-2019-217", "fix_versions": ["2.10.1"]}]},
    {"name": "jinja2", "version": "2.10", "vulns": [{"id": "PYSEC-2019-217", "fix_versions": ["2.10.1"]}]},
    {"name": "pip", "version": "25.0", "vulns": [{"id": "PYSEC-2026-1", "fix_versions": ["26.0"]}]},
    {"name": "localpkg", "skip_reason": "not on PyPI"},
]})


class ParserTests(unittest.TestCase):
    def test_bandit(self):
        self.assertEqual(_parse_bandit(BANDIT), [{
            "tool": "bandit", "file": "app.py", "line": 3, "rule": "B602",
            "severity": "high", "message": "subprocess call with shell=True",
        }])

    def test_semgrep_maps_warning_to_medium(self):
        [finding] = _parse_semgrep(SEMGREP)
        self.assertEqual((finding["rule"], finding["line"], finding["severity"]),
                         ("python.lang.security.eval", 5, "medium"))

    def test_gitleaks_never_copies_the_secret(self):
        [finding] = _parse_gitleaks(GITLEAKS)
        self.assertEqual((finding["file"], finding["severity"]), ("config.py", "high"))
        self.assertNotIn("AKIAREALSECRET", json.dumps(finding))
        self.assertEqual(_parse_gitleaks(""), [])

    def test_pip_audit_dedupes_and_skips_pip_and_unaudited_deps(self):
        self.assertEqual(_parse_pip_audit(PIP_AUDIT), [{
            "tool": "pip-audit", "file": "jinja2==2.10", "line": "-", "rule": "PYSEC-2019-217",
            "severity": "unknown", "message": "fixed in: 2.10.1",
        }])


class CheckSecurityTests(unittest.TestCase):
    def run_check(self, outputs):
        """outputs: tool name -> (exit_code, stdout)."""
        def fake_run(cmd, **kwargs):
            code, out = outputs[cmd[0]]
            return code, out, "boom" if code > 1 else "", 0.1

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app.py").write_text("x = 1\n")
            (root / ".patchwork-venv/lib/python3.12/site-packages").mkdir(parents=True)
            with patch("app.sandbox_service._run_cmd", side_effect=fake_run):
                return _check_security(root, ["app.py"], "docker")

    def test_high_finding_in_changed_file_blocks(self):
        res = self.run_check({"bandit": (1, BANDIT), "semgrep": (0, SEMGREP),
                              "gitleaks": (0, "[]"), "pip-audit": (0, '{"dependencies": []}')})
        self.assertFalse(res["passed"])
        self.assertEqual(res["blocking_count"], 1)
        self.assertEqual(res["tools"], ["bandit", "semgrep", "gitleaks", "pip-audit"])

    def test_pip_audit_and_medium_findings_do_not_block(self):
        res = self.run_check({"bandit": (0, '{"results": []}'), "semgrep": (0, SEMGREP),
                              "gitleaks": (0, "[]"), "pip-audit": (1, PIP_AUDIT)})
        self.assertTrue(res["passed"])
        self.assertEqual(res["findings_count"], 2)

    def test_scanner_crash_is_reported_not_swallowed(self):
        res = self.run_check({"bandit": (2, "not json"), "semgrep": (0, '{"results": []}'),
                              "gitleaks": (0, "[]"), "pip-audit": (0, '{"dependencies": []}')})
        self.assertEqual(res["errors"], ["bandit: boom"])
        self.assertIn("1 scanner error", res["summary"])


if __name__ == "__main__":
    unittest.main()
