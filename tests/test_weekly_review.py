from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from unittest.mock import patch

from analysis.weekly import WeeklyReviewSummary, build_experience_candidates, build_weekly_review
from app.config import Settings
from app.main import weekly_review_command
from storage.models import Observation


@contextmanager
def fake_connect(settings):
    yield object()


class FakeObservationRepository:
    listed: list[Observation] = []

    def __init__(self, connection) -> None:
        self.connection = connection

    def list(self, query):
        self.__class__.last_query = query
        return self.__class__.listed


class WeeklyReviewTests(unittest.TestCase):
    def tearDown(self) -> None:
        FakeObservationRepository.listed = []

    def test_build_weekly_review_summarizes_statuses(self) -> None:
        observations = [
            Observation(
                trade_date=date(2026, 6, 10),
                report_type="pre_market",
                theme="AI",
                hypothesis="AI 加强。",
                validation_condition="放量。",
                invalid_condition="无跟随。",
                priority="A",
                status="hit",
                outcome="成立",
                review_note="核心票未回落",
            ),
            Observation(
                trade_date=date(2026, 6, 11),
                report_type="pre_market",
                theme="地产",
                hypothesis="地产修复。",
                validation_condition="放量。",
                invalid_condition="无跟随。",
                priority="B",
                status="miss",
                outcome="不成立",
                review_note="板块无跟随",
            ),
            Observation(
                trade_date=date(2026, 6, 8),
                report_type="pre_market",
                theme="机器人",
                hypothesis="机器人修复。",
                validation_condition="放量。",
                invalid_condition="无跟随。",
                priority="B",
                status="pending",
            ),
        ]

        report = build_weekly_review(
            WeeklyReviewSummary(
                start_date=date(2026, 6, 8),
                end_date=date(2026, 6, 13),
                observations=observations,
                generated_at=__import__("datetime").datetime(2026, 6, 13, 20, 30, 0),
            )
        )

        self.assertIn("# 2026-06-08_2026-06-13 周度复盘", report)
        self.assertIn("命中率：50%", report)
        self.assertIn("## 命中观察", report)
        self.assertIn("## 误判观察", report)
        self.assertIn("## 陈旧观察", report)
        self.assertIn("机器人", report)
        self.assertIn("有效方向：AI(1)", report)
        self.assertIn("误判方向：地产(1)", report)
        self.assertIn("## 可沉淀条目", report)
        self.assertIn("有效样本 | AI", report)
        self.assertIn("误判样本 | 地产", report)
        self.assertIn("多次重复验证后再考虑更新 stock-review", report)

    def test_weekly_review_command_writes_report(self) -> None:
        FakeObservationRepository.listed = [
            Observation(
                trade_date=date(2026, 6, 10),
                report_type="pre_market",
                theme="AI",
                hypothesis="AI 加强。",
                validation_condition="放量。",
                invalid_condition="无跟随。",
                priority="A",
                status="hit",
            )
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            args = Namespace(start_date="2026-06-08", end_date="2026-06-13", limit=500)
            with patch("app.main.load_settings", return_value=Settings(report_output_dir=temp_dir)), patch("app.main.setup_logging"), patch(
                "storage.db.connect",
                fake_connect,
            ), patch("storage.repositories.ObservationRepository", FakeObservationRepository), patch("builtins.print"):
                exit_code = weekly_review_command(args)

            self.assertEqual(0, exit_code)
            self.assertEqual(date(2026, 6, 8), FakeObservationRepository.last_query.start_date)
            self.assertEqual(date(2026, 6, 13), FakeObservationRepository.last_query.end_date)
            report_path = Path(temp_dir) / "2026-06-13_weekly.md"
            experience_path = Path(temp_dir) / "2026-06-13_experience_candidates.md"
            self.assertTrue(report_path.exists())
            self.assertTrue(experience_path.exists())
            self.assertIn("周度复盘", report_path.read_text(encoding="utf-8"))
            self.assertIn("经验沉淀候选", experience_path.read_text(encoding="utf-8"))

    def test_build_experience_candidates_separates_notion_and_skill(self) -> None:
        observations = [
            Observation(
                trade_date=date(2026, 6, 10),
                report_type="pre_market",
                theme="AI",
                hypothesis="AI 加强。",
                validation_condition="放量。",
                invalid_condition="无跟随。",
                priority="A",
                status="hit",
                review_note="核心票未回落",
            ),
            Observation(
                trade_date=date(2026, 6, 11),
                report_type="pre_market",
                theme="AI",
                hypothesis="AI 延续。",
                validation_condition="继续放量。",
                invalid_condition="缩量。",
                priority="A",
                status="hit",
                review_note="板块扩散",
            ),
            Observation(
                trade_date=date(2026, 6, 12),
                report_type="pre_market",
                theme="地产",
                hypothesis="地产修复。",
                validation_condition="放量。",
                invalid_condition="无跟随。",
                priority="B",
                status="miss",
                review_note="板块无跟随",
            ),
            Observation(
                trade_date=date(2026, 6, 13),
                report_type="pre_market",
                theme="泛政策新闻",
                hypothesis="缺少交易锚点。",
                validation_condition="放量。",
                invalid_condition="无跟随。",
                priority="B",
                status="invalid",
                review_note="未映射到明确热点板块/标的，暂不沉淀",
            ),
        ]

        content = build_experience_candidates(
            WeeklyReviewSummary(
                start_date=date(2026, 6, 8),
                end_date=date(2026, 6, 13),
                observations=observations,
                generated_at=__import__("datetime").datetime(2026, 6, 13, 20, 30, 0),
            )
        )

        self.assertIn("## Notion 经验候选", content)
        self.assertIn("### 有效样本 | AI | 2026-06-10", content)
        self.assertIn("### 误判样本 | 地产 | 2026-06-12", content)
        self.assertNotIn("泛政策新闻", content)
        self.assertIn("## stock-review Skill 候选", content)
        self.assertIn("AI 连续命中 2 次", content)
        self.assertIn("提升 `skills/stock-review/SKILL.md` version", content)


if __name__ == "__main__":
    unittest.main()
