from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from analysis.events import EventScore, ExtractedEvent
from analysis.market_context import MarketContext
from analysis.observations import ObservationCandidate
from app.skills import Skill


@dataclass(frozen=True)
class ScoredEvent:
    event: ExtractedEvent
    score: EventScore


def build_pre_market_report(
    trade_date: date,
    market_context: MarketContext,
    scored_events: list[ScoredEvent],
    observations: list[ObservationCandidate],
    stock_review_skill: Skill | None = None,
    generated_at: datetime | None = None,
) -> str:
    generated_time = generated_at or datetime.now()
    lines = [
        f"# {trade_date.isoformat()} 盘前报告",
        "",
        f"- 生成时间：{generated_time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 交易日：{trade_date.isoformat()}",
    ]
    if stock_review_skill is not None:
        lines.append(f"- 框架依据：{stock_review_skill.name} v{stock_review_skill.version or 'unknown'}")
    lines.extend(
        [
            "",
            "## 市场概况",
            f"- 两市量能观察：{describe_amount_tier(market_context.amount_tier)}（观测成交额 {format_amount(market_context.observed_total_amount)}）",
            f"- 指数表现：{format_instruments(market_context.indexes[:3])}",
            f"- 强势个股：{format_instruments(market_context.strong_stocks[:5])}",
            f"- 强势板块：{format_sectors(market_context.sector_hotspots[:5])}",
            f"- 市场风格：{market_context.market_style}",
            f"- 情绪周期：{market_context.sentiment_cycle}",
        ]
    )
    if market_context.evidence_gaps:
        lines.append(f"- 证据缺口：{', '.join(market_context.evidence_gaps)}")

    sorted_events = sort_scored_events(scored_events)
    lines.extend(["", "## 资讯总结"])
    if not sorted_events:
        lines.append("- 暂无已入库公告或新闻，盘前判断需要更多依赖市场上下文和开盘反馈。")
    else:
        for item in sorted_events[:10]:
            lines.append(format_news_summary(item))

    lines.extend(["", "## 价值投机线索"])
    material_events = [item for item in sorted_events if item.score.priority in {"A", "B"}]
    if not material_events:
        lines.append("- 暂无 A/B 级催化，先把盘前重心放在量能、板块跟随和核心票强弱确认上。")
    else:
        for item in material_events[:6]:
            lines.extend(format_event_block(item))

    lines.extend(["", "## 重点观察项"])
    if not observations:
        lines.append("- 暂无候选观察项，建议等待开盘后根据量能和主线强弱重新确认。")
    else:
        for observation in sort_observations(observations):
            lines.extend(format_observation_block(observation, market_context))

    lines.extend(["", "## 风险提示"])
    risk_notes = build_risk_notes(market_context, scored_events, observations)
    if not risk_notes:
        lines.append("- 当前未识别到额外高优先级风险，仍需防止开盘一致性过高后的冲高回落。")
    else:
        for note in risk_notes:
            lines.append(f"- {note}")

    return "\n".join(lines) + "\n"


