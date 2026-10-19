import unittest
from pathlib import Path
from unittest.mock import patch

from app.sandbox_service import _make_sandbox_env


class SandboxEnvFilterTests(unittest.TestCase):
    def test_secrets_never_reach_the_sandbox(self):
        secrets = {
            "OPENROUTER_API_KEY": "or-x",
            "GROQ_API_KEY": "gq-x",
            "GEMINI_API_KEY": "gm-x",
            "GITHUB_TOKEN": "gh-x",
            "FOO_SECRET": "s",
            "DB_PASSWORD": "p",
            "PATH": "/usr/bin",  # a normal var must still pass through
        }
        with patch.dict("os.environ", secrets, clear=True):
            env = _make_sandbox_env(Path("."))

        for key in secrets:
            if key == "PATH":
                continue
            self.assertNotIn(key, env, f"{key} leaked into the sandbox environment")
        self.assertEqual(env.get("PATH"), "/usr/bin")


if __name__ == "__main__":
    unittest.main()
