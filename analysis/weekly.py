from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime

from storage.models import Observation


@dataclass(frozen=True)
class WeeklyReviewSummary:
    start_date: date
    end_date: date
    observations: list[Observation]
    generated_at: datetime


def build_weekly_review(summary: WeeklyReviewSummary) -> str:
    status_counts = Counter(observation.status for observation in summary.observations)
    reviewed_count = status_counts["hit"] + status_counts["miss"] + status_counts["invalid"]
    hit_rate = status_counts["hit"] / reviewed_count if reviewed_count else 0
    lines = [
        f"# {summary.start_date.isoformat()}_{summary.end_date.isoformat()} 周度复盘",
        "",
        f"- 生成时间：{summary.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 观察项总数：{len(summary.observations)}",
        f"- 已复盘：{reviewed_count}",
        f"- 命中率：{hit_rate:.0%}",
        f"- 状态分布：hit={status_counts['hit']} / miss={status_counts['miss']} / invalid={status_counts['invalid']} / pending={status_counts['pending']}",
        "",
        "## 命中观察",
    ]
    append_observation_lines(lines, [item for item in summary.observations if item.status == "hit"], empty="- 暂无命中观察。")
    lines.extend(["", "## 误判观察"])
    append_observation_lines(lines, [item for item in summary.observations if item.status == "miss"], empty="- 暂无误判观察。")
    lines.extend(["", "## 失效观察"])
    append_observation_lines(lines, [item for item in summary.observations if item.status == "invalid"], empty="- 暂无失效观察。")
    lines.extend(["", "## 待复盘观察"])
    append_observation_lines(lines, [item for item in summary.observations if item.status == "pending"], empty="- 暂无待复盘观察。")
    stale_observations = [item for item in summary.observations if item.status == "pending" and (summary.end_date - item.trade_date).days >= 5]
    lines.extend(["", "## 陈旧观察"])
    append_observation_lines(lines, stale_observations, empty="- 暂无超过 5 天未复盘的观察项。")
    lines.extend(["", "## 规则沉淀"])
    lines.extend(build_rule_notes(summary.observations))
    lines.extend(["", "## 可沉淀条目"])
    lines.extend(build_knowledge_candidates(summary.observations))
    return "\n".join(lines) + "\n"


def build_experience_candidates(summary: WeeklyReviewSummary) -> str:
    lines = [
        f"# {summary.start_date.isoformat()}_{summary.end_date.isoformat()} 经验沉淀候选",
        "",
        f"- 生成时间：{summary.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
        "- 用途：人工整理到 Notion 经验库，或在多次验证后更新 stock-review Skill。",
        "- 边界：单次命中或误判只作为样本，不直接固化为稳定规则。",
        "",
        "## Notion 经验候选",
    ]
    lines.extend(build_notion_candidates(summary.observations))
    lines.extend(["", "## stock-review Skill 候选"])
    lines.extend(build_skill_candidates(summary.observations))
    return "\n".join(lines) + "\n"


def append_observation_lines(lines: list[str], observations: list[Observation], empty: str) -> None:
    if not observations:
        lines.append(empty)
        return
    for observation in sorted(observations, key=lambda item: (item.trade_date, item.priority, item.theme)):
        stocks = "、".join(observation.related_stocks) if observation.related_stocks else "none"
        lines.append(f"- [{observation.trade_date.isoformat()}][{observation.priority}] {observation.theme} stocks={stocks}")
        lines.append(f"  - hypothesis: {observation.hypothesis}")
        if observation.outcome:
            lines.append(f"  - outcome: {observation.outcome}")
        if observation.review_note:
            lines.append(f"  - review_note: {observation.review_note}")


def build_rule_notes(observations: list[Observation]) -> list[str]:
    notes: list[str] = []
    hit_themes = Counter(item.theme for item in observations if item.status == "hit")
    miss_themes = Counter(item.theme for item in observations if item.status == "miss")
    if hit_themes:
        notes.append("- 有效方向：" + "；".join(f"{theme}({count})" for theme, count in hit_themes.most_common(5)))
    else:
        notes.append("- 有效方向：暂无足够样本。")
    if miss_themes:
        notes.append("- 误判方向：" + "；".join(f"{theme}({count})" for theme, count in miss_themes.most_common(5)))
    else:
        notes.append("- 误判方向：暂无足够样本。")
    notes.append("- 规则更新建议：只把有多次验证记录的模式沉淀到 stock-review 或 Notion，避免单次样本过拟合。")
    return notes


def build_knowledge_candidates(observations: list[Observation]) -> list[str]:
    candidates: list[str] = []
    for observation in observations:
        if observation.status == "hit":
            candidates.append(
                f"- 有效样本 | {observation.theme} | 假设：{observation.hypothesis} | 复盘：{observation.review_note or observation.outcome or '待补充'}"
            )
        elif observation.status == "miss":
            candidates.append(
                f"- 误判样本 | {observation.theme} | 假设：{observation.hypothesis} | 原因：{observation.review_note or observation.outcome or '待补充'}"
            )
    if not candidates:
        return ["- 暂无可沉淀条目。"]
    candidates.append("- 沉淀建议：有效样本优先进入 Notion 经验库，多次重复验证后再考虑更新 stock-review。")
    return candidates


def build_notion_candidates(observations: list[Observation]) -> list[str]:
    candidates: list[str] = []
    for observation in sorted(observations, key=lambda item: (item.status, item.trade_date, item.theme)):
        if observation.status not in {"hit", "miss"}:
            continue
        label = {"hit": "有效样本", "miss": "误判样本"}[observation.status]
        candidates.append(f"### {label} | {observation.theme} | {observation.trade_date.isoformat()}")
        candidates.append(f"- 假设：{observation.hypothesis}")
        candidates.append(f"- 验证条件：{observation.validation_condition}")
        candidates.append(f"- 失效条件：{observation.invalid_condition}")
        candidates.append(f"- 复盘结论：{observation.review_note or observation.outcome or '待补充'}")
        candidates.append("")
    if not candidates:
        return ["- 暂无已复盘的 Notion 经验候选。"]
    return candidates[:-1] if candidates[-1] == "" else candidates


def build_skill_candidates(observations: list[Observation]) -> list[str]:
    hit_themes = Counter(item.theme for item in observations if item.status == "hit")
    miss_themes = Counter(item.theme for item in observations if item.status == "miss")
    candidates: list[str] = []
    for theme, count in hit_themes.most_common():
        if count >= 2:
            candidates.append(f"- 可强化规则：{theme} 连续命中 {count} 次，可检查是否需要写入 stock-review 的主线/量能验证框架。")
    for theme, count in miss_themes.most_common():
        if count >= 2:
            candidates.append(f"- 可补充反例：{theme} 连续误判 {count} 次，可检查是否需要增加降级条件或风险提示。")
    if not candidates:
        return ["- 暂无达到多次验证门槛的 Skill 更新候选；先沉淀到 Notion，继续观察重复模式。"]
    candidates.append("- 更新提醒：修改 Skill 前需人工回看样本证据，提升 `skills/stock-review/SKILL.md` version 后再用 list-skills/show-skill 验证。")
    return candidates
