# AIMA_UGC Operations

`docs/operations/` 承担**已经存在的运行/部署能力怎样操作，以及真实生产动作需要满足什么门禁**。它与 Roadmap 的区别是：

```text
Operations
→ 当前能力怎么运行、部署、恢复、迁移、排障

Roadmap
→ 还有哪些已经批准但尚未完成的生产目标
```

当前运行文档：

- [`docs/operations/01_生产部署与离线Release方案.md`](01_生产部署与离线Release方案.md)：Docker/Compose、宿主目录、Secret、离线 Release、发布/回滚边界；
- [`docs/operations/02_4000万历史迁移与Analysis Run运行手册.md`](02_4000万历史迁移与Analysis%20Run运行手册.md)：统一 Data Import Campaign、Historical Fill-Only、容量门禁、迁移对账和手动 Analysis Run。

常用开发/本地运行命令仍由 [`docs/02_环境运行与部署.md`](../02_环境运行与部署.md) 维护；Windows Docker Desktop 操作见 [`docs/guides/03_Windows Docker Desktop Compose运行.md`](../guides/03_Windows%20Docker%20Desktop%20Compose运行.md)。

## 当前部署结论

当前仓库已经具备 Internal V1 的 Docker/Compose 运行基线和 GitHub 离线 Release 基础。不能再把 [`Dockerfile`](../../Dockerfile)、[`compose.yaml`](../../compose.yaml)、[`env.production.example`](../../env.production.example)、`images.tar`、manifest、`SHA256SUMS`、`DEPLOY.md` 或 no-build/no-pull 回放整体描述成“尚未实现”。

完整 Production 仍是 No-Go。未完成事项由 [`docs/roadmap/02_生产上线实施路线.md`](../roadmap/02_生产上线实施路线.md) 维护，Operations 文档不能把未来 Backup/Restore、企业认证、供应链强化或生产实机验收写成已经完成的命令。

## 当前 4000 万结论

大规模历史导入的软件能力已经完成。当前未完成的是：

- 公司服务器 500 万或业务批准的等效比例容量演练；
- 生产写授权；
- 4000 万正式 Campaign；
- 全量结果/冲突/资源账本对账。

这些未完成门禁由 [`docs/roadmap/03_4000万历史数据迁移实施方案.md`](../roadmap/03_4000万历史数据迁移实施方案.md) 维护；运行细节由本目录的运行手册维护。

## Operations 文档规则

1. 命令必须来自当前仓库真实脚本/Compose/Workflow；
2. 不伪造服务器执行证据；
3. 不把开发机/CI 证据当作生产实机证据；
4. 破坏性操作、生产写入、Secret、备份恢复必须明确授权和回滚边界；
5. 已实现能力与待实现目标必须分段写；
6. 精确机器事实回到当前代码、配置、Workflow 和锁文件。
