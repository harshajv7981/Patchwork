"""Self-check for the work-in-progress limits: python test_log.py (uses a throwaway BUG_BOUNTY_HOME)."""
import os
import sys
import tempfile
from pathlib import Path

os.environ["BUG_BOUNTY_HOME"] = tempfile.mkdtemp()
HOME = Path(os.environ["BUG_BOUNTY_HOME"])
sys.path.insert(0, str(Path(__file__).parent))
import log  # noqa: E402

POLICY = "https://www.microsoft.com/en-us/msrc/bounty-ai"
R = log.REFUSED


def submit_one(n):
    assert log.main(["start", f"p{n}", "--policy", POLICY]) == 0
    assert log.main(["submit", "--url", f"r{n}"]) == R  # no hypothesis yet
    assert log.main(["hypothesis", f"idea {n}"]) == 0
    assert log.main(["submit", "--url", f"r{n}"]) == 0


assert log.main(["status"]) == 0
assert log.main(["hypothesis", "x"]) == R  # nothing being worked on
assert log.main(["close", "abandoned"]) == R  # nothing open
assert log.main(["start", "copilot", "--policy", "http://x"]) == R  # not https
assert log.main(["start", "copilot", "--policy", POLICY]) == 0
assert (HOME / "bb-001" / "report.md").exists()
assert log.main(["start", "other", "--policy", POLICY]) == R  # one worked on at a time
assert log.main(["close", "disproved"]) == 0  # only one open: no --id needed

for n in (2, 3, 4):  # three reports awaiting triage at once is fine
    submit_one(n)
assert log.main(["hypothesis", "late idea"]) == R  # submitted reports are frozen
assert log.main(["start", "fifth", "--policy", POLICY]) == R  # a fourth would exceed MAX_AWAITING
assert log.main(["close", "accepted"]) == R  # ambiguous: three open
assert log.main(["close", "accepted", "--id", "bb-003", "--bounty", "500"]) == 0
assert log.main(["start", "fifth", "--policy", POLICY]) == 0  # slot freed
assert log.main(["hypothesis", "idea 5"]) == 0 and log.main(["submit", "--url", "r5"]) == 0
assert len(log.awaiting(log.load())) == 3 and log.active(log.load()) is None
for i in ("bb-002", "bb-004", "bb-005"):
    assert log.main(["close", "duplicate", "--id", i]) == 0
assert log.main(["metrics"]) == 0
assert sum(i["bounty"] for i in log.load()["investigations"]) == 500

# Candidate queue: patchwork-bot's private security findings.
C = ["candidate", "--repo", "o/r", "--file", "a.py", "--title", "Path traversal in load()",
     "--channel", "huntr", "--policy", "https://huntr.com/guidelines"]
assert log.main(C) == 0
assert log.main(C) == R  # duplicate
(HOME / "candidates" / "bc-001" / "poc_test.py").write_text("assert 0\n")
assert log.main(["start", "x", "--policy", POLICY]) == 0
assert log.main(["promote", "bc-001"]) == R  # an investigation is being worked on
assert log.main(["close", "abandoned"]) == 0
assert log.main(["promote", "bc-001"]) == 0
inv = log.active(log.load())
assert (HOME / inv["id"] / "poc_test.py").exists() and inv["status"] == "testing"  # PoC travels along
assert log.main(["promote", "bc-001"]) == R  # no longer queued
assert log.main(["discard", "bc-999", "--reason", "x"]) == R
print("ok")
