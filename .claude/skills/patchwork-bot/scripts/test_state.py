"""Self-check for the dnc lift: python test_state.py (uses a throwaway PATCHWORK_BOT_HOME)."""
import os
import sys
import tempfile
from pathlib import Path

os.environ["PATCHWORK_BOT_HOME"] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).parent))
import state  # noqa: E402

CASES = {  # repo: (dnc reason, may --lift-cla?)
    "a/cla": ("requires CLA (CLAassistant on PR #537)", True),
    "a/psf": ("requires PSF CLA (cpython-cla-bot)", True),
    "a/ms": ("requires Microsoft CLA (wiki How-to-Contribute); TypeScript, outside Python sandbox", True),
    "a/ha": ("CLA.md; AI_POLICY forbids tools posting unreviewed content", False),
    "a/mne": ("CONTRIBUTING.md forbids issues/PRs from fully-automated tools", False),
    "a/guard": ("unattended-pr-guard auto-closed PR #8405 as spam", False),
}

for repo, (reason, _) in CASES.items():
    assert state.main(["mark", repo, "dnc", "--reason", reason]) == 0
for repo, (_, liftable) in CASES.items():
    assert state.main(["mark", repo, "new"]) == state.REFUSED, repo  # no flag: still permanent
    assert (state.main(["mark", repo, "new", "--lift-cla"]) == 0) == liftable, repo

# A maintainer rejection is never lifted, even if the reason later mentions a CLA.
st = state.load()
st["items"].append({"id": "pb-0001", "repo": "a/rej", "status": "rejected"})
st["repos"]["a/rej"] = {"status": "dnc", "reason": "requires CLA"}
state.save(st)
assert state.main(["mark", "a/rej", "new", "--lift-cla"]) == state.REFUSED
assert state.main(["mark", "a/cla2", "dnc", "--reason", "requires CLA"]) == 0
assert state.main(["mark", "a/cla2", "trusted", "--lift-cla"]) == state.REFUSED  # only back to new
print("ok")
