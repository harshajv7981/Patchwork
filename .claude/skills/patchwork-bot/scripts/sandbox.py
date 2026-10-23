#!/usr/bin/env python3
"""Run a repo checkout through Patchwork's hardened Docker sandbox and print JSON.

Reuses backend/app/sandbox_service.py (wheel-only networked install, offline test run,
secrets scrubbed) instead of re-implementing it. Works on a throwaway copy, so the
checkout you pass in is never modified.

  sandbox.py <checkout_dir> [--changed FILE ...] [--tests TEST_PATH ...]

--changed  files to syntax/lint/type-check (the files the fix touched)
--tests    run only these test files/dirs; default = the repo's whole suite (avoid on big repos)
--dep-timeout  seconds for the dependency install (default 180; raise for torch-sized deps)
Exit code: 0 if everything passed, 1 if anything failed, 2 on setup error.
Run with the Patchwork virtualenv: <repo>/.venv/bin/python sandbox.py ...

The sandbox image is chosen to match the repo's `requires-python`: it tries the highest
built `patchwork-sandbox:pyX.Y` that satisfies it (dependencies are often gated on the
newest supported Python), and if the wheel-only dependency install fails there (brand-new
Pythons often lack wheels, and pinned deps may cap the Python version), steps down through
the older matching versions until one installs. Build images with:
  docker build --build-arg PYTHON_VERSION=3.14 -f Dockerfile.sandbox -t patchwork-sandbox:py3.14 .
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import Version

PATCHWORK_ROOT = Path(__file__).resolve().parents[4]  # .claude/skills/patchwork-bot/scripts -> repo
IMAGE = "patchwork-sandbox"


def built_pythons() -> list[str]:
    out = subprocess.run(["docker", "image", "ls", IMAGE, "--format", "{{.Tag}}"],
                         capture_output=True, text=True).stdout.split()
    return sorted((t[2:] for t in out if t.startswith("py")), key=Version)


def requires_python(checkout: Path) -> str | None:
    try:
        data = tomllib.loads((checkout / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    spec = data.get("project", {}).get("requires-python")
    return spec if isinstance(spec, str) else None


def candidate_pythons(spec: str | None, available: list[str]) -> list[str]:
    """Available X.Y versions satisfying `spec`, highest first (no/invalid spec -> all)."""
    try:
        allowed = SpecifierSet(spec) if spec else None
    except InvalidSpecifier:
        allowed = None
    # Check X.Y.99 too, so "<3.15" style upper bounds and ">=3.14.1" style lower bounds both work.
    fits = [v for v in available
            if allowed is None or any(allowed.contains(f"{v}.{p}", prereleases=True) for p in (0, 99))]
    return sorted(fits, key=Version, reverse=True)


MAX_PYTHON_TRIES = 4  # dependency-resolution failures are fast, so trying every built version is cheap


def run_once(sb, src: Path, args, version: str, spec: str | None) -> dict:
    """One full check on a throwaway copy of the checkout."""
    work = Path(tempfile.mkdtemp(prefix="patchwork_bot_"))
    try:
        shutil.copytree(src, work, dirs_exist_ok=True, symlinks=True,
                        ignore=shutil.ignore_patterns(".git", ".venv", ".patchwork-venv", "__pycache__"))
        return {
            "python": version,
            "requires_python": spec,
            "syntax": sb._check_syntax(work, args.changed, "docker") if args.changed else None,
            "lint": sb._check_linters(work, args.changed, "docker") if args.changed else None,
            "types": sb._check_types(work, args.changed, "docker") if args.changed else None,
            "tests": sb._run_pytest_suite(work, args.tests, args.timeout, "docker"),
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("checkout")
    p.add_argument("--changed", nargs="*", default=[])
    p.add_argument("--tests", nargs="*", default=[])
    p.add_argument("--timeout", type=int, default=300)
    p.add_argument("--dep-timeout", type=int, help="seconds for the dependency install (heavy deps like torch)")
    args = p.parse_args()

    src = Path(args.checkout).resolve()
    spec = requires_python(src)
    versions = candidate_pythons(spec, built_pythons())[:MAX_PYTHON_TRIES]
    if not versions:
        print(json.dumps({"setup_error": True, "passed": False,
                          "reason": f"no sandbox image satisfies requires-python {spec!r}"}))
        return 2
    sys.path.insert(0, str(PATCHWORK_ROOT / "backend"))
    from app import sandbox_service as sb
    if args.dep_timeout:
        sb.SANDBOX_DEPENDENCY_TIMEOUT_SECONDS = args.dep_timeout

    tried = []
    for version in versions:
        # The image is read from a module global, so switch it per attempt.
        sb.SANDBOX_DOCKER_IMAGE = f"{IMAGE}:py{version}"
        report = run_once(sb, src, args, version, spec)
        tried.append(version)
        if not report["tests"].get("setup_error"):
            break
    report["pythons_tried"] = tried

    tests = report["tests"]
    report["setup_error"] = bool(tests.get("setup_error"))
    # Syntax and tests gate the result; lint/type output is informational (most repos
    # already have warnings unrelated to the change).
    report["passed"] = (
        not report["setup_error"]
        and tests.get("passed", False)
        and (report["syntax"] is None or report["syntax"].get("passed", True))
    )
    print(json.dumps(report, indent=2, default=str))
    return 2 if report["setup_error"] else (0 if report["passed"] else 1)


if __name__ == "__main__":
    sys.exit(main())
