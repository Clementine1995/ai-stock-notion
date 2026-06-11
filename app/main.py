from __future__ import annotations

import argparse
import os
from contextlib import contextmanager
from datetime import date
from collections.abc import Iterator

from app.config import load_settings, redact_url
from app.logging import setup_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.main",
        description="A 股舆情、公告与报告分析工具",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("sync-notion", help="同步 Notion 经验文档")
    subparsers.add_parser("refresh-knowledge", help="同步 Notion 并刷新本地和向量知识库")

    collect_parser = subparsers.add_parser("collect", help="采集公告、新闻和行情")
    add_market_collect_args(collect_parser)

    collect_market_parser = subparsers.add_parser("collect-market", help="采集行情快照")
    add_market_collect_args(collect_market_parser)

    collect_announcements_parser = subparsers.add_parser("collect-announcements", help="采集上市公司公告")
    collect_announcements_parser.add_argument("--date", default=date.today().isoformat(), help="公告日期，格式 YYYY-MM-DD")
    collect_announcements_parser.add_argument("--category", default="全部", help="公告类型，例如 全部、重大事项、风险提示")
    collect_announcements_parser.add_argument("--no-proxy", action="store_true", help="AKShare 请求不使用 HTTP/HTTPS 代理")

    collect_news_parser = subparsers.add_parser("collect-news", help="采集新闻")
    collect_news_parser.add_argument("--date", default=date.today().isoformat(), help="新闻日期，格式 YYYY-MM-DD")
    collect_news_parser.add_argument("--source", default="cctv", choices=("cctv", "eastmoney-stock"), help="新闻来源")
    collect_news_parser.add_argument("--stock-code", action="append", default=None, help="A 股代码，可重复传入；eastmoney-stock 使用")
    collect_news_parser.add_argument("--no-proxy", action="store_true", help="AKShare 请求不使用 HTTP/HTTPS 代理")

    build_index_parser = subparsers.add_parser("build-index", help="构建或更新本地知识库索引")
    build_index_parser.add_argument("--source", default=None, help="按来源过滤，例如 notion")
    build_index_parser.add_argument("--doc-type", default=None, help="按文档类型过滤，例如 note")
    build_index_parser.add_argument("--limit", type=int, default=100, help="处理文档数量")
    build_index_parser.add_argument("--chunk-size", type=int, default=1200, help="单个切块最大字符数")
    build_index_parser.add_argument("--overlap", type=int, default=150, help="相邻切块重叠字符数")

    sync_vector_parser = subparsers.add_parser("sync-vector-index", help="同步文档切块到向量库")
    sync_vector_parser.add_argument("--embedding-status", default="pending", help="按 embedding 状态过滤")
    sync_vector_parser.add_argument("--limit", type=int, default=100, help="处理切块数量")

    search_parser = subparsers.add_parser("search-knowledge", help="检索知识库")
    search_parser.add_argument("--query", required=True, help="检索问题")
    search_parser.add_argument("--limit", type=int, default=5, help="返回条数")

    ensure_vector_parser = subparsers.add_parser("ensure-vector-collection", help="创建或更新 Qdrant collection")
    ensure_vector_parser.add_argument("--dimension", type=int, default=None, help="向量维度，默认读取 EMBEDDING_DIMENSION")
    ensure_vector_parser.add_argument("--distance", default="Cosine", help="向量距离，例如 Cosine")

    subparsers.add_parser("init-db", help="初始化 PostgreSQL 表结构")

    list_documents_parser = subparsers.add_parser("list-documents", help="列出最近入库的文档")
    list_documents_parser.add_argument("--source", default=None, help="按来源过滤，例如 notion")
    list_documents_parser.add_argument("--doc-type", default=None, help="按文档类型过滤，例如 note")
    list_documents_parser.add_argument("--limit", type=int, default=10, help="返回条数")

    list_chunks_parser = subparsers.add_parser("list-chunks", help="列出最近生成的文档切块")
    list_chunks_parser.add_argument("--embedding-status", default=None, help="按 embedding 状态过滤，例如 pending")
    list_chunks_parser.add_argument("--limit", type=int, default=10, help="返回条数")

    list_market_parser = subparsers.add_parser("list-market", help="列出已入库的行情快照")
    list_market_parser.add_argument("--date", default=None, help="交易日期，格式 YYYY-MM-DD")
    list_market_parser.add_argument("--code", default=None, help="股票代码")
    list_market_parser.add_argument("--source", default=None, help="数据源，例如 akshare 或 akshare_index")
    list_market_parser.add_argument("--instrument-type", default=None, help="标的类型，例如 stock 或 index")
    list_market_parser.add_argument("--limit", type=int, default=10, help="返回条数")

    analyze_market_parser = subparsers.add_parser("analyze-market", help="分析已入库行情的市场上下文")
    analyze_market_parser.add_argument("--date", default=date.today().isoformat(), help="交易日期，格式 YYYY-MM-DD")
    analyze_market_parser.add_argument("--limit", type=int, default=1000, help="读取行情快照数量")

    score_events_parser = subparsers.add_parser("score-events", help="抽取并评分已入库公告和新闻事件")
    score_events_parser.add_argument("--date", default=date.today().isoformat(), help="文档发布日期，格式 YYYY-MM-DD")
    score_events_parser.add_argument("--doc-type", default=None, help="文档类型，例如 announcement 或 news")
    score_events_parser.add_argument("--source", default=None, help="文档来源，例如 akshare 或 akshare_eastmoney")
    score_events_parser.add_argument("--limit", type=int, default=20, help="处理文档数量")

    subparsers.add_parser("list-skills", help="列出可用 Skills")
    show_skill_parser = subparsers.add_parser("show-skill", help="显示指定 Skill 内容")
    show_skill_parser.add_argument("name", help="Skill 名称")

    test_llm_parser = subparsers.add_parser("test-llm", help="测试 LLM 连接")
    test_llm_parser.add_argument("--prompt", default="请用一句话回复：连接成功。", help="测试提示词")

    report_parser = subparsers.add_parser("report", help="生成 Markdown 报告")
    report_subparsers = report_parser.add_subparsers(dest="report_type", required=True)
    for report_type in ("after-close", "pre-market", "noon"):
        child = report_subparsers.add_parser(report_type, help=f"生成 {report_type} 报告")
        child.add_argument("--date", default=date.today().isoformat(), help="交易日期，格式 YYYY-MM-DD")

    review_parser = subparsers.add_parser("review", help="回填观察项结果")
    review_parser.add_argument("--date", default=date.today().isoformat(), help="交易日期，格式 YYYY-MM-DD")

    subparsers.add_parser("show-config", help="显示当前配置概览")
    return parser


