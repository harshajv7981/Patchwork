import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.contribution_agent import ContributionAgent


class ApprovePullRequestTests(unittest.IsolatedAsyncioTestCase):
    async def test_pushes_sandbox_files_and_saves_pr_row(self):
        analysis_files = {"src.py": "original, unhealed"}
        sandbox_files = {"src.py": "healed", "tests/test_regression.py": "def test_x(): pass"}
        checkpoint = {
            "issue_number": 7,
            "analysis": {"pr_title": "Fix #7", "pr_body": "body", "file_rewrites": analysis_files, "analysis": "why"},
            "sandbox": {"overall_status": "passed", "file_rewrites": sandbox_files},
        }
        run = SimpleNamespace(id=1, status="awaiting_pr_approval", repository="owner/repo", updated_at=None)
        approval = SimpleNamespace(status="pending", reviewer=None, reason=None, decided_at=None)

        session = MagicMock()
        session.get = AsyncMock(return_value=run)
        session.scalar = AsyncMock(return_value=approval)
        session.scalars = AsyncMock(return_value=MagicMock(first=lambda: SimpleNamespace(output_json=json.dumps(checkpoint))))
        session.flush = AsyncMock()
        session.commit = AsyncMock()

        push = AsyncMock(return_value={"pr_url": "https://github.com/owner/repo/pull/9", "pr_number": 9, "branch": "patchwork/fix-issue-7"})
        with patch("app.contribution_agent.create_pull_request", new=push):
            pr = await ContributionAgent(session).approve_pr(1, reviewer="me")

        self.assertEqual(push.await_args.kwargs["file_rewrites"], sandbox_files)
        self.assertEqual(json.loads(pr.patch_content), sandbox_files)
        session.add.assert_called_once_with(pr)
        self.assertEqual(run.status, "monitoring_ci")
        self.assertEqual(approval.status, "approved")
        self.assertEqual(pr.number, 9)

    async def test_agent_and_ci_runs_can_reach_monitoring_ci(self):
        from app.agent_runtime import AgentRuntime

        runtime = AgentRuntime(MagicMock(flush=AsyncMock()))
        agent_run = SimpleNamespace(id=1, status="reviewing", updated_at=None)
        await runtime.request_approval(agent_run, "create_pull_request", "review passed")
        for state in ("executing", "monitoring_ci"):  # ContributionAgent.approve_pr
            await runtime.transition(agent_run, state)

        ci_run = SimpleNamespace(id=2, status="executing", updated_at=None)
        await runtime.request_approval(ci_run, "push_ci_followup", "repair ready")
        await runtime.transition(ci_run, "monitoring_ci")  # ci_agent.approve_ci_repair

        self.assertEqual((agent_run.status, ci_run.status), ("monitoring_ci", "monitoring_ci"))


if __name__ == "__main__":
    unittest.main()