def build_after_close_report(
    trade_date: date,
    market_context: MarketContext,
    scored_events: list[ScoredEvent],
    observations: list[ObservationCandidate],
    stock_review_skill: Skill | None = None,
    generated_at: datetime | None = None,
) -> str:
    generated_time = generated_at or datetime.now()
    sorted_events = sort_scored_events(scored_events)
    lines = [
        f"# {trade_date.isoformat()} 盘后复盘报告",
        "",
        f"- 生成时间：{generated_time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 交易日：{trade_date.isoformat()}",
    ]
    if stock_review_skill is not None:
        lines.append(f"- 框架依据：{stock_review_skill.name} v{stock_review_skill.version or 'unknown'}")

    lines.extend(
        [
            "",
            "## 市场概况",
            f"- 两市量能：{describe_amount_tier(market_context.amount_tier)}（观测成交额 {format_amount(market_context.observed_total_amount)}）",
            f"- 指数表现：{format_instruments(market_context.indexes[:3])}",
            f"- 市场风格：{market_context.market_style}",
            f"- 情绪周期：{market_context.sentiment_cycle}",
            "",
            "## 情绪指标",
            f"- 强势个股：{format_instruments(market_context.strong_stocks[:8])}",
            f"- 弱势个股：{format_instruments(market_context.weak_stocks[:8])}",
            f"- 成交额前排：{format_instruments(market_context.volume_leaders[:8])}",
            "",
            "## 强势板块",
            f"- {format_sectors(market_context.sector_hotspots[:8])}",
            "",
            "## 弱势板块",
            "- 当前数据源暂未提供完整板块跌幅榜，先用弱势个股和证据缺口辅助判断。",
        ]
    )
    if market_context.evidence_gaps:
        lines.append(f"- 证据缺口：{', '.join(market_context.evidence_gaps)}")

    lines.extend(["", "## 重要公告和新闻"])
    if not sorted_events:
        lines.append("- 暂无已入库公告或新闻。")
    else:
        for item in sorted_events[:10]:
            lines.append(format_news_summary(item))

    lines.extend(["", "## 今日推演验证"])
    lines.append("- 当前展示待复盘观察项，用于对照盘前推演是否成立；最终状态仍需用户复盘确认。")
    if not observations:
        lines.append("- 今日暂无可验证的 A/B 级观察项。")
    else:
        for observation in sort_observations(observations):
            lines.append(
                f"- [{observation.priority}] {observation.theme}：推演“{observation.hypothesis}”；对照成立条件“{observation.validation_condition}”，"
                f"失效条件“{observation.invalid_condition}”。"
            )

    lines.extend(["", "## 明日观察方向"])
    if not observations:
        lines.append("- 暂无明确方向，明日优先观察量能、强势板块延续性和核心票承接。")
    else:
        for observation in sort_observations(observations):
            lines.extend(format_observation_block(observation, market_context))

    lines.extend(["", "## 风险清单"])
    risk_notes = build_risk_notes(market_context, scored_events, observations)
    if not risk_notes:
        lines.append("- 暂未识别到额外高优先级风险，仍需警惕一致性过高后的兑现。")
    else:
        for note in risk_notes:
            lines.append(f"- {note}")

    return "\n".join(lines) + "\n"


def build_noon_report(
    trade_date: date,
    market_context: MarketContext,
    scored_events: list[ScoredEvent],
    observations: list[ObservationCandidate],
    stock_review_skill: Skill | None = None,
    generated_at: datetime | None = None,
) -> str:
    generated_time = generated_at or datetime.now()
    sorted_events = sort_scored_events(scored_events)
    lines = [
        f"# {trade_date.isoformat()} 午间复盘报告",
        "",
        f"- 生成时间：{generated_time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 交易日：{trade_date.isoformat()}",
    ]
    if stock_review_skill is not None:
        lines.append(f"- 框架依据：{stock_review_skill.name} v{stock_review_skill.version or 'unknown'}")

    lines.extend(
        [
            "",
            "## 上午市场与盘前推演对比",
            f"- 指数表现：{format_instruments(market_context.indexes[:3])}",
            f"- 两市量能：{describe_amount_tier(market_context.amount_tier)}（观测成交额 {format_amount(market_context.observed_total_amount)}）",
            "- 当前展示待复盘观察项，用于对照上午走势和盘前推演；最终状态仍需用户复盘确认。",
        ]
    )
    if observations:
        for observation in sort_observations(observations):
            lines.append(
                f"- [{observation.priority}] {observation.theme}：推演“{observation.hypothesis}”；对照成立条件“{observation.validation_condition}”，"
                f"失效条件“{observation.invalid_condition}”。"
            )
    else:
        lines.append("- 暂无可对照的 A/B 级候选观察项。")

    lines.extend(
        [
            "",
            "## 主线状态",
            f"- 强势板块：{format_sectors(market_context.sector_hotspots[:6])}",
            f"- 强势个股：{format_instruments(market_context.strong_stocks[:6])}",
            f"- 弱势个股：{format_instruments(market_context.weak_stocks[:6])}",
            f"- 成交额前排：{format_instruments(market_context.volume_leaders[:6])}",
        ]
    )
    if market_context.evidence_gaps:
        lines.append(f"- 证据缺口：{', '.join(market_context.evidence_gaps)}")

    lines.extend(["", "## 下午机会"])
    if not observations:
        lines.append("- 暂无明确候选方向，下午优先观察量能是否继续支持主线，以及强势板块是否扩散。")
    else:
        for observation in sort_observations(observations):
            lines.append(
                f"- [{observation.priority}] {observation.theme}：若午后仍满足“{observation.validation_condition}”，"
                "可继续作为复盘重点；否则只保留为观察记录。"
            )

    lines.extend(["", "## 下午风险"])
    risk_notes = build_risk_notes(market_context, scored_events, observations)
    if not risk_notes:
        lines.append("- 暂未识别到额外高优先级风险，仍需关注午后缩量、核心票跳水和后排掉队。")
    else:
        for note in risk_notes:
            lines.append(f"- {note}")

    lines.extend(["", "## 降低关注方向"])
    downgraded_events = [item for item in sorted_events if item.score.priority == "C" or item.score.risk_score >= 4]
    if not downgraded_events:
        lines.append("- 暂无明确需要降低关注的事件方向。")
    else:
        for item in downgraded_events[:6]:
            lines.append(f"- {item.event.title}：{describe_event_risk(item)}")

    lines.extend(["", "## 重要公告和新闻"])
    if not sorted_events:
        lines.append("- 暂无已入库公告或新闻。")
    else:
        for item in sorted_events[:8]:
            lines.append(format_news_summary(item))

    return "\n".join(lines) + "\n"


