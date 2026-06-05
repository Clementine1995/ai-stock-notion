# MVP 任务拆分

## 1. MVP 范围

MVP 目标是跑通“采集 -> 入库 -> 知识检索 -> 分析 -> 报告 -> 结果回填”的最小闭环。

不追求完整覆盖所有数据源，不做 Web UI，不做自动交易。

## 2. 里程碑概览

| 里程碑 | 周期 | 目标 |
| --- | --- | --- |
| M0 项目初始化 | 0.5 天 | 建立代码结构、配置、运行方式 |
| M1 数据存储 | 1 天 | PostgreSQL 表结构和基础 repository |
| M2 Notion 同步 | 2 天 | 同步经验文档并入库 |
| M3 公告/新闻/行情采集 | 3 天 | 拉取 MVP 所需市场信息 |
| M4 向量库 | 2 天 | 文档切块、embedding、Qdrant 检索 |
| M5 事件抽取与评分 | 3 天 | 结构化事件和 A/B/C 优先级 |
| M6 报告生成 | 3 天 | 盘后、盘前、午间 Markdown |
| M7 验证闭环 | 2 天 | 观察项记录和结果回填 |
| M8 稳定化 | 2 天 | 测试、日志、文档、样例数据 |

总计约 2-3 周，取决于数据源账号和 API 权限准备情况。

## 3. M0 项目初始化

### 任务

- 初始化 Python 项目。
- 创建目录结构。
- 配置 `.env.example`。
- 加入基础日志。
- 加入命令行入口。

### 验收标准

- 可以运行 `python -m app.main --help`。
- 可以读取 `.env` 配置。
- 日志能输出到控制台和文件。

### 建议产物

```text
app/main.py
app/config.py
app/logging.py
.env.example
requirements.txt
README.md
```

## 4. M1 数据存储

### 任务

- 建立 PostgreSQL 数据库。
- 定义 RawDocument、MarketSnapshot、ExtractedEvent、Observation、Report 表。
- 实现基础 CRUD repository。
- 实现 content_hash 去重。

### 验收标准

- 可以插入一条 RawDocument。
- 相同 content_hash 重复插入不会产生重复记录。
- 可以查询指定日期范围的文档。

### 测试用例

- 插入重复公告，确认只有一条。
- 查询空日期范围，返回空列表。
- 查询指定 doc_type，返回正确结果。

## 5. M2 Notion 同步

### 任务

- 配置 Notion API Key。
- 读取指定 page 或 database。
- 递归读取 block children。
- 提取纯文本和标题。
- 保存为 RawDocument。

### 验收标准

- 至少同步 1 个 Notion 页面。
- 页面标题、正文、更新时间能正确保存。
- 重复同步不会重复入库。

### 注意事项

- Notion 页面可能包含 toggle、子页面、表格、PDF、图片。
- MVP 先处理标题、段落、列表、引用、代码块。
- 不支持的 block 类型记录日志，不中断任务。

## 6. M3 公告/新闻/行情采集

### 任务

- 实现公告采集器。
- 实现新闻采集器。
- 实现行情采集器。
- 所有采集器统一返回 RawDocument 或 MarketSnapshot。

### MVP 优先级

P0：

- 公告标题、公司、股票代码、发布时间、URL。
- 新闻标题、正文或摘要、发布时间、来源。
- 指数和个股日线基础行情。

P1：

- 公告 PDF 下载和正文解析。
- 外围市场数据。
- 板块行情。

### 验收标准

- 可以按日期采集公告并入库。
- 可以按日期采集新闻并入库。
- 可以按交易日采集行情并入库。
- 采集失败时有错误日志，不影响其他采集器。

## 7. M4 向量库与知识检索

### 任务

- 本地启动 Qdrant。
- 实现文档切块。
- 调用 embedding 模型生成向量。
- 将 Notion 文档和复盘文档写入 Qdrant。
- 实现相似经验检索。

### 验收标准

- 输入“高位利好兑现”，能检索到相关 Notion 经验。
- 检索结果包含标题、片段、来源、相似度。
- 重复同步同一文档不会无限增加重复向量。

### 测试用例

- 写入 3 条样例经验，查询相似主题。
- 删除或更新文档后，检索结果不出现旧版本重复内容。

## 8. M5 事件抽取与评分

### 任务

