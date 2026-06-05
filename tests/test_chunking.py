from __future__ import annotations

import unittest

from parsers.chunking import split_text


class ChunkingTests(unittest.TestCase):
    def test_split_text_keeps_short_text_as_one_chunk(self) -> None:
        chunks = split_text("第一段\n\n第二段", chunk_size=20, overlap=3)

        self.assertEqual(["第一段\n第二段"], chunks)

    def test_split_text_splits_long_paragraph_with_overlap(self) -> None:
        chunks = split_text("abcdefghij", chunk_size=4, overlap=1)

        self.assertEqual(["abcd", "defg", "ghij"], chunks)

    def test_split_text_rejects_invalid_overlap(self) -> None:
        with self.assertRaises(ValueError):
            split_text("text", chunk_size=10, overlap=10)


if __name__ == "__main__":
    unittest.main()