def write_report(output_dir: str | Path, trade_date: date, report_type: str, content: str) -> Path:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{trade_date.isoformat()}_{report_type}.md"
    path.write_text(content, encoding="utf-8")
    return path


def sort_scored_events(scored_events: list[ScoredEvent]) -> list[ScoredEvent]:
    priority_order = {"A": 0, "B": 1, "C": 2}
    return sorted(
        scored_events,
        key=lambda item: (
            priority_order.get(item.score.priority, 9),
            -item.score.expectation_gap_score,
            -item.score.catalyst_score,
            item.event.title,
        ),
    )


def sort_observations(observations: list[ObservationCandidate]) -> list[ObservationCandidate]:
    priority_order = {"A": 0, "B": 1, "C": 2}
    return sorted(observations, key=lambda item: (priority_order.get(item.priority, 9), item.theme))


def format_event_block(item: ScoredEvent) -> list[str]:
    event = item.event
    score = item.score
    related = "、".join(event.affected_stocks or event.affected_sectors) or "未识别"
    return [
        f"### {score.priority} | {event.title}",
        f"- 事件类型：{event.event_type}，方向：{event.impact_direction}，相关对象：{related}",
        f"- 评分：催化 {score.catalyst_score} / 预期差 {score.expectation_gap_score} / 风险 {score.risk_score}",
        f"- 价值投机判断：{describe_speculation_value(item)}",
        f"- 证据：{'; '.join(event.evidence[:3])}",
        f"- 备注：{'; '.join(score.rationale[:3])}",
        "",
    ]


def format_news_summary(item: ScoredEvent) -> str:
    event = item.event
    score = item.score
    related = "、".join(event.affected_stocks or event.affected_sectors) or "未识别"
    return (
        f"- [{score.priority}] {event.title}：{event.event_type} / {event.impact_direction} / "
        f"相关对象 {related} / 催化 {score.catalyst_score} / 预期差 {score.expectation_gap_score} / 风险 {score.risk_score}"
    )


def describe_speculation_value(item: ScoredEvent) -> str:
    event = item.event
    score = item.score
    if score.priority == "A":
        return "催化和预期差都较强，适合进入重点观察，但必须等待板块和量能确认。"
    if score.priority == "B":
        return "催化存在，短线窗口取决于开盘强度、板块跟随和核心票承接。"
    if event.impact_direction == "negative" or score.risk_score >= 4:
        return "更适合作为风险项跟踪，不应压过市场主线和量能判断。"
    return "当前证据不足，先作为资讯记录，不提升为交易观察。"


def format_observation_block(observation: ObservationCandidate, market_context: MarketContext) -> list[str]:
    related = "、".join(observation.related_stocks) if observation.related_stocks else "待盘中补充"
    return [
        f"### {observation.priority} | {observation.theme}",
        f"- 观察标的：{related}",
        f"- 核心票锚点：{describe_core_anchors(observation, market_context)}",
        f"- 弹性票候选：{describe_elastic_candidates(observation)}",
        f"- 推演假设：{observation.hypothesis}",
        f"- 开盘验证条件：{observation.validation_condition}",
        f"- 复盘验证点：{describe_review_checkpoint(observation)}",
        f"- 失效条件：{observation.invalid_condition}",
        f"- 证据来源：{'; '.join(observation.evidence[:4])}",
        "",
    ]