def add_market_collect_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--date", default=None, help="交易日期，格式 YYYY-MM-DD")
    parser.add_argument("--start-date", default=None, help="开始交易日期，格式 YYYY-MM-DD")
    parser.add_argument("--end-date", default=None, help="结束交易日期，格式 YYYY-MM-DD")
    parser.add_argument("--stock-code", action="append", default=None, help="A 股代码，可重复传入")
    parser.add_argument("--index-code", action="append", default=None, help="指数代码，可重复传入，例如 sh000001")
    parser.add_argument("--no-proxy", action="store_true", help="AKShare 请求不使用 HTTP/HTTPS 代理")


def run_placeholder(command: str) -> int:
    settings = load_settings()
    logger = setup_logging(settings)
    logger.info("%s command is not implemented yet; M0 CLI wiring is ready.", command)
    return 0


def parse_date_arg(value: str):
    return date.fromisoformat(value)


def split_codes(value: str) -> list[str]:
    normalized = value.replace(";", ",").replace("\n", ",").replace("\t", ",").replace(" ", ",")
    return [code.strip() for code in normalized.split(",") if code.strip()]


def unique_codes(codes: list[str]) -> list[str]:
    return list(dict.fromkeys(codes))


def resolve_market_date_range(args: argparse.Namespace) -> tuple[date, date]:
    if args.date and (args.start_date or args.end_date):
        raise ValueError("--date cannot be used with --start-date or --end-date")
    if args.date:
        trade_date = parse_date_arg(args.date)
        return trade_date, trade_date
    if args.start_date or args.end_date:
        start_date = parse_date_arg(args.start_date or args.end_date)
        end_date = parse_date_arg(args.end_date or args.start_date)
    else:
        start_date = end_date = date.today()
    if start_date > end_date:
        raise ValueError("--start-date must be earlier than or equal to --end-date")
    return start_date, end_date


