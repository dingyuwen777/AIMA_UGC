# Content 模块

Content 是 Canonical Content/Comment 业务事实的唯一写 Owner。Stage 6 已建立 Account、Content/Comment
Current、Version、Metric Observation 与评论覆盖表，以及 Canonical → Ingestion Service → PostgreSQL
Repository 的首个小红书纵切。

## 生产入口

- `aima_ugc.modules.content.ContentIngestionService`：只接受 `CanonicalContentV1` / `CanonicalCommentV1`，
  把写入委托给 Content Owner Repository；
- `aima_ugc.adapters.persistence.postgres.content.PostgresContentRepository`：在调用方持有的 SQLAlchemy
  Session/事务内写 Current、Version、Metric 与 Account，不提交事务、不解释 Provider 私有字段；
- `aima_ugc.modules.content.tables` / `account_tables`：Content Owner 的关系表机器事实；
- `aima_ugc.modules.content.InMemoryContentRepository`：只用于快速验证领域合并语义，不替代 PostgreSQL
  Repository 或数据库约束测试。

写入按 `observed_fields` 稀疏合并。业务 Hash 只与当前版本比较，因此 `A → B → A` 形成三个版本；指标
首次、变化和每日无变化检查点分别留痕，指标下降也是有效观察。

## 独立验证

```bash
uv run pytest tests/unit/content -q
uv run alembic upgrade head
uv run pytest tests/integration/content -q
uv run alembic check
```

Unit 使用固定 Canonical 观察验证合并语义；Integration 使用隔离 PostgreSQL 18、正式 Migration、
Candidate/Raw 来源链和 PostgreSQL Repository，覆盖内容/评论版本、指标、事务回滚、追加账本约束和小红书
已存 Raw 回放。完整环境由 `Stage 6 XHS Vertical Slice` CI 固定验证。

## 当前限制

- 当前没有 Query Repository/Read Model、公开 HTTP API 或前端页面；
- 当前生产映射纵切只覆盖小红书 TikHub App V2；其余平台必须另建 Operation/Fixture/Mapper；
- `InMemoryContentRepository` 不证明数据库约束、并发、Migration 或事务正确；
- 没有启用真实 Provider Transport 或最终预算，普通测试和 CI 不访问 TikHub。
