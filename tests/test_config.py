from __future__ import annotations

import unittest
from pathlib import Path

from app.config import load_settings, redact_url


class ConfigTests(unittest.TestCase):
    def test_redact_url_hides_password(self) -> None:
        url = "postgresql://user:secret@example.com:5432/db?sslmode=require"

        redacted = redact_url(url)

        self.assertEqual("postgresql://user:***@example.com:5432/db?sslmode=require", redacted)
        self.assertNotIn("secret", redacted)

    def test_redact_url_leaves_url_without_password(self) -> None:
        url = "postgresql://example.com/db"

        self.assertEqual(url, redact_url(url))

    def test_empty_openai_model_does_not_override_default_llm_model(self) -> None:
        path = Path("test.env")
        path.write_text("OPENAI_MODEL=\nLLM_MODEL=\n", encoding="utf-8")
        try:
            settings = load_settings(path)
        finally:
            path.unlink()

        self.assertEqual("deepseek-chat", settings.llm_model)

    def test_market_codes_load_from_env(self) -> None:
        path = Path("test.env")
        path.write_text("MARKET_STOCK_CODES=000001,600000\nMARKET_INDEX_CODES=sh000001\n", encoding="utf-8")
        try:
            settings = load_settings(path)
        finally:
            path.unlink()

        self.assertEqual("000001,600000", settings.market_stock_codes)
        self.assertEqual("sh000001", settings.market_index_codes)

    def test_embedding_api_key_can_fall_back_to_openai_key(self) -> None:
        path = Path("test.env")
        path.write_text("OPENAI_API_KEY=key\nEMBEDDING_MODEL=model\nEMBEDDING_DIMENSION=1024\n", encoding="utf-8")
        try:
            settings = load_settings(path)
        finally:
            path.unlink()

        self.assertEqual("key", settings.embedding_api_key)
        self.assertEqual("model", settings.embedding_model)
        self.assertEqual("openai-compatible", settings.embedding_provider)
        self.assertEqual(1024, settings.embedding_dimension)

    def test_qdrant_api_key_loads_from_env(self) -> None:
        path = Path("test.env")
        path.write_text("QDRANT_API_KEY=qdrant-key\n", encoding="utf-8")
        try:
            settings = load_settings(path)
        finally:
            path.unlink()

        self.assertEqual("qdrant-key", settings.qdrant_api_key)


if __name__ == "__main__":
    unittest.main()