def resolve_market_codes(args: argparse.Namespace, settings) -> tuple[list[str], list[str]]:
    configured_stock_codes = split_codes(settings.market_stock_codes)
    configured_index_codes = split_codes(settings.market_index_codes)
    stock_codes = args.stock_code or configured_stock_codes
    index_codes = args.index_code or configured_index_codes
    if not stock_codes and not index_codes:
        stock_codes = ["000001"]
    return unique_codes(stock_codes), unique_codes(index_codes)


@contextmanager
def without_http_proxy(enabled: bool) -> Iterator[None]:
    if not enabled:
        yield
        return

    proxy_names = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy", "NO_PROXY", "no_proxy")
    previous = {name: os.environ.get(name) for name in proxy_names}
    try:
        for name in proxy_names:
            os.environ.pop(name, None)
        os.environ["NO_PROXY"] = "*"
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def collect_command(args: argparse.Namespace) -> int:
    return collect_market_command(args)


def collect_market_command(args: argparse.Namespace) -> int:
    from collectors.akshare_market import collect_index_daily_range, collect_stock_daily_range
    from storage.db import connect, init_db
    from storage.repositories import MarketSnapshotRepository

    settings = load_settings()
    logger = setup_logging(settings)
    init_db(settings)
    try:
        start_date, end_date = resolve_market_date_range(args)
    except ValueError as exc:
        print(str(exc))
        return 1
    stock_codes, index_codes = resolve_market_codes(args, settings)
    snapshots = []
    failed_count = 0
    with without_http_proxy(args.no_proxy):
        for stock_code in stock_codes:
            try:
                collected = collect_stock_daily_range(stock_code, start_date, end_date)
            except Exception as exc:
                failed_count += 1
                logger.error("Failed to collect market snapshots for %s: %s", stock_code, exc)
                continue
            logger.info("Collected %s market snapshot(s) for %s.", len(collected), stock_code)
            snapshots.extend(collected)
        for index_code in index_codes:
            try:
                collected = collect_index_daily_range(index_code, start_date, end_date)
            except Exception as exc:
                failed_count += 1
                logger.error("Failed to collect market snapshots for %s: %s", index_code, exc)
                continue
            logger.info("Collected %s market snapshot(s) for %s.", len(collected), index_code)
            snapshots.extend(collected)

    with connect(settings) as connection:
        count = MarketSnapshotRepository(connection).upsert_many(snapshots)
    logger.info("Stored %s market snapshot(s).", count)
    print(f"snapshots={count}")
    return 1 if failed_count and not snapshots else 0


def collect_announcements_command(args: argparse.Namespace) -> int:
    from collectors.akshare_announcements import collect_announcements
    from storage.db import connect, init_db
    from storage.repositories import RawDocumentRepository

    settings = load_settings()
    logger = setup_logging(settings)
    init_db(settings)
    trade_date = parse_date_arg(args.date)
    with without_http_proxy(args.no_proxy):
        documents = collect_announcements(trade_date, category=args.category)
    with connect(settings) as connection:
        RawDocumentRepository(connection).upsert_many(documents)
    logger.info("Stored %s announcement document(s).", len(documents))
    print(f"documents={len(documents)}")
    return 0


def collect_news_command(args: argparse.Namespace) -> int:
    from collectors.akshare_news import collect_cctv_news, collect_stock_news
    from storage.db import connect, init_db
    from storage.repositories import RawDocumentRepository

    settings = load_settings()
    logger = setup_logging(settings)
    init_db(settings)
    news_date = parse_date_arg(args.date)
    with without_http_proxy(args.no_proxy):
        if args.source == "cctv":
            documents = collect_cctv_news(news_date)
        else:
            stock_codes = unique_codes(args.stock_code or split_codes(settings.market_stock_codes))
            if not stock_codes:
                print("MARKET_STOCK_CODES or --stock-code is required for eastmoney-stock news.")
                return 1
            documents = collect_stock_news(stock_codes, min_publish_date=news_date)
    with connect(settings) as connection:
        RawDocumentRepository(connection).upsert_many(documents)
    logger.info("Stored %s news document(s) from %s.", len(documents), args.source)
    print(f"documents={len(documents)}")
    return 0