def describe_core_anchors(observation: ObservationCandidate, market_context: MarketContext) -> str:
    if not observation.related_stocks:
        return "暂无明确个股，先用主题内成交额前排、涨幅前排和最先主动走强的标的做锚定。"

    summaries = {item.code: item for item in [*market_context.strong_stocks, *market_context.volume_leaders]}
    anchors = []
    for code in observation.related_stocks[:3]:
        summary = summaries.get(code)
        if summary is None:
            anchors.append(code)
        else:
            anchors.append(f"{summary.code} {summary.name} pct={format_float(summary.pct_chg)} amount={format_amount(summary.amount)}")
    return "；".join(anchors)


def describe_elastic_candidates(observation: ObservationCandidate) -> str:
    if len(observation.related_stocks) > 1:
        return "、".join(observation.related_stocks[1:4])
    return "从同主题低位、放量、主动跟随标的中筛选，必须服从核心票强弱和板块确认。"


def describe_review_checkpoint(observation: ObservationCandidate) -> str:
    return (
        f"午盘和收盘复盘时，对照“{observation.validation_condition}”判断推演是否成立；"
        f"若触发“{observation.invalid_condition}”，记录为失效或需要降级。"
    )


def build_risk_notes(
    market_context: MarketContext,
    scored_events: list[ScoredEvent],
    observations: list[ObservationCandidate],
) -> list[str]:
    notes: list[str] = []
    if market_context.evidence_gaps:
        notes.append("市场证据仍有缺口，当前结论应以开盘后的量能和板块跟随度二次确认。")

    for item in sort_scored_events(scored_events):
        if item.score.risk_score < 4 and item.event.impact_direction != "negative":
            continue
        reason = describe_event_risk(item)
        notes.append(f"{item.event.title}：{reason}")
        if len(notes) >= 5:
            break

    if observations and all(item.priority == "B" for item in observations):
        notes.append("当前候选观察项以 B 类为主，说明催化存在但市场确认度仍不足。")
    return dedupe(notes)


def describe_event_risk(item: ScoredEvent) -> str:
    event = item.event
    score = item.score
    if event.event_type == "shareholder_reduction":
        return "存在减持风险，需防止情绪和流动性同步转弱。"
    if event.event_type == "regulatory_risk":
        return "存在监管或风险提示，除非出现强修复，否则不宜提升关注。"
    if score.risk_score >= 4 and not event.affected_sectors:
        return "证据和板块扩散仍偏弱，容易只有消息没有跟随。"
    if event.impact_direction == "negative":
        return "负面方向事件更适合作为风险跟踪，不应压过主线判断。"
    return "需要留意高位兑现、板块确认不足或开盘一致性过高后的回落。"


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def format_instruments(items: list[object]) -> str:
    if not items:
        return "暂无数据"
    return "；".join(
        f"{item.code} {item.name} pct={format_float(item.pct_chg)} amount={format_amount(item.amount)}"
        for item in items
    )


def format_sectors(items: list[object]) -> str:
    if not items:
        return "暂无数据"
    return "；".join(
        f"{item.sector} avg_pct={format_float(item.average_pct_chg)} amount={format_amount(item.total_amount)}"
        for item in items
    )


def format_float(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


def format_amount(value: float | None) -> str:
    if value is None:
        return "n/a"
    if value >= 100_000_000:
        return f"{value / 100_000_000:.2f} 亿"
    return f"{value:.0f}"


def describe_amount_tier(amount_tier: str) -> str:
    if amount_tier == "above_2t_supports_two_to_three_main_sectors":
        return "2 万亿以上，理论上能支撑两到三个主线板块"
    if amount_tier == "above_1t_supports_one_main_sector":
        return "1 万亿以上，理论上能支撑一个主线板块"
    if amount_tier == "below_1t_watch_small_caps_or_shrinking_liquidity":
        return "1 万亿以下，偏向小票或缩量抱团环境"
    return "量能分档未知"
