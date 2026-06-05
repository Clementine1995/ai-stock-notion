# 股市舆情与公告分析工具技术设计

## 1. 设计假设

- 市场范围：A 股为主。
- 使用频率：交易日盘后、盘前、午间定时运行。
- 实时性要求：分钟级到小时级，不做秒级盯盘。
- 部署方式：优先本地开发，本地或轻量 VPS 部署。
- 报告形式：MVP 输出 Markdown 文件，后续扩展 Web UI。
- AI 输出：必须尽量结构化，方便入库、回测和复盘。

## 2. 总体架构

```text
数据源
  |-- Tushare / AKShare
  |-- Notion
  |-- 新闻 / 研报 / 外围市场
        |
        v
采集层 collectors
        |
        v
清洗与标准化 parsers
        |
        v
存储层 storage
  |-- PostgreSQL
  |-- Qdrant
        |
        v
分析层 analysis
  |-- 事件抽取
  |-- RAG 检索
  |-- 板块映射
  |-- 评分
  |-- 风险评估
        |
        v
报告层 reports
  |-- 盘后
  |-- 盘前
  |-- 午间
  |-- 周报
        |
        v
验证闭环 eval
```

## 3. 推荐技术栈

| 模块 | MVP 选择 | 后续可替换 |
| --- | --- | --- |
| 语言 | Python 3.13 | Python 3.13+ |
| API 服务 | FastAPI | FastAPI |
| 任务调度 | APScheduler | Celery / Airflow |
| 结构化数据库 | PostgreSQL | PostgreSQL |
| 向量数据库 | Qdrant local Docker | Qdrant Cloud / Milvus |
| 文档解析 | pypdf / pymupdf | unstructured |
| RAG 框架 | LlamaIndex 或轻量自研 | LangGraph |
| AI 模型 | OpenAI / 兼容接口模型 | 本地模型混合 |
| 报告 | Markdown | Web UI / Notion 回写 |

## 4. 目录结构

```text
stock-ai-assistant/
  app/
    main.py
    config.py
    logging.py
  collectors/
    base.py
    tushare_collector.py
    akshare_collector.py
    notion_collector.py
    news_collector.py
    market_collector.py
  parsers/
    announcement_parser.py
    pdf_parser.py
    notion_parser.py
    text_normalizer.py
  storage/
    db.py
    models.py
    repositories.py
    vector_store.py
  analysis/
    event_extractor.py
    rag.py
    sector_mapper.py
    scorer.py
    risk_checker.py
    report_generator.py
  jobs/
    run_after_close.py
    run_pre_market.py
    run_noon_review.py
    run_weekly_review.py
  reports/
    output/
    templates/
      after_close.md
      pre_market.md
      noon.md
      weekly.md
  eval/
    prediction_tracker.py
    outcome_checker.py
    weekly_summarizer.py
  tests/
```

## 5. 数据模型

### 5.1 RawDocument

原始文档表，保存公告、新闻、Notion 文档等。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string | 唯一 ID |
| source | string | tushare / akshare / notion / news |
| doc_type | string | announcement / news / note / research |
| title | string | 标题 |
| content | text | 正文 |
| url | string | 来源链接 |
| publish_time | datetime | 发布时间 |
| fetched_at | datetime | 抓取时间 |
| stock_code | string | 股票代码，可为空 |
| stock_name | string | 股票名称，可为空 |
| metadata | json | 额外信息 |
| content_hash | string | 去重哈希 |

### 5.2 MarketSnapshot

行情快照表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string | 唯一 ID |
| trade_date | date | 交易日 |
| code | string | 股票或指数代码 |
| name | string | 名称 |
| open | float | 开盘价 |
| close | float | 收盘价 |
| high | float | 最高价 |
| low | float | 最低价 |
| pct_chg | float | 涨跌幅 |
| amount | float | 成交额 |
| turnover_rate | float | 换手率 |
| limit_status | string | up / down / none |

### 5.3 ExtractedEvent

AI 或规则抽取后的事件表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string | 唯一 ID |
| raw_document_id | string | 来源文档 |
| event_type | string | 事件类型 |
| summary | text | 摘要 |
| impact_direction | string | positive / negative / neutral / uncertain |
| affected_sectors | json | 相关板块 |
| related_stocks | json | 相关股票 |
| evidence | json | 证据片段 |
| confidence | float | 置信度 |
| created_at | datetime | 创建时间 |