def show_config() -> int:
    settings = load_settings()
    logger = setup_logging(settings)
    logger.info("Loaded configuration from .env when present.")
    print(f"DATABASE_URL={redact_url(settings.database_url)}")
    print(f"REPORT_OUTPUT_DIR={settings.report_output_dir}")
    print(f"TIMEZONE={settings.timezone}")
    print(f"LOG_FILE={settings.log_file}")
    return 0


def init_db_command() -> int:
    from storage.db import init_db

    settings = load_settings()
    logger = setup_logging(settings)
    init_db(settings)
    logger.info("PostgreSQL schema is ready.")
    return 0


def sync_notion_command() -> int:
    from collectors.notion import fetch_notion_documents
    from storage.db import connect, init_db
    from storage.repositories import RawDocumentRepository

    settings = load_settings()
    logger = setup_logging(settings)
    init_db(settings)
    documents = fetch_notion_documents(settings)
    with connect(settings) as connection:
        repository = RawDocumentRepository(connection)
        for document in documents:
            repository.upsert(document)
            logger.info("Synced Notion page: %s", document.title)
    logger.info("Synced %s Notion document(s).", len(documents))
    return 0


def refresh_knowledge_command() -> int:
    sync_notion_command()
    build_index_command(
        argparse.Namespace(
            source="notion",
            doc_type="note",
            limit=100,
            chunk_size=1200,
            overlap=150,
        )
    )
    sync_vector_index_command(argparse.Namespace(embedding_status="pending", limit=100))
    return 0


def build_index_command(args: argparse.Namespace) -> int:
    from analysis.indexing import build_local_index
    from storage.db import connect, init_db
    from storage.models import RawDocumentQuery
    from storage.repositories import DocumentChunkRepository, RawDocumentRepository

    settings = load_settings()
    logger = setup_logging(settings)
    init_db(settings)
    query = RawDocumentQuery(source=args.source, doc_type=args.doc_type, limit=args.limit)
    with connect(settings) as connection:
        result = build_local_index(
            RawDocumentRepository(connection),
            DocumentChunkRepository(connection),
            query,
            chunk_size=args.chunk_size,
            overlap=args.overlap,
        )
    logger.info("Built local index for %s document(s), %s chunk(s).", result.document_count, result.chunk_count)
    print(f"documents={result.document_count} chunks={result.chunk_count}")
    return 0


def sync_vector_index_command(args: argparse.Namespace) -> int:
    from analysis.embeddings import EmbeddingClient
    from analysis.vector_index import QdrantClient, sync_vector_index
    from storage.db import connect, init_db
    from storage.models import DocumentChunkQuery
    from storage.repositories import DocumentChunkRepository

    settings = load_settings()
    logger = setup_logging(settings)
    init_db(settings)
    query = DocumentChunkQuery(embedding_status=args.embedding_status, limit=args.limit)
    with connect(settings) as connection:
        result = sync_vector_index(
            DocumentChunkRepository(connection),
            EmbeddingClient(settings),
            QdrantClient(settings),
            query,
        )
    logger.info("Synced %s chunk(s) from %s document(s) to vector index.", result.chunk_count, result.document_count)
    print(f"chunks={result.chunk_count} documents={result.document_count}")
    return 0


def search_knowledge_command(args: argparse.Namespace) -> int:
    from analysis.embeddings import EmbeddingClient
    from analysis.vector_index import QdrantClient, search_knowledge

    settings = load_settings()
    setup_logging(settings)
    matches = search_knowledge(EmbeddingClient(settings), QdrantClient(settings), args.query, args.limit)
    if not matches:
        print("No knowledge matches found.")
        return 0
    for match in matches:
        title = match.metadata.get("title", "")
        source = match.metadata.get("source", "")
        preview = match.content.replace("\n", " ")[:100]
        print(f"score={match.score:.4f} | {source} | {title} | {preview}")
    return 0


def ensure_vector_collection_command(args: argparse.Namespace) -> int:
    from analysis.vector_index import QdrantClient

    settings = load_settings()
    logger = setup_logging(settings)
    dimension = args.dimension or settings.embedding_dimension
    QdrantClient(settings).ensure_collection(dimension, distance=args.distance)
    logger.info("Qdrant collection %s is ready with dimension=%s.", settings.qdrant_collection, dimension)
    print(f"collection={settings.qdrant_collection} dimension={dimension}")
    return 0


