# WisersOne 本地与 Linux 验证证据

最终产品 revision：`18eec1e025eb1309dd39ba80b0bf69d3d422f234`；base：`3e13cccf63a75b05eec12e302d557c3cf99dcaac`。本轮日期按北京时间为2026-10-03。本文记录实际输出，远端 CI、merge 与合并后事实由 PR/Actions 持有，不能用本文代替。

## 自动回归

执行 `.venv/Scripts/python.exe .runtime/wisersone-task/run_preflight.py --fix`，临时入口只调用项目 `scripts/dev/validate_changed.py` 的 classifier、build_fix_commands 和 build_validation_commands，为 Windows 解析真实 `npm.CMD`。没有另建 scope mapping。原输出 `.runtime/wisersone-task/preflight-final.log`，退出码0。

| 实际命令 | 结果 |
| --- | --- |
| `uv run ruff format --check <classifier的当前Python文件>` | PASS |
| `uv run ruff check <同一文件清单>` | PASS |
| `uv run mypy backend/src` | 454个source，无错误 |
| `uv run pytest tests/unit tests/contracts tests/api -q` | 2066 PASS，16既有skip，12subtests PASS，4310既有warning，92.31秒 |
| `uv run python scripts/contracts/generate.py --check` | PASS，无生成漂移 |
| `uv run python scripts/contracts/check_compatibility.py` | PASS |
| `npm --prefix frontend run lint` | PASS |
| `npm --prefix frontend run test -- --run` | 38文件、306项PASS |
| `npm --prefix frontend run build` | PASS；保留既有bundle体积提示 |
| `npm --prefix frontend run test:e2e` | 205项PASS，3.6分钟；包含默认Wise共用弹窗、频率/品牌请求及取消/恢复/结果 |

Secret检查另执行 `.venv/Scripts/python.exe scripts/quality/scan_secrets.py`：PASS。例外只覆盖已获用户批准的两个初始JSON的SEC002/003；private-key规则和其它路径不豁免。

## 真实 PostgreSQL 与完整工作流

所有数据库属于带 `aima.task=wisersone-700` 标签的隔离 PostgreSQL18容器，端口55470。没有使用或清空既有用户数据库。测试 Secret 不输出。

- Windows：`pytest tests/integration/ingestion/test_wisersone_review_regressions.py tests/integration/ingestion/test_wisersone_workflow.py tests/integration/ingestion/test_wisersone_plans_lifecycle.py tests/integration/ingestion/test_wisersone_recovery_permissions.py -q`：13 PASS，109既有warning，14.53秒。独立 `test_wisersone_review_boundaries.py`：8 PASS，107既有warning，10.05秒。
- Linux：从根Dockerfile当前正式backend candidate增加临时层，只复制锁定pytest依赖与五份目标test；**未复制AIMA生产源码**。`docker run --rm ... aima-ugc-wisersone-700:linux-tests` 调用镜像已安装wheel：21 PASS，109既有warning，32.11秒。
- 正式candidate分别执行 `python -m alembic upgrade head`、`current`、`check`：`20261003_0082 (head)`，`No new upgrade operations detected`。全栈新建空库完整执行全部迁移亦到0082并无漂移。
- `.venv/Scripts/python.exe .runtime/wisersone-task/run_fullstack_final.py` 启动本任务隔离API、正式Worker注册（只替代外部网站/TikHub/LLM边界），然后 `npm --prefix frontend run test:e2e:fullstack`：**19 PASS，3.7分钟，exit0**。使用`wisersone_fullstack_serial_700`及独立目录。结束只停止脚本创建的API/Worker/LLM进程。
- 新Wise工作流1.6分钟通过：默认Wise弹窗→名称/3小时频率/品牌→真实Scheduler唯一Occurrence→真实30秒Job续跑→Source/生产Reader/Mapper/Canonical/Owner→一条新建一条过滤→任务结果/声音广场。没有人为提早Job时间或复制入库规则。

第一轮full-stack为18 PASS/1 FAIL：原有Excel测试等待时弹窗消失，后台于15:24:56已经完成；并行客户端生成mtime15:25:00，API随后重新读取principal，符合热更新重建页面状态。停止生成后串行复测原测试11.6秒PASS，未修改测试、断言或预算。重跑准备时发现父Python继承`SSLKEYLOGFILE`引起本机健康探测PermissionError，仅清本任务进程环境后直连本机服务；不修改系统设置。

## 审查反例与修复机制