### 5.4 Observation

报告中的观察项，用于后续验证。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string | 唯一 ID |
| trade_date | date | 交易日 |
| report_type | string | after_close / pre_market / noon |
| theme | string | 主题或板块 |
| related_stocks | json | 相关标的 |
| hypothesis | text | 推演假设 |
| validation_condition | text | 成立条件 |
| invalid_condition | text | 失效条件 |
| priority | string | A / B / C |
| status | string | pending / hit / miss / invalid |
| outcome | text | 实际结果 |
| review_note | text | 复盘结论 |

### 5.5 Report

报告表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string | 唯一 ID |
| trade_date | date | 交易日 |
| report_type | string | 报告类型 |
| title | string | 标题 |
| content | text | Markdown 内容 |
| generated_at | datetime | 生成时间 |
| source_event_ids | json | 引用事件 |
| observation_ids | json | 观察项 |

## 6. 采集层设计

### 6.1 Collector 接口

```python
class Collector:
    def fetch(self, start_time, end_time) -> list[RawDocument]:
        raise NotImplementedError
```

所有采集器都返回统一的 RawDocument 对象。

### 6.2 NotionCollector

职责：

- 根据配置读取 Notion page 或 database。
- 递归读取 block children。
- 提取文本、标题、层级、更新时间。
- 将每个页面保存为 RawDocument。

配置项：

```env
NOTION_API_KEY=
NOTION_ROOT_PAGE_IDS=
NOTION_DATABASE_IDS=
```

### 6.3 AnnouncementCollector

职责：

- 拉取指定日期范围的上市公司公告。
- 保存标题、公司、公告时间、PDF URL。
- 可选下载 PDF 并解析正文。

MVP 策略：

- 第一版只解析标题和可用摘要。
- 对优先级高的公告下载 PDF 正文。

### 6.4 NewsCollector

职责：

- 拉取指定来源新闻。
- 保存标题、正文、发布时间、来源。
- 对新闻做去重。

### 6.5 MarketCollector

职责：

- 拉取指数、个股日线行情。
- 拉取涨停、跌停、成交额排行。
- 后续扩展板块行情。

## 7. 清洗与解析层

### 7.1 去重

使用 `content_hash = sha256(source + title + publish_time + stock_code)`。

同一 URL 重复出现时只保留一条。

### 7.2 文本标准化

- 去掉多余空白。
- 去掉免责声明、页眉页脚。
- 保留公告标题、章节标题和关键表格文本。

### 7.3 文档切块

Notion 和公告正文写入向量库前切块。

建议 MVP 参数：

- chunk_size: 800-1200 中文字符。
- chunk_overlap: 100-200 中文字符。
- metadata: source、title、url、publish_time、doc_type、stock_code。

## 8. 向量库设计

### 8.1 Collection

建议先建一个 collection：

```text
market_knowledge
```

payload 字段：

```json
{
  "source": "notion",
  "doc_type": "note",
  "title": "高位利好兑现案例",
  "url": "notion://...",
  "publish_time": "2026-05-27T00:00:00",
  "stock_code": "",
  "tags": ["交易原则", "风险"]
}
```

### 8.2 检索策略

分析某个事件时，检索条件：

- query: 事件摘要 + 板块 + 公告类型。
- top_k: 5-8。
- filter: 优先 Notion 经验和历史复盘。

输出报告时，必须展示相似经验的标题和简短引用。

## 9. AI 分析层设计

### 9.1 EventExtractor

输入：

- RawDocument。

输出：

- ExtractedEvent。

处理流程：

1. 判断文档是否与交易相关。
2. 识别事件类型。
3. 提取影响方向。
4. 提取相关板块和标的。
5. 抽取证据。
6. 给出置信度。

### 9.2 RAGAnalyzer

输入：

- ExtractedEvent。

输出：

- 相似历史案例。
- 用户经验匹配。
- 本次事件与历史案例差异。

### 9.3 SectorMapper

职责：

- 将公告或新闻映射到行业、概念、产业链。
- MVP 可先使用手工维护的 `sector_keywords.yaml`。

示例：

