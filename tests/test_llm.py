from __future__ import annotations

import unittest

from analysis.llm import ChatMessage, LLMError, build_chat_payload, parse_chat_text


class LLMTests(unittest.TestCase):
    def test_build_chat_payload(self) -> None:
        payload = build_chat_payload(
            "deepseek-chat",
            [ChatMessage(role="user", content="ping")],
            temperature=0.1,
        )

        self.assertEqual("deepseek-chat", payload["model"])
        self.assertEqual([{"role": "user", "content": "ping"}], payload["messages"])
        self.assertEqual(0.1, payload["temperature"])

    def test_parse_chat_text(self) -> None:
        content = parse_chat_text({"choices": [{"message": {"content": "pong"}}]})

        self.assertEqual("pong", content)

    def test_parse_chat_text_rejects_invalid_response(self) -> None:
        with self.assertRaises(LLMError):
            parse_chat_text({"choices": []})


if __name__ == "__main__":
    unittest.main()
