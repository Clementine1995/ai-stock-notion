from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from analysis.events import EventScore, ExtractedEvent
from analysis.market_context import MarketContext, MarketInstrumentSummary, SectorHotspot
from analysis.observations import ObservationCandidate
from app.config import Settings
from app.main import normalize_cli_report_type, report_command
from app.reports import ScoredEvent, build_after_close_report, build_noon_report, build_pre_market_report, write_report
from app.skills import Skill
from storage.models import RawDocument


class ReportTests(unittest.TestCase):
    def test_normalize_cli_report_type(self) -> None:
        self.assertEqual("after_close", normalize_cli_report_type("after-close"))
        self.assertEqual("pre_market", normalize_cli_report_type("pre-market"))
        self.assertEqual("noon", normalize_cli_report_type("noon"))

    def test_build_after_close_report_renders_required_sections(self) -> None:
        trade_date = date(2026, 6, 12)
        market_context = MarketContext(
            trade_date=trade_date,
            snapshot_count=10,
            stock_count=8,
            index_count=2,
            observed_total_amount=980_000_000_000,
            amount_tier="below_1t_watch_small_caps_or_shrinking_liquidity",
            indexes=[MarketInstrumentSummary(code="sh000001", name="上证指数", pct_chg=-0.32, amount=None, turnover_rate=None, source="akshare")],
            strong_stocks=[MarketInstrumentSummary(code="000001", name="平安银行", pct_chg=4.51, amount=12_300_000_000, turnover_rate=None, source="akshare")],
            weak_stocks=[MarketInstrumentSummary(code="000002", name="万科A", pct_chg=-5.12, amount=8_500_000_000, turnover_rate=None, source="akshare")],
            volume_leaders=[MarketInstrumentSummary(code="000001", name="平安银行", pct_chg=4.51, amount=12_300_000_000, turnover_rate=None, source="akshare")],
            sector_hotspots=[SectorHotspot(sector="AI", stock_count=5, average_pct_chg=3.2, total_amount=320_000_000_000)],
            market_style="unknown",
            sentiment_cycle="unknown",
            evidence_gaps=["missing_sector_mapping"],
        )
        scored_events = [
            ScoredEvent(
                event=ExtractedEvent(
                    raw_document_id="doc-1",
                    source="akshare",
                    doc_type="announcement",
                    title="某公司签订重大合同",
                    event_type="major_contract",
                    impact_direction="positive",
                    affected_stocks=["000001"],
                    affected_sectors=["AI"],
                    evidence=["title:某公司签订重大合同", "stock:000001", "sectors:AI"],
                    confidence=0.9,
                ),
                score=EventScore(
                    catalyst_score=4,
                    freshness_score=3,
                    expectation_gap_score=4,
                    sector_spread_score=4,
                    liquidity_score=2,
                    risk_score=2,
                    priority="A",
                    rationale=["amount_tier=below_1t_watch_small_caps_or_shrinking_liquidity"],
                ),
            )
        ]
        observations = [
            ObservationCandidate(
                trade_date=trade_date,
                report_type="after_close",
                theme="AI",
                related_stocks=["000001"],
                hypothesis="AI 可能受 major_contract 催化，需要观察是否获得板块和量能确认。",
                validation_condition="相关板块或标的成交额放大，核心标的高开不回落，且板块有跟随。",
                invalid_condition="相关标的低开低走，板块无跟随，或成交额缩量导致催化无法延续。",
                priority="A",
                status="pending",
                source_event_ids=["doc-1"],
                evidence=["title:某公司签订重大合同", "sectors:AI"],
            )
        ]

        report = build_after_close_report(
            trade_date,
            market_context,
            scored_events,
            observations,
            stock_review_skill=Skill(
                name="stock-review",
                description="desc",
                path=Path("skills/stock-review/SKILL.md"),
                body="body",
                version="1.2",
            ),
            generated_at=datetime(2026, 6, 12, 15, 30, 0),
        )

        self.assertIn("# 2026-06-12 盘后复盘报告", report)
        self.assertIn("## 市场概况", report)
        self.assertIn("## 情绪指标", report)
        self.assertIn("## 强势板块", report)
        self.assertIn("## 弱势板块", report)
        self.assertIn("## 重要公告和新闻", report)
        self.assertIn("## 今日推演验证", report)
        self.assertIn("## 明日观察方向", report)
        self.assertIn("## 风险清单", report)
        self.assertIn("Observation 入库和回填尚未接入", report)
        self.assertIn("核心票锚点：000001 平安银行", report)
        assert_no_unconditional_trade_instruction(self, report)

    def test_build_noon_report_renders_required_sections(self) -> None:
        trade_date = date(2026, 6, 12)
        market_context = MarketContext(
            trade_date=trade_date,
            snapshot_count=10,
            stock_count=8,
            index_count=2,
            observed_total_amount=620_000_000_000,
            amount_tier="below_1t_watch_small_caps_or_shrinking_liquidity",
            indexes=[MarketInstrumentSummary(code="sh000001", name="上证指数", pct_chg=0.12, amount=None, turnover_rate=None, source="akshare")],
            strong_stocks=[MarketInstrumentSummary(code="000001", name="平安银行", pct_chg=4.51, amount=12_300_000_000, turnover_rate=None, source="akshare")],
            weak_stocks=[MarketInstrumentSummary(code="000002", name="万科A", pct_chg=-5.12, amount=8_500_000_000, turnover_rate=None, source="akshare")],
            volume_leaders=[MarketInstrumentSummary(code="000001", name="平安银行", pct_chg=4.51, amount=12_300_000_000, turnover_rate=None, source="akshare")],
            sector_hotspots=[SectorHotspot(sector="AI", stock_count=5, average_pct_chg=3.2, total_amount=320_000_000_000)],
            market_style="unknown",
            sentiment_cycle="unknown",
            evidence_gaps=[],
        )
        scored_events = [
            ScoredEvent(
                event=ExtractedEvent(
                    raw_document_id="doc-1",
                    source="akshare",
                    doc_type="announcement",
                    title="某公司签订重大合同",
                    event_type="major_contract",
                    impact_direction="positive",
                    affected_stocks=["000001"],
                    affected_sectors=["AI"],
                    evidence=["title:某公司签订重大合同", "stock:000001", "sectors:AI"],
                    confidence=0.9,
                ),
                score=EventScore(
                    catalyst_score=4,
                    freshness_score=3,
                    expectation_gap_score=4,
                    sector_spread_score=4,
                    liquidity_score=2,
                    risk_score=2,
                    priority="A",
                    rationale=["amount_tier=below_1t_watch_small_caps_or_shrinking_liquidity"],
                ),
            ),
            ScoredEvent(
                event=ExtractedEvent(
                    raw_document_id="doc-2",
                    source="akshare",
                    doc_type="announcement",
                    title="某股东拟减持公司股份",
                    event_type="shareholder_reduction",
                    impact_direction="negative",
                    affected_stocks=["000002"],
                    affected_sectors=[],
                    evidence=["title:某股东拟减持公司股份", "stock:000002"],
                    confidence=0.8,
                ),
                score=EventScore(
                    catalyst_score=1,
                    freshness_score=3,
                    expectation_gap_score=1,
                    sector_spread_score=2,
                    liquidity_score=2,
                    risk_score=5,
                    priority="C",
                    rationale=["event_type=shareholder_reduction"],
                ),
            ),
        ]
        observations = [
            ObservationCandidate(
                trade_date=trade_date,
                report_type="noon",
                theme="AI",
                related_stocks=["000001"],
                hypothesis="AI 可能受 major_contract 催化，需要观察是否获得板块和量能确认。",
                validation_condition="相关板块或标的成交额放大，核心标的高开不回落，且板块有跟随。",
                invalid_condition="相关标的低开低走，板块无跟随，或成交额缩量导致催化无法延续。",
                priority="A",
                status="pending",
                source_event_ids=["doc-1"],
                evidence=["title:某公司签订重大合同", "sectors:AI"],
            )
        ]

        report = build_noon_report(
            trade_date,
            market_context,
            scored_events,
            observations,
            stock_review_skill=Skill(
                name="stock-review",
                description="desc",
                path=Path("skills/stock-review/SKILL.md"),
                body="body",
                version="1.2",
            ),
            generated_at=datetime(2026, 6, 12, 12, 10, 0),
        )

        self.assertIn("# 2026-06-12 午间复盘报告", report)
        self.assertIn("## 上午市场与盘前推演对比", report)
        self.assertIn("## 主线状态", report)
        self.assertIn("## 下午机会", report)
        self.assertIn("## 下午风险", report)
        self.assertIn("## 降低关注方向", report)
        self.assertIn("## 重要公告和新闻", report)
        self.assertIn("某股东拟减持公司股份", report)
        self.assertIn("Observation 入库和盘前观察项读取尚未接入", report)
        assert_no_unconditional_trade_instruction(self, report)

    def test_build_pre_market_report_renders_required_sections(self) -> None:
        trade_date = date(2026, 6, 12)
        market_context = MarketContext(
            trade_date=trade_date,
            snapshot_count=10,
            stock_count=8,
            index_count=2,
            observed_total_amount=1_230_000_000_000,
            amount_tier="above_1t_supports_one_main_sector",
            indexes=[MarketInstrumentSummary(code="sh000001", name="上证指数", pct_chg=0.82, amount=None, turnover_rate=None, source="akshare")],
            strong_stocks=[MarketInstrumentSummary(code="000001", name="平安银行", pct_chg=4.51, amount=12_300_000_000, turnover_rate=None, source="akshare")],
            weak_stocks=[],
            volume_leaders=[],
            sector_hotspots=[SectorHotspot(sector="AI", stock_count=5, average_pct_chg=3.2, total_amount=320_000_000_000)],
            market_style="unknown",
            sentiment_cycle="unknown",
            evidence_gaps=["missing_index_snapshots"],
        )
        scored_events = [
            ScoredEvent(
                event=ExtractedEvent(
                    raw_document_id="doc-1",
                    source="akshare",
                    doc_type="announcement",
                    title="某公司签订重大合同",
                    event_type="major_contract",
                    impact_direction="positive",
                    affected_stocks=["000001"],
                    affected_sectors=["AI"],
                    evidence=["title:某公司签订重大合同", "stock:000001", "sectors:AI"],
                    confidence=0.9,
                ),
                score=EventScore(
                    catalyst_score=4,
                    freshness_score=3,
                    expectation_gap_score=4,
                    sector_spread_score=4,
                    liquidity_score=4,
                    risk_score=2,
                    priority="A",
                    rationale=["amount_tier=above_1t_supports_one_main_sector"],
                ),
            ),
            ScoredEvent(
                event=ExtractedEvent(
                    raw_document_id="doc-2",
                    source="akshare",
                    doc_type="announcement",
                    title="某股东拟减持公司股份",
                    event_type="shareholder_reduction",
                    impact_direction="negative",
                    affected_stocks=["000002"],
                    affected_sectors=[],
                    evidence=["title:某股东拟减持公司股份", "stock:000002"],
                    confidence=0.8,
                ),
                score=EventScore(
                    catalyst_score=1,
                    freshness_score=3,
                    expectation_gap_score=1,
                    sector_spread_score=2,
                    liquidity_score=4,
                    risk_score=5,
                    priority="C",
                    rationale=["event_type=shareholder_reduction"],
                ),
            )
        ]
        observations = [
            ObservationCandidate(
                trade_date=trade_date,
                report_type="pre_market",
                theme="AI",
                related_stocks=["000001"],
                hypothesis="AI 可能受 major_contract 催化，需要观察是否获得板块和量能确认。",
                validation_condition="相关板块或标的成交额放大，核心标的高开不回落，且板块有跟随。",
                invalid_condition="相关标的低开低走，板块无跟随，或成交额缩量导致催化无法延续。",
                priority="A",
                status="pending",
                source_event_ids=["doc-1"],
                evidence=["title:某公司签订重大合同", "sectors:AI", "amount_tier=above_1t_supports_one_main_sector"],
            )
        ]

        report = build_pre_market_report(
            trade_date,
            market_context,
            scored_events,
            observations,
            stock_review_skill=Skill(
                name="stock-review",
                description="desc",
                path=Path("skills/stock-review/SKILL.md"),
                body="body",
                version="1.2",
            ),
            generated_at=datetime(2026, 6, 12, 8, 15, 0),
        )

        self.assertIn("# 2026-06-12 盘前报告", report)
        self.assertIn("框架依据：stock-review v1.2", report)
        self.assertIn("## 市场概况", report)
        self.assertIn("## 资讯总结", report)
        self.assertIn("## 价值投机线索", report)
        self.assertIn("## 重点观察项", report)
        self.assertIn("## 风险提示", report)
        self.assertIn("某股东拟减持公司股份", report)
        self.assertIn("价值投机判断", report)
        self.assertIn("核心票锚点：000001 平安银行", report)
        self.assertIn("弹性票候选：从同主题低位、放量、主动跟随标的中筛选", report)
        self.assertIn("复盘验证点", report)
        self.assertIn("开盘验证条件", report)
        self.assertIn("失效条件", report)
        self.assertIn("missing_index_snapshots", report)
        assert_no_unconditional_trade_instruction(self, report)

    def test_write_report_uses_documented_filename(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = write_report(temp_dir, date(2026, 6, 12), "pre_market", "# report\n")

            self.assertTrue(path.exists())
            self.assertEqual("2026-06-12_pre_market.md", path.name)
            self.assertEqual("# report\n", path.read_text(encoding="utf-8"))

    def test_report_command_generates_pre_market_file(self) -> None:
        trade_date = date(2026, 6, 12)
        market_context = MarketContext(
            trade_date=trade_date,
            snapshot_count=2,
            stock_count=1,
            index_count=1,
            observed_total_amount=1_230_000_000_000,
            amount_tier="above_1t_supports_one_main_sector",
            indexes=[MarketInstrumentSummary(code="sh000001", name="上证指数", pct_chg=0.82, amount=None, turnover_rate=None, source="akshare")],
            strong_stocks=[MarketInstrumentSummary(code="000001", name="平安银行", pct_chg=4.51, amount=12_300_000_000, turnover_rate=None, source="akshare")],
            weak_stocks=[],
            volume_leaders=[],
            sector_hotspots=[SectorHotspot(sector="AI", stock_count=5, average_pct_chg=3.2, total_amount=320_000_000_000)],
            market_style="unknown",
            sentiment_cycle="unknown",
            evidence_gaps=[],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings(report_output_dir=temp_dir)
            args = Namespace(report_type="pre-market", date="2026-06-12")
            with patch("app.main.load_settings", return_value=settings), patch("app.main.setup_logging"), patch(
                "app.main.load_documents_and_market_context_for_filters",
                return_value=(
                    [
                        RawDocument(
                            id="doc-1",
                            source="akshare",
                            doc_type="announcement",
                            title="某公司签订重大合同",
                            content="算力数据中心建设",
                            stock_code="000001",
                            content_hash="hash",
                        )
                    ],
                    market_context,
                ),
            ), patch(
                "app.skills.load_skill",
                return_value=Skill(
                    name="stock-review",
                    description="desc",
                    path=Path("skills/stock-review/SKILL.md"),
                    body="body",
                    version="1.2",
                ),
            ), patch("builtins.print"):
                exit_code = report_command(args)

            self.assertEqual(0, exit_code)
            report_path = Path(temp_dir) / "2026-06-12_pre_market.md"
            self.assertTrue(report_path.exists())
            content = report_path.read_text(encoding="utf-8")
            self.assertIn("某公司签订重大合同", content)
            self.assertIn("## 重点观察项", content)

    def test_report_command_generates_after_close_file(self) -> None:
        trade_date = date(2026, 6, 12)
        market_context = MarketContext(
            trade_date=trade_date,
            snapshot_count=2,
            stock_count=1,
            index_count=1,
            observed_total_amount=1_230_000_000_000,
            amount_tier="above_1t_supports_one_main_sector",
            indexes=[MarketInstrumentSummary(code="sh000001", name="上证指数", pct_chg=0.82, amount=None, turnover_rate=None, source="akshare")],
            strong_stocks=[MarketInstrumentSummary(code="000001", name="平安银行", pct_chg=4.51, amount=12_300_000_000, turnover_rate=None, source="akshare")],
            weak_stocks=[],
            volume_leaders=[],
            sector_hotspots=[SectorHotspot(sector="AI", stock_count=5, average_pct_chg=3.2, total_amount=320_000_000_000)],
            market_style="unknown",
            sentiment_cycle="unknown",
            evidence_gaps=[],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings(report_output_dir=temp_dir)
            args = Namespace(report_type="after-close", date="2026-06-12")
            with patch("app.main.load_settings", return_value=settings), patch("app.main.setup_logging"), patch(
                "app.main.load_documents_and_market_context_for_filters",
                return_value=(
                    [
                        RawDocument(
                            id="doc-1",
                            source="akshare",
                            doc_type="announcement",
                            title="某公司签订重大合同",
                            content="算力数据中心建设",
                            stock_code="000001",
                            content_hash="hash",
                        )
                    ],
                    market_context,
                ),
            ), patch(
                "app.skills.load_skill",
                return_value=Skill(
                    name="stock-review",
                    description="desc",
                    path=Path("skills/stock-review/SKILL.md"),
                    body="body",
                    version="1.2",
                ),
            ), patch("builtins.print"):
                exit_code = report_command(args)

            self.assertEqual(0, exit_code)
            report_path = Path(temp_dir) / "2026-06-12_after_close.md"
            self.assertTrue(report_path.exists())
            content = report_path.read_text(encoding="utf-8")
            self.assertIn("盘后复盘报告", content)
            self.assertIn("## 明日观察方向", content)

    def test_report_command_generates_noon_file(self) -> None:
        trade_date = date(2026, 6, 12)
        market_context = MarketContext(
            trade_date=trade_date,
            snapshot_count=2,
            stock_count=1,
            index_count=1,
            observed_total_amount=1_230_000_000_000,
            amount_tier="above_1t_supports_one_main_sector",
            indexes=[MarketInstrumentSummary(code="sh000001", name="上证指数", pct_chg=0.82, amount=None, turnover_rate=None, source="akshare")],
            strong_stocks=[MarketInstrumentSummary(code="000001", name="平安银行", pct_chg=4.51, amount=12_300_000_000, turnover_rate=None, source="akshare")],
            weak_stocks=[],
            volume_leaders=[],
            sector_hotspots=[SectorHotspot(sector="AI", stock_count=5, average_pct_chg=3.2, total_amount=320_000_000_000)],
            market_style="unknown",
            sentiment_cycle="unknown",
            evidence_gaps=[],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings(report_output_dir=temp_dir)
            args = Namespace(report_type="noon", date="2026-06-12")
            with patch("app.main.load_settings", return_value=settings), patch("app.main.setup_logging"), patch(
                "app.main.load_documents_and_market_context_for_filters",
                return_value=(
                    [
                        RawDocument(
                            id="doc-1",
                            source="akshare",
                            doc_type="announcement",
                            title="某公司签订重大合同",
                            content="算力数据中心建设",
                            stock_code="000001",
                            content_hash="hash",
                        )
                    ],
                    market_context,
                ),
            ), patch(
                "app.skills.load_skill",
                return_value=Skill(
                    name="stock-review",
                    description="desc",
                    path=Path("skills/stock-review/SKILL.md"),
                    body="body",
                    version="1.2",
                ),
            ), patch("builtins.print"):
                exit_code = report_command(args)

            self.assertEqual(0, exit_code)
            report_path = Path(temp_dir) / "2026-06-12_noon.md"
            self.assertTrue(report_path.exists())
            content = report_path.read_text(encoding="utf-8")
            self.assertIn("午间复盘报告", content)
            self.assertIn("## 下午机会", content)


def assert_no_unconditional_trade_instruction(test_case: unittest.TestCase, report: str) -> None:
    for keyword in ("买入", "卖出", "建仓", "清仓"):
        test_case.assertNotIn(keyword, report)


if __name__ == "__main__":
    unittest.main()
