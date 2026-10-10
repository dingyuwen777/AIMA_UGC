# 共享源码开发快照

团队成员从 Git 获取同一份业务子集，运行原来的 `uv run python scripts/dev/backend.py`。只有固定源码开发 PostgreSQL 中尚无应用 Schema 时会自动恢复；随后正常 Migration、配置 Provider、启动 Worker/API。已有 Schema（即使没有帖子）一律保留。

快照固定为 [aima_recent30.tar.gz](aima_recent30.tar.gz)，由 Git LFS 管理。首次 clone 前安装 Git LFS 并运行 `git lfs install`；已有 clone 缺少大文件时运行 `git lfs pull`。如果只有指针，启动器会给出相同提示。正常启动不会下载或更新快照。

## 生成和更新

服务器使用已有 `aima_recent30_transfer.sh export`，按该脚本的参数指定容器、数据库、Artifact 根与输出文件。输出格式保持 `aima-recent-content-postgresql.v1`。将原始文件放到本目录，经代码审查和正常 Git/LFS 提交流程更新，不重新压缩或转换。服务器脚本 SHA-256 来源及本次专项验收由对应 Change/Issue 记录；这里不维护另一份 Schema 或表清单。

这是按帖子时间窗口及关联闭包导出的开发数据，不是生产全量备份。包含已有 AI/人工结论、评论、品牌车型和实际存在的 Artifact；`missing_artifacts` 列出不可恢复的文件。它来自经授权的共享 Git 数据，`schema.dump` 含可执行 DDL，不能拿任意来源的归档替换。

## 本地使用与保护边界

恢复只使用 Windows/Linux Python、现有依赖及 Docker CLI，容器内运行 PostgreSQL 客户端。无需 Bash、WSL 或宿主 `psql`。完整 Compose、Release 和前端入口不导入；CI 默认跳过共享真实包，永久测试使用小型合成快照。数据包不进入 Docker 镜像。

容器、卷、回环端口、Role 和数据库必须匹配源码开发常量，远程 Docker/Compose/未知目标拒绝。无包保持原有启动；`backend.py --skip-seed` 跳过共享包，`--validate-only`/`--prepare-only` 不恢复。已证明属于当前数据库的失败现场仍阻止迁移与业务启动，skip 无法绕过。

首次校验需要展开全部文件，检查大小、SHA、CSV 行数、实际 FK、PG 主版本及 Alembic 升级路径，并检查宿主与 Docker 空间。耗时与数据规模有关。较旧已知版本先恢复再正常升级；较新或未知版本须先更新代码。正常重复启动只检查归档身份及实际 DB 完成状态，不重新展开全部 CSV。

状态文件 `.runtime/dev/seed-state.json` 属于本机缓存，不能替代实际数据库。固定开发卷内还保存按数据库绑定的专用恢复状态；另一 checkout 即使没有本地缓存或跳过快照，也不能绕过失败保护。恢复完成后数据库与原工作目录的 Artifact 根绑定，避免其它目录误用缺文件的数据库。容器重建但复用原卷仍保留保护。快照更新不会覆盖本地数据；需要采用新版时显式重置。

历史 queued/running Job 会取消，计划及导入的 Provider 停用，成功 AI/Run 及结果保持。本地正常 Provider 配置仍可用于新任务，内部投影/工作台预热沿用现有机制。含飞书活动镜像或认证会话的归档拒绝恢复，避免共享快照重启外部活动或复制登录状态。

## 维护命令

在仓库根运行，PowerShell 和 CMD 相同：

```powershell
uv run python scripts/dev/seed_data.py status
uv run python scripts/dev/seed_data.py verify
uv run python scripts/dev/seed_data.py reset --dry-run
uv run python scripts/dev/seed_data.py reset --execute
```

`status` 只读查看实际容器/DB、内容/评论/AI计数、快照身份与版本变化；Docker或容器不可用时明确报错。`verify` 只校验归档和当前升级链，不写数据库；临时展开文件自动清理。

恢复失败会记录状态并保留数据库与 Artifact，禁止假成功或自动清空重试。先停止所有源码 API/Worker/Scheduler，查询状态并保留现场。确认不再需要本地业务数据后，先查看 dry-run，再 execute 并手工输入 `RESET aima_ugc`。命令只重建固定开发数据库，保留卷、内部 Secret 和全部 Artifact；未知/不同内容文件不删除，后续冲突须人工核对。重置后运行原后端命令恢复当前共享包。

启动器从恢复、Migration 到业务子进程退出持续持有共享锁，与第二启动及 reset 互斥；数据库仍有其它连接时也拒绝写入。reset 在删库后中断时保留共享归属，可经同一确认入口继续创建空库；若发现陌生重建的数据库则保护并报错，不自动删除。禁止为绕过失败而手工删除状态文件。代码回滚本身不删除已恢复数据，也不能把本功能当生产备份、迁移或灾备方案。
