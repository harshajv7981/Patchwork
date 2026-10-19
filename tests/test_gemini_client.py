import unittest

import httpx

from app.llm_client import GeminiClient


def _client(handler):
    client = GeminiClient(transport=httpx.MockTransport(handler))
    client.api_key = "test-key"
    return client


class GeminiClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_shaped_error_surfaces_the_real_message(self):
        # Gemini returns errors as a single-element list; the client must read the
        # message out of it, not crash with AttributeError and hide it.
        def handler(request):
            return httpx.Response(404, json=[{"error": {"code": 404, "message": "model X is no longer available"}}])

        with self.assertRaises(RuntimeError) as ctx:
            await _client(handler).generate(model="x", prompt="hi", options={"num_predict": 8})
        self.assertIn("no longer available", str(ctx.exception))

    async def test_successful_completion_is_parsed(self):
        def handler(request):
            return httpx.Response(200, json={"model": "m", "choices": [{"message": {"content": "hello"}}]})

        result = await _client(handler).generate(model="m", prompt="hi", options={"num_predict": 8})
        self.assertEqual(result.response, "hello")


if __name__ == "__main__":
    unittest.main()
