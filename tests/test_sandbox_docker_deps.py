import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import sandbox_service


class DockerDependencyInstallTests(unittest.TestCase):
    """Docker isn't available in CI, so we assert the command plan, not real execution."""

    def _run(self, files, result=(0, "ok", "", 0.1)):
        calls = []

        def fake_run_cmd(cmd, cwd, timeout=30, env_extra=None, runtime=None, network=False):
            calls.append({"cmd": cmd, "network": network})
            return result

        with tempfile.TemporaryDirectory() as d:
            sandbox = Path(d)
            for name, body in files.items():
                (sandbox / name).parent.mkdir(parents=True, exist_ok=True)
                (sandbox / name).write_text(body)
            with patch.object(sandbox_service, "_run_cmd", side_effect=fake_run_cmd):
                python_path, _, setup_error = sandbox_service._prepare_test_environment(sandbox, "docker")
        return python_path, setup_error, calls

    def test_requirements_install_only_plain_wheels_with_network(self):
        python_path, setup_error, calls = self._run({
            "requirements.txt": "requests>=2  # http\n-r requirements-dev.txt\n-e .\ngit+https://evil/x.git\n--index-url https://evil/simple\n",
            "requirements-dev.txt": "pywin32; sys_platform == 'win32'\nfoo @ https://evil/foo.whl\n",
        })
        self.assertIsNone(setup_error)
        self.assertEqual(python_path, sandbox_service.DOCKER_VENV_PYTHON)
        self.assertEqual(len(calls), 1)  # no local project -> no offline editable step
        install = calls[0]
        self.assertTrue(install["network"])
        self.assertIn("--only-binary=:all:", install["cmd"][2])
        specs = install["cmd"][4:]
        self.assertEqual(specs, ["pytest", "requests>=2", "pywin32; sys_platform == 'win32'"])

    def test_pyproject_deps_read_statically_and_project_installed_offline(self):
        _, setup_error, calls = self._run({"pyproject.toml": """
[build-system]
requires = ["hatchling"]
[project]
name = "My_Pkg"
dependencies = ["click>=8"]
[project.optional-dependencies]
dev = ["my-pkg[lint]", "pytest-cov"]
lint = ["ruff"]
"""})
        self.assertIsNone(setup_error)
        online, offline = calls
        self.assertTrue(online["network"])
        self.assertEqual(sorted(online["cmd"][4:]), ["click>=8", "hatchling", "pytest", "pytest-cov", "ruff"])
        self.assertFalse(offline["network"])
        self.assertIn("--no-index", offline["cmd"])
        self.assertEqual(offline["cmd"][-2:], ["-e", "/workspace/."])

    def test_hash_pinned_requirements_keep_their_packages(self):
        _, _, calls = self._run({
            "requirements.txt": "requests==2.32.3 \\\n    --hash=sha256:abc\nclick==8.1.7 \\\n    --hash=sha256:def\n",
        })
        self.assertEqual(calls[0]["cmd"][4:], ["pytest", "requests==2.32.3", "click==8.1.7"])

    def test_editable_line_in_requirements_installs_project_deps_and_extras(self):
        _, setup_error, calls = self._run({
            "pyproject.toml": "[project]\nname='x'\ndependencies=['click']\n"
                              "[project.optional-dependencies]\nfast=['orjson']\n",
            "requirements-dev.txt": "-e .[fast]\npytest-cov\n",
        })
        self.assertIsNone(setup_error)
        online, offline = calls
        self.assertEqual(sorted(online["cmd"][4:]), ["click", "orjson", "pytest", "pytest-cov", "setuptools>=40.8.0"])
        self.assertEqual(offline["cmd"][-2:], ["-e", "/workspace/."])

    def test_symlinks_out_of_the_sandbox_are_never_read(self):
        with tempfile.TemporaryDirectory() as outside_dir:
            secret = Path(outside_dir) / "secret.txt"
            secret.write_text("hostsecret==1\n")
            (Path(outside_dir) / "pyproject.toml").write_text("[project]\nname='x'\ndependencies=['leaked']\n")
            with tempfile.TemporaryDirectory() as d:
                sandbox = Path(d)
                (sandbox / "requirements.txt").symlink_to(secret)
                (sandbox / "requirements-dev.txt").write_text("-r ../" + secret.name + "\n")
                self.assertEqual(sandbox_service._wheel_requirements(sandbox / "requirements.txt", sandbox, set(), {}), [])
                self.assertEqual(sandbox_service._wheel_requirements(sandbox / "requirements-dev.txt", sandbox, set(), {}), [])
                (sandbox / "pkg").mkdir()
                (sandbox / "pkg" / "pyproject.toml").symlink_to(Path(outside_dir) / "pyproject.toml")
                self.assertIsNone(sandbox_service._static_project_requirements(sandbox / "pkg", sandbox))

    def test_dynamic_dependencies_are_a_setup_error_without_running_anything(self):
        _, setup_error, calls = self._run({"pyproject.toml": "[project]\nname='x'\ndynamic=['dependencies']\n"})
        self.assertIn("does not declare its dependencies statically", setup_error)
        self.assertEqual(calls, [])

    def test_non_installable_repo_root_runs_from_source(self):
        # Wheels install fine, but the repo root isn't a package (flat collection of modules):
        # the offline editable install fails and the tests should still run from source.
        def fake(cmd, cwd, timeout=30, env_extra=None, runtime=None, network=False):
            return (0, "", "", 0.1) if network else (1, "", "Multiple top-level packages discovered", 0.1)

        with tempfile.TemporaryDirectory() as d:
            sandbox = Path(d)
            (sandbox / "pyproject.toml").write_text("[project]\nname='algos'\ndependencies=['numpy']\n")
            with patch.object(sandbox_service, "_run_cmd", side_effect=fake):
                _, manager, setup_error = sandbox_service._prepare_test_environment(sandbox, "docker")
        self.assertIsNone(setup_error)
        self.assertIn("run from source", manager)

    def test_install_failure_surfaces_as_setup_error(self):
        _, setup_error, _ = self._run({"requirements.txt": "nope\n"}, result=(1, "", "No matching distribution", 0.1))
        self.assertIn("No matching distribution", setup_error)


