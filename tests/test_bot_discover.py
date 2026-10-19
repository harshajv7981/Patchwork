import importlib.util
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / ".claude/skills/patchwork-bot/scripts"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    spec.loader.exec_module(module)
    return module


discover = _load("discover")
sandbox = _load("sandbox")
NOW = datetime(2026, 10, 19, tzinfo=timezone.utc)


def iso(days_ago):
    return (NOW - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")


def pr(assoc, created_ago, merged_ago=None, login="someone", kind="User"):
    return {"authorAssociation": assoc, "createdAt": iso(created_ago),
            "mergedAt": iso(merged_ago) if merged_ago is not None else None,
            "author": {"login": login, "__typename": kind}}


def repo(prs, stars=5000, open_prs=10, python=1.0, description="A library"):
    return {"stargazerCount": stars, "pushedAt": iso(1), "isFork": False, "isArchived": False,
            "description": description, "openPRs": {"totalCount": open_prs},
            "languages": {"totalSize": 100, "edges": [{"size": int(100 * python), "node": {"name": "Python"}}]},
            "closed": {"nodes": prs}}


class ReceptivenessTests(unittest.TestCase):
    def judge(self, data):
        return discover.assess(discover.measure(data, NOW), NOW)

    def test_fast_merging_repo_is_eligible(self):
        prs = [pr("CONTRIBUTOR", 3, 2) for _ in range(8)] + [pr("NONE", 5) for _ in range(2)]
        ok, reason, score = self.judge(repo(prs))
        self.assertTrue(ok, reason)
        self.assertGreater(score, 0)

    def test_repo_that_rejects_outsiders_is_skipped(self):
        prs = [pr("CONTRIBUTOR", 3, 2)] + [pr("NONE", 5) for _ in range(9)]
        ok, reason, _ = self.judge(repo(prs))
        self.assertFalse(ok)
        self.assertIn("merges only", reason)

    def test_slow_large_repo_is_skipped_but_same_speed_small_repo_is_not(self):
        prs = [pr("CONTRIBUTOR", 10, 5) for _ in range(10)]  # 5 days to merge
        self.assertFalse(self.judge(repo(prs, stars=100_000))[0])
        self.assertTrue(self.judge(repo(prs, stars=5_000))[0])

    def test_bots_and_maintainers_dont_count_as_outsiders(self):
        prs = [pr("MEMBER", 2, 1) for _ in range(20)] + [pr("NONE", 2, 1, login="renovate[bot]", kind="Bot") for _ in range(20)]
        ok, reason, _ = self.judge(repo(prs))
        self.assertFalse(ok)
        self.assertIn("too little outsider", reason)

    def test_list_and_non_python_repos_are_skipped(self):
        prs = [pr("CONTRIBUTOR", 3, 2) for _ in range(8)]
        self.assertFalse(self.judge(repo(prs, description="A curated list of tools"))[0])
        self.assertFalse(self.judge(repo(prs, python=0.3))[0])


class PickPythonTests(unittest.TestCase):
    AVAILABLE = ["3.12", "3.13", "3.14", "3.15"]

    def test_candidates_are_satisfying_versions_highest_first(self):
        self.assertEqual(sandbox.candidate_pythons(">=3.11,<3.15", self.AVAILABLE), ["3.14", "3.13", "3.12"])
        self.assertEqual(sandbox.candidate_pythons(">=3.15", self.AVAILABLE), ["3.15"])
        self.assertEqual(sandbox.candidate_pythons(">=3.14.1", self.AVAILABLE), ["3.15", "3.14"])

    def test_no_spec_allows_all_and_impossible_spec_allows_none(self):
        self.assertEqual(sandbox.candidate_pythons(None, self.AVAILABLE), ["3.15", "3.14", "3.13", "3.12"])
        self.assertEqual(sandbox.candidate_pythons(">=3.20", self.AVAILABLE), [])


if __name__ == "__main__":
    unittest.main()