```yaml
算力:
  - GPU
  - 数据中心
  - 液冷
  - 服务器
  - 光模块
半导体:
  - 晶圆
  - 光刻
  - 封测
  - 存储芯片
```

### 9.4 Scorer

评分字段：

```json
{
  "catalyst_score": 4,
  "freshness_score": 3,
  "expectation_gap_score": 4,
  "sector_spread_score": 3,
  "liquidity_score": 3,
  "risk_score": 2,
  "priority": "A"
}
```

优先级建议：

- A：值得重点观察，需要明确验证条件。
- B：有价值，但需要板块或市场配合。
- C：信息价值有限或风险较高。

### 9.5 RiskChecker

风险类型：

- 高位利好兑现。
- 板块一致性过强。
- 公告不及预期。
- 监管或问询。
- 减持、解禁、业绩证伪。
- 外围风险。
- 市场流动性不足。

## 10. 报告生成设计

### 10.1 盘后流程

```text
拉取当日行情
拉取盘后公告和新闻
抽取事件
检索相似经验
生成观察项
验证今日盘前观察项
生成盘后报告
```

### 10.2 盘前流程

```text
拉取隔夜外围数据
拉取隔夜新闻和公告
抽取事件
检索 Notion 经验和历史案例
生成预期差候选
生成开盘验证条件
生成盘前报告
```

### 10.3 午间流程

```text
拉取上午行情
读取盘前观察项
判断成立、失效或待观察
生成下午机会与风险
生成午间报告
```

### 10.4 报告模板原则

- 先结论，后证据。
- 区分事实、推断、交易观察。
- 每个 A 类观察项必须有失效条件。
- 不使用“必涨”“稳赚”“确定性买点”等表述。

## 11. 配置设计

`.env` 示例：

```env
OPENAI_API_KEY=
OPENAI_MODEL=
EMBEDDING_MODEL=

TUSHARE_TOKEN=
NOTION_API_KEY=
NOTION_ROOT_PAGE_IDS=

DATABASE_URL=postgresql://stock_ai:stock_ai@localhost:5432/stock_ai
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=market_knowledge

REPORT_OUTPUT_DIR=reports/output
TIMEZONE=Asia/Shanghai
```

## 12. 定时任务

MVP 可先手动运行，之后加调度。

建议时间：

| 任务 | 时间 |
| --- | --- |
| 盘后复盘 | 16:30 |
| 盘后公告补充 | 20:30 |
| 盘前报告 | 08:15 |
| 午间复盘 | 12:10 |
| 周度复盘 | 周五 20:30 |

## 13. 测试策略

### 13.1 单元测试

- 文档去重。
- Notion 文本解析。
- 公告事件抽取 JSON schema 校验。
- 评分函数。
- 报告模板渲染。

### 13.2 集成测试

- 从样例公告生成事件。
- 从样例 Notion 文档写入向量库并检索。
- 生成一份完整盘前报告。

### 13.3 人工验收

- 报告是否有证据链。
- 观察项是否可验证。
- AI 是否把事实和推断混在一起。
- 是否存在明显幻觉来源。

## 14. 部署设计

### 14.1 本地 MVP

```text
Python venv
PostgreSQL
Qdrant Docker
Markdown reports
```

### 14.2 Docker Compose 后续形态

```yaml
services:
  app:
    build: .
    env_file: .env
    volumes:
      - ./reports:/app/reports
      - ./data:/app/data
    depends_on:
      - postgres
  postgres:
    image: postgres:17
    environment:
      POSTGRES_USER: stock_ai
      POSTGRES_PASSWORD: stock_ai
      POSTGRES_DB: stock_ai
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
  qdrant:
    image: qdrant/qdrant
    ports:
      - "6333:6333"
    volumes:
      - qdrant_storage:/qdrant/storage

volumes:
  postgres_data:
  qdrant_storage:
```

## 15. 主要风险

| 风险 | 缓解 |
| --- | --- |
| 数据源不稳定 | 采集器隔离，支持多源替换 |
| AI 幻觉 | 结构化输出、证据引用、置信度 |
| 过度拟合历史经验 | 周度验证、记录失效规则 |
| 成本失控 | 优先摘要后深度分析，限制 token |
| 报告太长不可用 | A/B/C 优先级和固定模板 |
| 结论不可验证 | 强制观察项包含成立和失效条件 |
