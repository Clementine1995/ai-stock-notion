from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from analysis.market_context import MarketContext
from app.config import PROJECT_ROOT
from storage.models import RawDocument


EVENT_TYPES = (
    "earnings_forecast",
    "major_contract",
    "merger_acquisition",
    "share_repurchase",
    "shareholder_reduction",
    "policy_catalyst",
    "industry_news",
    "regulatory_risk",
    "other",
)

EXTRACTED_EVENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "raw_document_id",
        "source",
        "doc_type",
        "title",
        "event_type",
        "impact_direction",
        "affected_stocks",
        "affected_sectors",
        "evidence",
        "confidence",
    ],
    "properties": {
        "raw_document_id": {"type": "string"},
        "source": {"type": "string"},
        "doc_type": {"type": "string"},
        "title": {"type": "string"},
        "event_type": {"type": "string", "enum": list(EVENT_TYPES)},
        "impact_direction": {"type": "string", "enum": ["positive", "negative", "neutral", "unknown"]},
        "affected_stocks": {"type": "array", "items": {"type": "string"}},
        "affected_sectors": {"type": "array", "items": {"type": "string"}},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}


@dataclass(frozen=True)
class ExtractedEvent:
    raw_document_id: str
    source: str
    doc_type: str
    title: str
    event_type: str
    impact_direction: str
    affected_stocks: list[str]
    affected_sectors: list[str]
    evidence: list[str]
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EventScore:
    catalyst_score: int
    freshness_score: int
    expectation_gap_score: int
    sector_spread_score: int
    liquidity_score: int
    risk_score: int
    priority: str
    rationale: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_event(document: RawDocument, sector_keywords: dict[str, list[str]] | None = None) -> ExtractedEvent:
    active_sector_keywords = sector_keywords if sector_keywords is not None else load_sector_keywords()
    text = " ".join(value for value in (document.title, document.content) if value)
    event_type = classify_event_type(document, text)
    impact_direction = classify_impact_direction(event_type, text)
    affected_sectors = map_sectors(text, active_sector_keywords)
    affected_stocks = [document.stock_code] if document.stock_code else []
    evidence = build_evidence(document, event_type, affected_sectors)
    confidence = estimate_confidence(document, event_type, affected_sectors, evidence)
    return ExtractedEvent(
        raw_document_id=document.id,
        source=document.source,
        doc_type=document.doc_type,
        title=document.title,
        event_type=event_type,
        impact_direction=impact_direction,
        affected_stocks=affected_stocks,
        affected_sectors=affected_sectors,
        evidence=evidence,
        confidence=confidence,
    )


def score_event(event: ExtractedEvent, market_context: MarketContext | None = None, now: datetime | None = None) -> EventScore:
    catalyst_score = catalyst_score_for(event)
    risk_score = risk_score_for(event)
    freshness_score = 3
    if now is not None:
        freshness_score = 4
    sector_spread_score = sector_score_for(event, market_context)
    liquidity_score = liquidity_score_for(event, market_context)
    expectation_gap_score = expectation_score_for(event, sector_spread_score, liquidity_score)
    rationale = build_score_rationale(event, market_context, sector_spread_score, liquidity_score)
    priority = classify_priority(catalyst_score, expectation_gap_score, risk_score, event.confidence)
    if not has_tradeable_anchor(event):
        priority = "C"
        rationale.append("no_tradeable_anchor")
    return EventScore(
        catalyst_score=catalyst_score,
        freshness_score=freshness_score,
        expectation_gap_score=expectation_gap_score,
        sector_spread_score=sector_spread_score,
        liquidity_score=liquidity_score,
        risk_score=risk_score,
        priority=priority,
        rationale=rationale,
    )


def has_tradeable_anchor(event: ExtractedEvent) -> bool:
    return bool(event.affected_stocks or event.affected_sectors)


def classify_event_type(document: RawDocument, text: str) -> str:
    category = str(document.metadata.get("announcement_category") or "")
    active_text = f"{category} {text}"
    if contains_any(active_text, ("问询", "监管", "处罚", "立案", "风险提示")):
        return "regulatory_risk"
    if contains_any(active_text, ("减持", "解禁")):
        return "shareholder_reduction"
    if contains_any(active_text, ("回购",)):
        return "share_repurchase"
    if contains_any(active_text, ("重组", "并购", "收购", "资产购买")):
        return "merger_acquisition"
    if contains_any(active_text, ("重大合同", "签订合同", "中标", "订单")):
        return "major_contract"
    if contains_any(active_text, ("业绩预告", "预增", "预减", "扭亏", "年度报告", "季报", "半年报")):
        return "earnings_forecast"
    if contains_any(active_text, ("政策", "国务院", "工信部", "发改委", "规划", "支持")):
        return "policy_catalyst"
    if document.doc_type == "news":
        return "industry_news"
    return "other"