- 编写事件抽取 prompt。
- 定义 ExtractedEvent JSON schema。
- 对公告和新闻生成结构化事件。
- 实现板块关键词映射。
- 实现评分器。

### 验收标准

- 给定一条样例公告，输出合法 JSON。
- 输出包含事件类型、影响方向、证据、置信度。
- 评分结果包含催化、新鲜度、预期差、风险和优先级。

### 事件类型 MVP 枚举

```text
earnings_forecast
major_contract
merger_acquisition
share_repurchase
shareholder_reduction
policy_catalyst
industry_news
regulatory_risk
other
```

### 优先级规则初版

- A：预期差高、催化强、风险可控。
- B：催化存在，但需要市场确认。
- C：证据不足、已充分发酵或风险较高。

## 9. M6 报告生成

### 任务

- 编写报告模板。
- 实现盘后报告生成。
- 实现盘前报告生成。
- 实现午间报告生成。
- 将报告保存到 `reports/output/`。

### 验收标准

- 每类报告都能用样例数据生成 Markdown。
- 报告中重点观察项包含证据来源。
- A 类观察项包含成立条件和失效条件。
- 报告不会输出无条件买卖指令。

### 报告文件命名

```text
reports/output/2026-05-27_after_close.md
reports/output/2026-05-28_pre_market.md
reports/output/2026-05-28_noon.md
```

## 10. M7 验证闭环

### 任务

- 从报告中抽取观察项并保存 Observation。
- 次日根据行情回填基础结果。
- 支持人工补充 outcome 和 review_note。
- 生成每周命中与误判总结。

### 验收标准

- 盘前报告中的观察项能被保存。
- 次日可查询 pending 观察项。
- 可以将观察项标记为 hit、miss 或 invalid。
- 周报能列出本周有效规则和失效规则。

### 初版自动回填规则

- 板块或标的高开高走，且成交额放大，可初步标记为 hit_candidate。
- 低开低走或板块无跟随，可初步标记为 miss_candidate。
- 自动结果只作为候选，最终允许人工修正。

## 11. M8 稳定化与文档

### 任务

- 补充单元测试。
- 增加样例数据。
- 编写 README。
- 编写本地部署说明。
- 编写常见问题。

### 验收标准

- 新用户可以按 README 跑通样例流程。
- 无 API Key 时可以用样例数据生成报告。
- 关键模块有测试覆盖。
- 错误日志足够定位问题。

## 12. 开发顺序建议

推荐顺序：

1. 先做数据模型。
2. 再做样例数据报告生成。
3. 再接真实数据源。
4. 再接 Notion 和向量库。
5. 最后做自动验证闭环。

这样可以更早看到报告形态，避免一开始陷入数据源细节。

## 13. 第一版命令设计

```bash
python -m app.main sync-notion
python -m app.main collect --date 2026-05-27
python -m app.main build-index
python -m app.main report after-close --date 2026-05-27
python -m app.main report pre-market --date 2026-05-28
python -m app.main report noon --date 2026-05-28
python -m app.main review --date 2026-05-28
```

## 14. 人工配置清单

### 必填

- OpenAI 或兼容模型 API Key。
- Notion API Key。
- Notion page/database ID。
- 至少一个行情或公告数据源。

### 可选

- Tushare Token。
- Qdrant URL。
- 推送渠道 webhook。
- 板块关键词配置。

## 15. 交付检查表

- [ ] `.env.example` 已提供。
- [ ] 样例数据可运行。
- [ ] PostgreSQL 初始化成功。
- [ ] Notion 同步成功。
- [ ] 公告采集成功。
- [ ] 新闻采集成功。
- [ ] 行情采集成功。
- [ ] Qdrant 检索成功。
- [ ] 事件抽取 JSON 合法。
- [ ] 三类报告生成成功。
- [ ] 观察项入库成功。
- [ ] 次日验证可执行。
- [ ] README 可指导本地运行。

## 16. 后续版本规划

### V0.2

- 接入板块行情。
- 接入外围市场。
- 支持 Notion 回写报告。
- 优化 PDF 公告解析。

### V0.3

- 增加 Web UI。
- 增加观察池看板。
- 增加历史相似案例页面。
- 增加周度统计图表。

### V0.4

- 多模型对比。
- 风险 Agent。
- 研报摘要聚合。
- 更细的题材生命周期分析。