def list_documents_command(args: argparse.Namespace) -> int:
    from storage.db import connect
    from storage.models import RawDocumentQuery
    from storage.repositories import RawDocumentRepository

    settings = load_settings()
    setup_logging(settings)
    query = RawDocumentQuery(source=args.source, doc_type=args.doc_type, limit=args.limit)
    with connect(settings) as connection:
        documents = RawDocumentRepository(connection).list(query)

    if not documents:
        print("No documents found.")
        return 0

    for document in documents:
        fetched_at = document.fetched_at.isoformat() if document.fetched_at else ""
        print(
            f"{document.source} | {document.doc_type} | {document.title} | "
            f"content_len={len(document.content)} | fetched_at={fetched_at} | {document.url}"
        )
    return 0


def list_chunks_command(args: argparse.Namespace) -> int:
    from storage.db import connect
    from storage.models import DocumentChunkQuery
    from storage.repositories import DocumentChunkRepository

    settings = load_settings()
    setup_logging(settings)
    query = DocumentChunkQuery(embedding_status=args.embedding_status, limit=args.limit)
    with connect(settings) as connection:
        chunks = DocumentChunkRepository(connection).list(query)

    if not chunks:
        print("No chunks found.")
        return 0

    for chunk in chunks:
        preview = chunk.content.replace("\n", " ")[:80]
        print(
            f"{chunk.raw_document_id} | index={chunk.chunk_index} | "
            f"chars={chunk.char_count} | status={chunk.embedding_status} | {preview}"
        )
    return 0


def list_market_command(args: argparse.Namespace) -> int:
    from storage.db import connect
    from storage.models import MarketSnapshotQuery
    from storage.repositories import MarketSnapshotRepository

    settings = load_settings()
    setup_logging(settings)
    trade_date = parse_date_arg(args.date) if args.date else None
    query = MarketSnapshotQuery(
        trade_date=trade_date,
        code=args.code,
        source=args.source,
        instrument_type=args.instrument_type,
        limit=args.limit,
    )
    with connect(settings) as connection:
        snapshots = MarketSnapshotRepository(connection).list(query)

    if not snapshots:
        print("No market snapshots found.")
        return 0

    for snapshot in snapshots:
        instrument_type = snapshot.metadata.get("instrument_type", "")
        data_provider = snapshot.metadata.get("data_provider", "")
        print(
            f"{snapshot.trade_date.isoformat()} | {snapshot.code} | {snapshot.name} | "
            f"open={snapshot.open} close={snapshot.close} pct_chg={snapshot.pct_chg} "
            f"amount={snapshot.amount} source={snapshot.source} type={instrument_type} provider={data_provider}"
        )
    return 0


def analyze_market_command(args: argparse.Namespace) -> int:
    from analysis.market_context import build_market_context
    from storage.db import connect
    from storage.models import MarketSnapshotQuery
    from storage.repositories import MarketSnapshotRepository

    settings = load_settings()
    setup_logging(settings)
    trade_date = parse_date_arg(args.date)
    with connect(settings) as connection:
        snapshots = MarketSnapshotRepository(connection).list(MarketSnapshotQuery(trade_date=trade_date, limit=args.limit))
    context = build_market_context(snapshots, trade_date)

    print(f"date={context.trade_date.isoformat()} snapshots={context.snapshot_count} stocks={context.stock_count} indexes={context.index_count}")
    print(f"observed_total_amount={context.observed_total_amount:.0f} amount_tier={context.amount_tier}")
    print(f"market_style={context.market_style} sentiment_cycle={context.sentiment_cycle}")
    print("indexes=" + format_instruments(context.indexes))
    print("strong_stocks=" + format_instruments(context.strong_stocks[:5]))
    print("weak_stocks=" + format_instruments(context.weak_stocks[:5]))
    print("volume_leaders=" + format_instruments(context.volume_leaders[:5]))
    print("sector_hotspots=" + format_sectors(context.sector_hotspots[:5]))
    print("evidence_gaps=" + ",".join(context.evidence_gaps))
    return 0


