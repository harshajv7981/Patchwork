import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

STATE_PY = Path(__file__).resolve().parents[1] / ".claude/skills/patchwork-bot/scripts/state.py"
spec = importlib.util.spec_from_file_location("bot_state", STATE_PY)
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = bot.main(list(argv))
    return code, json.loads(out.getvalue())


def add(repo, title, kind="bug", type_="issue", number=1):
    return run("add", "--repo", repo, "--kind", kind, "--file", "a.py", "--title", title,
               "--url", f"https://github.com/{repo}/issues/{number}", "--type", type_, "--number", str(number))


class BotLimitTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        os.environ["PATCHWORK_BOT_HOME"] = self.home.name

    def tearDown(self):
        self.home.cleanup()
        os.environ.pop("PATCHWORK_BOT_HOME", None)

    def test_one_open_item_per_repo(self):
        self.assertEqual(add("o/a", "first")[0], 0)
        code, out = add("o/a", "second", number=2)
        self.assertEqual(code, bot.REFUSED)
        self.assertIn("already has an open item", out["reason"])

    def test_daily_cap_across_repos(self):
        for i in range(bot.DAILY_NEW_SUBMISSIONS):
            self.assertEqual(add(f"o/r{i}", "bug")[0], 0)
        code, out = add("o/extra", "bug")
        self.assertEqual(code, bot.REFUSED)
        self.assertIn("daily cap", out["reason"])

    def test_rejection_makes_repo_permanently_do_not_contact(self):
        _, out = add("o/a", "bug")
        run("update", out["item"]["id"], "--status", "rejected")
        self.assertEqual(run("check", "o/a")[0], bot.REFUSED)
        code, out = run("mark", "o/a", "trusted")
        self.assertEqual(code, bot.REFUSED)  # dnc can't be undone by the bot

    def test_merge_earns_trust_and_frees_the_slot(self):
        _, out = add("o/a", "bug")
        run("update", out["item"]["id"], "--status", "merged")
        self.assertEqual(run("repo", "o/a")[1]["status"], "trusted")
        self.assertEqual(run("check", "o/a")[0], 0)

    def test_review_and_ci_round_limits(self):
        _, out = add("o/a", "bug", type_="pr")
        item = out["item"]["id"]
        for _ in range(bot.MAX_REVIEW_ROUNDS):
            self.assertEqual(run("update", item, "--inc", "review")[0], 0)
        self.assertEqual(run("update", item, "--inc", "review")[0], bot.REFUSED)
        for _ in range(bot.MAX_CI_ATTEMPTS):
            self.assertEqual(run("update", item, "--inc", "ci")[0], 0)
        self.assertEqual(run("update", item, "--inc", "ci")[0], bot.REFUSED)

    def test_seen_findings_are_remembered(self):
        args = ("--repo", "o/a", "--kind", "bug", "--file", "a.py", "--title", "Off by one")
        self.assertFalse(run("seen", *args)[1]["seen"])
        run("drop", *args, "--reason", "not reproducible")
        self.assertTrue(run("seen", *args)[1]["seen"])

    def test_deferred_findings_stay_unseen_until_submitted_or_dropped(self):
        f = ("--repo", "o/a", "--kind", "bug", "--file", "a.py")
        self.assertEqual(run("defer", *f, "--title", "DOI prefix", "--confidence", "high")[0], 0)
        self.assertEqual(run("defer", *f, "--title", "Slug bug")[0], 0)
        self.assertFalse(run("seen", *f, "--title", "DOI prefix")[1]["seen"])  # still a candidate
        self.assertEqual(len(run("deferred", "o/a")[1]["o/a"]), 2)
        add("o/a", "DOI prefix")  # submitting it clears it from the backlog
        run("drop", *f, "--title", "Slug bug", "--reason", "fixed upstream")
        self.assertEqual(run("deferred", "o/a")[1]["o/a"], [])
        self.assertEqual(run("defer", *f, "--title", "DOI prefix")[0], bot.REFUSED)  # already submitted

    def test_audit_cooldown(self):
        self.assertEqual(run("check", "o/a", "--audit")[0], 0)
        run("audited", "o/a")
        self.assertEqual(run("check", "o/a", "--audit")[0], bot.REFUSED)
        self.assertEqual(run("check", "o/a")[0], 0)  # cool-down only gates audits, not watching


if __name__ == "__main__":
    unittest.main()
