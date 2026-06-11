# 股市舆情与公告分析工具

这是一个面向 A 股短线交易研究的 AI 助理方案文档集。当前阶段选择方案 B：Python 自研轻量系统。

## 文档阅读顺序

1. [PRD](docs/PRD.md)：产品目标、使用场景、核心需求和验收标准。
2. [技术设计](docs/TECHNICAL_DESIGN.md)：系统架构、数据模型、模块设计和部署方案。
3. [MVP 任务拆分](docs/MVP_TASK_BREAKDOWN.md)：按里程碑拆分的开发任务和验收清单。

## MVP 核心闭环

```text
采集公告/新闻/行情/Notion
  -> 入库与去重
  -> 知识库检索
  -> AI 事件抽取与评分
  -> 生成盘后/盘前/午间报告
  -> 记录观察项
  -> 次日或周度复盘验证
```

## 当前原则

- 不做自动交易。
- 不输出无条件买卖指令。
- 所有重点结论必须包含证据、置信度、成立条件和失效条件。
- MVP 优先低成本、本地可运行、结果可验证。

## 下一步建议

先按 `docs/MVP_TASK_BREAKDOWN.md` 从 M0 开始搭项目骨架，再用样例数据生成第一份盘前报告。等报告格式满意后，再接入真实数据源和 Notion。

## 本地运行

要求 Python 3.13。

```bash
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m app.main --help
.\.venv\Scripts\python -m app.main show-config
.\.venv\Scripts\python -m app.main init-db
```

配置从项目根目录 `.env` 读取。第一次运行可以复制 `.env.example` 后按需填写。

## Skills

Skills live under `skills/<skill-name>/SKILL.md`. Each file can define simple
frontmatter and a Markdown instruction body:

```markdown
---
name: risk-checker
description: Identify common short-term trading risks.
stage: m5
---

Skill instructions go here.
```

Useful commands:

```bash
.\.venv\Scripts\python -m app.main list-skills
.\.venv\Scripts\python -m app.main show-skill risk-checker
```

## LLM

The app uses an OpenAI-compatible chat completions client. DeepSeek can be used
with this configuration:

```env
LLM_PROVIDER=deepseek
LLM_API_KEY=
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
LLM_TIMEOUT=60
```

Verify connectivity:

```bash
.\.venv\Scripts\python -m app.main test-llm
```

## 知识库刷新

Notion 页面变化后，可以用一个命令刷新本地切块和向量库：

```bash
.\.venv\Scripts\python -m app.main refresh-knowledge
```

该命令等价于依次运行：

```bash
.\.venv\Scripts\python -m app.main sync-notion
.\.venv\Scripts\python -m app.main build-index --source notion --doc-type note
.\.venv\Scripts\python -m app.main sync-vector-index
```

`sync-vector-index` 会先按 `raw_document_id` 删除 Qdrant 中已有 points，再写入当前切块。
因此更新同一篇 Notion 页面不会持续追加重复向量。