def score_events_command(args: argparse.Namespace) -> int:
    import json
    from datetime import datetime, time

    from analysis.events import extract_event, score_event
    from analysis.market_context import build_market_context
    from storage.db import connect
    from storage.models import MarketSnapshotQuery, RawDocumentQuery
    from storage.repositories import MarketSnapshotRepository, RawDocumentRepository

    settings = load_settings()
    setup_logging(settings)
    active_date = parse_date_arg(args.date)
    start_time = datetime.combine(active_date, time.min)
    end_time = datetime.combine(active_date, time.max)
    with connect(settings) as connection:
        documents = RawDocumentRepository(connection).list(
            RawDocumentQuery(
                start_time=start_time,
                end_time=end_time,
                doc_type=args.doc_type,
                source=args.source,
                limit=args.limit,
            )
        )
        snapshots = MarketSnapshotRepository(connection).list(MarketSnapshotQuery(trade_date=active_date, limit=1000))
    market_context = build_market_context(snapshots, active_date)
    for document in documents:
        event = extract_event(document)
        score = score_event(event, market_context)
        print(json.dumps({"event": event.to_dict(), "score": score.to_dict()}, ensure_ascii=False))
    return 0


def format_instruments(instruments) -> str:
    if not instruments:
        return "none"
    return "; ".join(
        f"{item.code} {item.name} pct={format_optional_float(item.pct_chg)} amount={format_optional_float(item.amount)}"
        for item in instruments
    )


def format_sectors(sectors) -> str:
    if not sectors:
        return "none"
    return "; ".join(
        f"{item.sector} count={item.stock_count} avg_pct={format_optional_float(item.average_pct_chg)} amount={format_optional_float(item.total_amount)}"
        for item in sectors
    )


def format_optional_float(value) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


def list_skills_command() -> int:
    from app.skills import list_skills

    settings = load_settings()
    skills = list_skills(settings)
    if not skills:
        print("No skills found.")
        return 0

    for skill in skills:
        stage = f" | stage={skill.stage}" if skill.stage else ""
        version = f" | version={skill.version}" if skill.version else ""
        print(f"{skill.name} | {skill.description}{stage}{version}")
    return 0


def show_skill_command(args: argparse.Namespace) -> int:
    from app.skills import load_skill

    settings = load_settings()
    skill = load_skill(settings, args.name)
    print(f"# {skill.name}")
    if skill.description:
        print(f"\n{skill.description}")
    if skill.version:
        print(f"\nVersion: {skill.version}")
    print(f"\nPath: {skill.path}")
    print("\n---\n")
    print(skill.body)
    return 0


def test_llm_command(args: argparse.Namespace) -> int:
    from analysis.llm import ChatMessage, LLMClient

    settings = load_settings()
    logger = setup_logging(settings)
    try:
        client = LLMClient(settings)
    except ValueError as exc:
        print(str(exc))
        return 1
    content = client.chat_text(
        [
            ChatMessage(role="system", content="你是一个简洁的连通性测试助手。"),
            ChatMessage(role="user", content=args.prompt),
        ],
        temperature=0,
    )
    logger.info("LLM provider=%s model=%s responded.", settings.llm_provider, settings.llm_model)
    print(content)
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "show-config":
        return show_config()
    if args.command == "collect":
        return collect_command(args)
    if args.command == "collect-market":
        return collect_market_command(args)
    if args.command == "collect-announcements":
        return collect_announcements_command(args)
    if args.command == "collect-news":
        return collect_news_command(args)
    if args.command == "init-db":
        return init_db_command()
    if args.command == "sync-notion":
        return sync_notion_command()
    if args.command == "refresh-knowledge":
        return refresh_knowledge_command()
    if args.command == "build-index":
        return build_index_command(args)
    if args.command == "sync-vector-index":
        return sync_vector_index_command(args)
    if args.command == "search-knowledge":
        return search_knowledge_command(args)
    if args.command == "ensure-vector-collection":
        return ensure_vector_collection_command(args)
    if args.command == "list-documents":
        return list_documents_command(args)
    if args.command == "list-chunks":
        return list_chunks_command(args)
    if args.command == "list-market":
        return list_market_command(args)
    if args.command == "analyze-market":
        return analyze_market_command(args)
    if args.command == "score-events":
        return score_events_command(args)
    if args.command == "list-skills":
        return list_skills_command()
    if args.command == "show-skill":
        return show_skill_command(args)
    if args.command == "test-llm":
        return test_llm_command(args)
    return run_placeholder(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