独立Review首轮WIS-DR-01/02/03对应4个反例在修复前Red；修复后13项目标测试Green，并增加8项独立边界。Red阶段根据真实HTTP路由将错误的202期待改为200，并根据`skip_locked`修正为检验cleanup是否认领/删除；没有放松业务安全断言。

- 取消意图同事务持久保存，并由同一Job type的cancel阶段传播；Campaign未settle时保持cancelling；最后Chunk先完成时保留实际succeeded；耗尽attempt仍续传播。
- 同一Campaign监控恢复、暂态发现/快照恢复和失败Chunk恢复分别处理；ready/running/succeeded可恢复观察；永久无效输入拒绝，不重新导出。
- WisersOne和既有Campaign retry先锁Download，后锁Campaign；激活与恢复同事务。cleanup先认领时两入口均409；retry先认领时cleanup跳过活动文件；保留Canonical可解析。

## 真实网站、打包与镜像

真实导出只核验ZIP CRC、结构、所需表头和文件hash；**不审核数据内容业务正确性**。Windows与Linux均无密码提示，记录见同一evidence目录的windows-download.json、linux-download.json、linux-final.json。

最终真实Linux导出在13:43:45至14:31:51之间完成，整个流程48分06秒。该事实证明流程跨30分钟仍能取得文件，不将全部耗时归因于网站生成。文件17,782,821字节。最终修复只影响bootstrap/PG取消恢复，Provider/Auth代码未改变；当前candidate逐模块hash与本轮source相同，原真实网站证据仍覆盖该外部边界。

正式镜像：`sha256:eb5cffe47c32f68ad41c246de0cddf27dc9792f64521d48736f31aac784d3f34`。实际uid10001启动headless Chromium，无需运行时下载。实际安装路径均为site-packages，含2份JSON和人工入口；同一刷新的host auth经过升级prepare后hash未变化。源码hash/包hash见candidate.json。

`uv build --out-dir .runtime/wisersone-task/package-artifacts`：exit0，当前wheel与sdist重新打开/CRC/JSON解析成功，各含两份JSON，不含.runtime或测试Secret。wheel包含人工入口。rootbuild context、Python3.14.7、Playwright1.62.0与锁定依赖未升级。

## 正式交付边界

本地证据不冒充当前PR CI或合并后main-fresh。用户明确授权Agent完成本地/Linux技术验证后合并，未把用户本人验收标为PASSED。PR #701最终CI、guarded merge、native archive、Issue状态写回与closure、缓存/任务分支cleanup仍须按真实平台结果继续执行。Release、Deploy、生产Migration和生产导入未授权、不执行。

## 最终共享文件修复与当前环境阻塞

WIS-DR-04：新增正式公开server_path消费者对同一受管原Excel的准入与保留保护，复用持久冻结目录范围及短事务advisory gate，不新增Schema。清理先认领时原子409，不创建Campaign/Job；新消费者先提交时保护Discover、Source复制及复制后复核，全部消费者终态满七天后才能清理。Windows路径等价按锁定Python3.14.7的OS normcase，Linux保留大小写。

- 校准共享输入Red：14 FAIL/3 PASS，18.76秒；大小写Red：6个实际安全断言FAIL，6.76秒，前一个连接超时日志不算产品Red。
- 当前全部六份PG测试：45 PASS，109既有warning，54.72秒，`pg-final.log`，exit0。包含独立Source和Canonical完整导入、7天清理及Windows大小写，暂存目录大小写也拒绝。
- 当前Ruff与Mypy454 PASS；`pytest tests/unit tests/contracts tests/api -q`：2066 PASS/16既有skip/12subtests PASS，84.04秒，`backend-final.log`，exit0。追加Unicode正式Browser读取/发现控制：3 PASS，0.48秒。Windows normcase实为LCMapStringEx，U+0130不展开。
- `preflight-repair2.log`：项目唯一classifier完整执行，生成漂移/兼容、frontend lint/build PASS，306单元PASS、205浏览器PASS（3.5分钟）。后续仅目录等价Python修正，不改变前端或公共Contract；后端按上一项刷新。
- 当前wheel/sdist重新打开CRC/JSON/入口PASS，全部454份wheel源码与当前源码逐文件相等；当前包身份另见package-current.json。`candidate.json`保持此前e5baa候选真实身份，不改写成最新镜像。

