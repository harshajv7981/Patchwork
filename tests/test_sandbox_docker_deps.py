import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import sandbox_service


class DockerDependencyInstallTests(unittest.TestCase):
    """Docker isn't available in CI, so we assert the command plan, not real execution."""

    def _run(self, files):
        calls = []

        def fake_run_cmd(cmd, cwd, timeout=30, env_extra=None, runtime=None, network=False):
            calls.append({"cmd": cmd, "network": network, "runtime": runtime})
            return 0, "ok", "", 0.1

        with tempfile.TemporaryDirectory() as d:
            sandbox = Path(d)
            for name, body in files.items():
                (sandbox / name).write_text(body)
            with patch.object(sandbox_service, "_run_cmd", side_effect=fake_run_cmd):
                python_path, manager, setup_error = sandbox_service._prepare_test_environment(sandbox, "docker")
        return python_path, manager, setup_error, calls

    def test_requirements_install_with_network_then_offline_interpreter(self):
        python_path, _, setup_error, calls = self._run({"requirements.txt": "pytest\n"})
        self.assertIsNone(setup_error)
        # Returned interpreter is workspace-relative so the offline pytest run uses the venv.
        self.assertEqual(python_path, ".patchwork-venv/bin/python")
        self.assertFalse(Path(python_path).is_absolute())
        # venv creation + dependency install both ran with the network enabled.
        self.assertTrue(calls and all(c["network"] for c in calls))
        self.assertIn("-r", calls[-1]["cmd"])

    def test_pyproject_installs_editable_package(self):
        _, _, setup_error, calls = self._run({"pyproject.toml": "[project]\nname='x'\n"})
        self.assertIsNone(setup_error)
        self.assertIn("-e", calls[-1]["cmd"])
        self.assertIn(".[dev]", calls[-1]["cmd"])

    def test_install_failure_surfaces_as_setup_error(self):
        def fail_second(cmd, cwd, timeout=30, env_extra=None, runtime=None, network=False):
            # venv create succeeds, dependency install fails.
            return (0, "", "", 0.1) if "venv" in cmd else (1, "", "No matching distribution", 0.1)

        with tempfile.TemporaryDirectory() as d:
            sandbox = Path(d)
            (sandbox / "requirements.txt").write_text("nope\n")
            with patch.object(sandbox_service, "_run_cmd", side_effect=fail_second):
                _, _, setup_error = sandbox_service._prepare_test_environment(sandbox, "docker")
        self.assertIsNotNone(setup_error)
        self.assertIn("No matching distribution", setup_error)


if __name__ == "__main__":
    unittest.main()