class DockerRunFlagsTests(unittest.TestCase):
    def _docker_cmd(self, cmd, network):
        with tempfile.TemporaryDirectory() as cache, patch.object(sandbox_service, "PIP_CACHE_DIR", Path(cache)), \
                patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")) as run:
            sandbox_service._run_cmd(cmd, cwd=Path("."), runtime="docker", network=network)
        return run.call_args.args[0]

    def test_offline_runs_have_no_network_and_see_the_workspace(self):
        cmd = self._docker_cmd([sandbox_service.VENV_PYTHON, "-m", "pytest"], network=False)
        self.assertIn("--network=none", cmd)
        self.assertNotIn("--network=bridge", cmd)
        self.assertIn("PYTHONPATH=/workspace", cmd)
        self.assertNotIn("PIP_CACHE_DIR=/pip-cache", cmd)
        self.assertEqual(cmd[-3:], ["python", "-m", "pytest"])  # host interpreter -> image python

    def test_network_runs_keep_the_repo_off_sys_path_and_pip_config(self):
        cmd = self._docker_cmd(["sh", "-c", "true"], network=True)
        self.assertIn("--network=bridge", cmd)
        self.assertNotIn("--network=none", cmd)
        self.assertNotIn("PYTHONPATH=/workspace", cmd)
        self.assertIn("PIP_CONFIG_FILE=/dev/null", cmd)
        self.assertEqual(cmd[cmd.index("-w") + 1], "/tmp")


if __name__ == "__main__":
    unittest.main()