18eec最终本机构建未成功：Docker数据盘在D盘，宿主仅约24MB可用，Linux内核记录I/O error、ext4 aborted journal并切换只读；`candidate-final-build.log`明确失败。最终installed Linux PG和新full-stack未执行成功（createdb I/O失败及准备Migration失败），不能记为PASS。未删除旧DB、重置Docker或在无备份情况下fsck。Windows最终验证仍有效，Linux旧阶段成功只证明当时边界。

## 用户追加交付决定与当前 CI 路径

2026-10-03 用户明确要求：“如果前面验证过没问题，就合并到主分支吧”。该决定已同步并重读 live Issue #700，AC1–AC13保留。

据此复用本轮既有真实 Windows/Linux 下载、正式非 root 镜像、installed-package PG 和19项 full-stack 验证，不再等待本机磁盘恢复后重复整套本地 Linux 验证。最终产品修复的 Windows45项PG、后端2066项和Unicode3项控制、当前wheel454源码检查仍是当前实现的直接证据。旧candidate身份保持原revision，不称为18eec新构建成功。

当前PR必须由项目正式CI取得Linux新鲜证据：PostgreSQL Integration包含六份WisersOne测试和空库迁移；Real Full-stack Golden Path运行真实API/Scheduler/Worker/PG与浏览器；Compose Golden Path构建根Dockerfile正式镜像并运行。原生 `validate_changed.deferred_ci_layers` 也将真实PG/full-stack留给正式CI。独立Review、Completion以及current-head/current-base required checks继续是merge前门禁。远端结果以PR/Actions持有，不预先写PASS。

本机Docker只读导致的task-owned镜像/构建缓存清理限制是另一个收尾轴，不能冒充已清理，也不以清理阻塞撤回已经取得的产品验证事实。认证运行态已单独保留到默认AIMA_HOST_ROOT/runtime/wisersone-auth；该持久状态不属临时缓存。main-fresh、原生自动归档、Issue Closure及限定cleanup仍按实际结果继续。

有限独立复审最终报告原文保存在 `review-final.md`：WIS-DR-01至04 resolved，代码范围 NO_FINDINGS_WITHIN_SCOPE，本地Completion准入获支持，当前CI/merge clearance仍pending。Owner据此准确更新R12/R14/R15/R16与完成审计，并实际执行 `scripts/quality/check_change_completion.py --root . --require-active-ready`：PASS（159 gated/strict，128 legacy）。初次严格检查暴露Change列表和来源的机器格式错误，已仅修正metadata为正式块列表和稳定AC绑定；未改变产品、验证断言或完成语义。canonical governance_contract validate-change及validate-pr亦PASS。

## 正式 CI 首轮与检查同步

carrier `02a23c3087ef551be52e27ed23bb55c1a090732b` 的实际完整CI：`37116942170`，Runtime `37116941912`，Release只读dry-run `37116941849`，Tooling `37116941841`。

- 正式Linux full-stack通过；离线候选构建和严格回放通过；Linux/Windows工具链通过。当前CI总体仍失败，不据部分绿色合并。
- Linux单元1822 PASS/1 FAIL：原 `test_prepare_host` 的精确放宽目录集合仍只列data/log，遗漏已批准的Wise认证和输入bind；default Linux严格权限逻辑不改变。
- Linux PG collection236 PASS/1 FAIL：原 `test_collection_worker_runtime` 精确Registry列表遗漏正式新增的Wise Job，既有所有类型和顺序保持。
- Compose已通过主Linux运行步骤，但Windows overlay精确mount字典仍漏新增Wise bind，失败在bootstrap集合比对。

修正仅同步既有强断言：Windows兼容精确列四个bind目录且其它目录全部strict；Registry精确列表添加实际Wise类型；正式Runtime exact mounts补新增挂载并增加宿主源路径、API只读、Worker/Scheduler可写检查。没有删测试、改预算或把等号改成包含。prepare_host只改注释和CLI说明，不改运行逻辑；Operations记录既有Windows权限翻译边界。

本地重新执行同一Runtime workflow内嵌validator，输入为实际 `docker compose -f compose.yaml -f compose.windows.yaml config --format json`：PASS。目标Unit/部署/CI检查51 PASS/6既有POSIX skip，0.49秒；Ruff检查和format通过。首次sandbox运行出现pytest目录WinError5属于宿主权限错误，已在授权正常宿主环境原断言重跑；不算产品失败或通过。三个Linux实际失败的修正仍须下一current-head正式CI得到Green；PR已返回Draft修正，不绕过门禁。
