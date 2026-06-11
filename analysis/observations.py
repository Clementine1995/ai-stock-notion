from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from analysis.events import EventScore, ExtractedEvent


@dataclass(frozen=True)
class ObservationCandidate:
    trade_date: date
    report_type: str
    theme: str
    related_stocks: list[str]
    hypothesis: str
    validation_condition: str
    invalid_condition: str
    priority: str
    status: str
    source_event_ids: list[str]
    evidence: list[str]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["trade_date"] = self.trade_date.isoformat()
        return result


def build_observation_candidate(
    event: ExtractedEvent,
    score: EventScore,
    trade_date: date,
    report_type: str = "pre_market",
) -> ObservationCandidate | None:
    if score.priority == "C":
        return None
    theme = resolve_theme(event)
    return ObservationCandidate(
        trade_date=trade_date,
        report_type=report_type,
        theme=theme,
        related_stocks=event.affected_stocks,
        hypothesis=build_hypothesis(event, theme),
        validation_condition=build_validation_condition(event),
        invalid_condition=build_invalid_condition(event),
        priority=score.priority,
        status="pending",
        source_event_ids=[event.raw_document_id],
        evidence=[*event.evidence, *score.rationale],
    )


def resolve_theme(event: ExtractedEvent) -> str:
    if event.affected_sectors:
        return event.affected_sectors[0]
    if event.affected_stocks:
        return event.affected_stocks[0]
    return event.title


def build_hypothesis(event: ExtractedEvent, theme: str) -> str:
    if event.impact_direction == "negative":
        return f"{theme} 出现风险事件，需要观察是否扩散为板块或个股压力。"
    return f"{theme} 可能受 {event.event_type} 催化，需要观察是否获得板块和量能确认。"


def build_validation_condition(event: ExtractedEvent) -> str:
    if event.impact_direction == "negative":
        return "相关标的继续走弱，板块无修复，且风险信息被市场放大。"
    return "相关板块或标的成交额放大，核心标的高开不回落，且板块有跟随。"


def build_invalid_condition(event: ExtractedEvent) -> str:
    if event.impact_direction == "negative":
        return "相关标的止跌修复，板块出现承接，且风险影响未继续扩散。"
    return "相关标的低开低走，板块无跟随，或成交额缩量导致催化无法延续。"
