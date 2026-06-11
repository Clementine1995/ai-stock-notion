from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from analysis.events import EXTRACTED_EVENT_SCHEMA, extract_event, load_sector_keywords, parse_simple_sector_yaml, score_event
from analysis.market_context import build_market_context
from storage.models import MarketSnapshot, RawDocument


class EventAnalysisTests(unittest.TestCase):
    def test_extracted_event_schema_contains_mvp_fields(self) -> None:
        required = set(EXTRACTED_EVENT_SCHEMA["required"])

        self.assertIn("event_type", required)
        self.assertIn("impact_direction", required)
        self.assertIn("affected_sectors", required)
        self.assertIn("evidence", required)
        self.assertIn("confidence", required)
        self.assertIn("major_contract", EXTRACTED_EVENT_SCHEMA["properties"]["event_type"]["enum"])

    def test_parse_simple_sector_yaml(self) -> None:
        sectors = parse_simple_sector_yaml("AI:\n  - 算力\n  - GPU\n半导体:\n  - 光刻\n")

        self.assertEqual(["算力", "GPU"], sectors["AI"])
        self.assertEqual(["光刻"], sectors["半导体"])

    def test_load_sector_keywords_reads_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sector_keywords.yaml"
            path.write_text("金融:\n  - 银行\n", encoding="utf-8")

            sectors = load_sector_keywords(path)

        self.assertEqual({"金融": ["银行"]}, sectors)

    def test_extract_event_from_announcement_maps_type_stock_and_sector(self) -> None:
        document = RawDocument(
            id="doc-1",
            source="akshare",
            doc_type="announcement",
            title="某公司签订重大合同，涉及算力数据中心建设",
            content="Stock: 000001 平安银行\nCategory: 重大事项",
            stock_code="000001",
            stock_name="平安银行",
            content_hash="hash",
        )

        event = extract_event(document, {"AI": ["算力", "数据中心"]})

        self.assertEqual("major_contract", event.event_type)
        self.assertEqual("positive", event.impact_direction)
        self.assertEqual(["000001"], event.affected_stocks)
        self.assertEqual(["AI"], event.affected_sectors)
        self.assertGreaterEqual(event.confidence, 0.8)
        self.assertIn("title:某公司签订重大合同，涉及算力数据中心建设", event.evidence)

    def test_score_event_uses_market_context_sector_and_liquidity(self) -> None:
        trade_date = date(2026, 6, 11)
        document = RawDocument(
            id="doc-1",
            source="akshare",
            doc_type="announcement",
            title="某公司签订重大合同，涉及算力数据中心建设",
            content="content",
            stock_code="000001",
            content_hash="hash",
        )
        event = extract_event(document, {"AI": ["算力", "数据中心"]})
        market_context = build_market_context(
            [
                MarketSnapshot(
                    trade_date=trade_date,
                    code="000001",
                    name="强势股",
                    pct_chg=5.0,
                    amount=900_000_000_000,
                    source="akshare",
                    metadata={"instrument_type": "stock", "sector": "AI"},
                ),
                MarketSnapshot(
                    trade_date=trade_date,
                    code="000002",
                    name="跟随股",
                    pct_chg=3.0,
                    amount=200_000_000_000,
                    source="akshare",
                    metadata={"instrument_type": "stock", "sector": "AI"},
                ),
            ],
            trade_date,
        )

        score = score_event(event, market_context)

        self.assertEqual(4, score.catalyst_score)
        self.assertEqual(4, score.sector_spread_score)
        self.assertEqual(4, score.liquidity_score)
        self.assertEqual("A", score.priority)

    def test_negative_event_is_downgraded_by_risk(self) -> None:
        document = RawDocument(
            id="doc-1",
            source="akshare",
            doc_type="announcement",
            title="股东拟减持公司股份",
            content="content",
            stock_code="000001",
            content_hash="hash",
        )
        event = extract_event(document, {"金融": ["银行"]})

        score = score_event(event)

        self.assertEqual("shareholder_reduction", event.event_type)
        self.assertEqual("negative", event.impact_direction)
        self.assertEqual(5, score.risk_score)
        self.assertEqual("C", score.priority)


if __name__ == "__main__":
    unittest.main()
