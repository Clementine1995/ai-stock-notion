from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.config import Settings
from app.skills import list_skills, parse_skill_markdown, render_skill_context


class SkillTests(unittest.TestCase):
    def test_parse_skill_markdown_with_frontmatter(self) -> None:
        metadata, body = parse_skill_markdown(
            "---\nname: demo\ndescription: Demo skill\nstage: m1\n---\n\nBody text"
        )

        self.assertEqual("demo", metadata["name"])
        self.assertEqual("Demo skill", metadata["description"])
        self.assertEqual("m1", metadata["stage"])
        self.assertEqual("\nBody text", body)

    def test_list_skills_reads_skill_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "demo"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: demo\ndescription: Demo skill\n---\n\nBody text",
                encoding="utf-8",
            )

            skills = list_skills(Settings(skills_dir=temp_dir))

        self.assertEqual(1, len(skills))
        self.assertEqual("demo", skills[0].name)
        self.assertEqual("Body text", skills[0].body)

    def test_render_skill_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "demo"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: demo\ndescription: Demo skill\n---\n\nBody text",
                encoding="utf-8",
            )
            context = render_skill_context(list_skills(Settings(skills_dir=temp_dir)))

        self.assertIn("# Skill: demo", context)
        self.assertIn("Body text", context)


if __name__ == "__main__":
    unittest.main()
