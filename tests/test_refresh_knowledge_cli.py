from __future__ import annotations

import unittest
from unittest.mock import patch

from app.main import refresh_knowledge_command


class RefreshKnowledgeCliTests(unittest.TestCase):
    def test_refresh_knowledge_runs_notion_build_and_vector_sync(self) -> None:
        calls = []

        def fake_sync_notion():
            calls.append(("sync-notion", None))
            return 0

        def fake_build_index(args):
            calls.append(("build-index", args))
            return 0

        def fake_sync_vector(args):
            calls.append(("sync-vector-index", args))
            return 0

        with (
            patch("app.main.sync_notion_command", side_effect=fake_sync_notion),
            patch("app.main.build_index_command", side_effect=fake_build_index),
            patch("app.main.sync_vector_index_command", side_effect=fake_sync_vector),
        ):
            result = refresh_knowledge_command()

        self.assertEqual(0, result)
        self.assertEqual(["sync-notion", "build-index", "sync-vector-index"], [name for name, _ in calls])
        self.assertEqual("notion", calls[1][1].source)
        self.assertEqual("note", calls[1][1].doc_type)
        self.assertEqual("pending", calls[2][1].embedding_status)


if __name__ == "__main__":
    unittest.main()