def classify_impact_direction(event_type: str, text: str) -> str:
    if event_type in {"shareholder_reduction", "regulatory_risk"}:
        return "negative"
    if contains_any(text, ("预减", "亏损", "下滑", "处罚", "立案", "减持")):
        return "negative"
    if event_type in {"earnings_forecast", "major_contract", "merger_acquisition", "share_repurchase", "policy_catalyst", "industry_news"}:
        return "positive"
    return "unknown"


def build_evidence(document: RawDocument, event_type: str, affected_sectors: list[str]) -> list[str]:
    evidence = [f"title:{document.title}", f"event_type:{event_type}"]
    if document.stock_code:
        evidence.append(f"stock:{document.stock_code}")
    if affected_sectors:
        evidence.append("sectors:" + ",".join(affected_sectors))
    return evidence


def estimate_confidence(document: RawDocument, event_type: str, affected_sectors: list[str], evidence: list[str]) -> float:
    score = 0.45
    if event_type != "other":
        score += 0.25
    if document.stock_code:
        score += 0.1
    if affected_sectors:
        score += 0.1
    if len(evidence) >= 2:
        score += 0.05
    return min(score, 0.95)


def catalyst_score_for(event: ExtractedEvent) -> int:
    if event.event_type in {"major_contract", "policy_catalyst", "merger_acquisition"}:
        return 4
    if event.event_type in {"earnings_forecast", "share_repurchase", "industry_news"}:
        return 3
    if event.event_type in {"shareholder_reduction", "regulatory_risk"}:
        return 1
    return 2


def risk_score_for(event: ExtractedEvent) -> int:
    if event.event_type in {"shareholder_reduction", "regulatory_risk"} or event.impact_direction == "negative":
        return 5
    if event.confidence < 0.6:
        return 4
    return 2


def sector_score_for(event: ExtractedEvent, market_context: MarketContext | None) -> int:
    if market_context is None:
        return 3
    if not event.affected_sectors:
        return 2
    hot_sectors = {item.sector for item in market_context.sector_hotspots[:3]}
    return 4 if any(sector in hot_sectors for sector in event.affected_sectors) else 2


def liquidity_score_for(event: ExtractedEvent, market_context: MarketContext | None) -> int:
    if market_context is None:
        return 3
    if market_context.amount_tier.startswith("above_2t"):
        return 5
    if market_context.amount_tier.startswith("above_1t"):
        return 4
    if market_context.amount_tier.startswith("below_1t"):
        return 2
    return 1


def expectation_score_for(event: ExtractedEvent, sector_spread_score: int, liquidity_score: int) -> int:
    if event.impact_direction == "negative":
        return 1
    base = 2
    if event.event_type in {"major_contract", "policy_catalyst", "merger_acquisition"}:
        base += 1
    if sector_spread_score >= 4:
        base += 1
    if liquidity_score >= 4:
        base += 1
    return min(base, 5)


def classify_priority(catalyst_score: int, expectation_gap_score: int, risk_score: int, confidence: float) -> str:
    if risk_score >= 5 or confidence < 0.6:
        return "C"
    if catalyst_score >= 4 and expectation_gap_score >= 4 and risk_score <= 3:
        return "A"
    if catalyst_score >= 3 and expectation_gap_score >= 3:
        return "B"
    return "C"


def build_score_rationale(
    event: ExtractedEvent,
    market_context: MarketContext | None,
    sector_spread_score: int,
    liquidity_score: int,
) -> list[str]:
    rationale = [f"event_type={event.event_type}", f"impact={event.impact_direction}"]
    if market_context is None:
        rationale.append("market_context=missing")
    else:
        rationale.append(f"amount_tier={market_context.amount_tier}")
        if market_context.evidence_gaps:
            rationale.append("evidence_gaps=" + ",".join(market_context.evidence_gaps))
    rationale.append(f"sector_spread_score={sector_spread_score}")
    rationale.append(f"liquidity_score={liquidity_score}")
    return rationale


def map_sectors(text: str, sector_keywords: dict[str, list[str]]) -> list[str]:
    sectors = []
    for sector, keywords in sector_keywords.items():
        if contains_any(text, tuple(keywords)):
            sectors.append(sector)
    return sectors


def load_sector_keywords(path: Path | None = None) -> dict[str, list[str]]:
    active_path = path or PROJECT_ROOT / "config" / "sector_keywords.yaml"
    if not active_path.exists():
        return {}
    return parse_simple_sector_yaml(active_path.read_text(encoding="utf-8"))


def parse_simple_sector_yaml(raw: str) -> dict[str, list[str]]:
    sectors: dict[str, list[str]] = {}
    current_sector = ""
    for raw_line in raw.splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and line.endswith(":"):
            current_sector = line[:-1].strip()
            sectors[current_sector] = []
            continue
        stripped = line.strip()
        if current_sector and stripped.startswith("- "):
            sectors[current_sector].append(stripped[2:].strip())
    return sectors


def contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword and keyword in text for keyword in keywords)
