# 飞书分应用配置与多行模板补充验收

## epoch 4：唯一登录配置与恢复远程交付

最新唯一需求 [#714](https://github.com/dingyuwen777/AIMA_UGC/issues/714) live updated_at `2026-10-10T05:01:08Z`，candidate/create 与 live 校验 PASS、重读字节一致。用户明确取消旧单应用配置兼容，并授权本地全部任务修改验证后合并远程 main。以下结果基于 HEAD `2510bd272840f73a338b123f4b8fc20324a8e7f1` 上的最终未提交增量；fetch 后 origin/main 仍为 `e1a7f13bca75110b26d4836d3c707bc20aab667c`，已包含在任务分支。人工额外等待记 USER_WAIVED，不冒充人工已验收。

本轮删除 Settings 中旧登录组/回调字段、ENV 映射及 `build_feishu_auth_settings` fallback。登录仅按 CONNECTORS 注册表装配，一项即单应用；正式模式缺数组拒绝启动。旧非空组/回调变量在 Settings 与源码入口明确拒绝，不能静默忽略并回退开发管理员。报告/多维表应用与 Secret 引用独立校验/消费；CONNECTORS 内手工引用模式继续允许，HTTP 登录别名与公开 Contract 保持。两份模板、部署说明和运维手册同步唯一配置源。

| 命令 / 边界 | 结果 |
| --- | --- |
| 新配置目标用例，修复前 | 5 failed，分别验证旧变量拒绝、移除字段、报告应用独立；错误 import 夹具先修正后才取得有效 Red |
| `pytest tests/unit/identity/test_feishu_connector_only_config.py tests/unit/identity/test_feishu_auth_http.py tests/unit/identity/test_settings_multi_connector.py -q` | 70 passed，退出0 |
| `pytest tests/unit/identity tests/unit/platform/test_feishu_config_input.py tests/unit/platform/test_local_dev_runtime.py tests/unit/test_env_compose_config_contract.py tests/unit/test_ci_scope.py tests/unit/test_release_bundle.py -q` | 308 passed / 8 skipped，退出0，平台条件跳过 |
| `python scripts/dev/validate_changed.py --base origin/main --execute` | 正式 classifier full；后端2653 passed / 22 skipped / 12 subtests，mypy480 files、Ruff、Contract/兼容、前端lint、Vitest361、Typecheck/Build均通过。整条退出1：末尾默认六并发Browser148PASS/70FAIL，测试站点4173随后拒绝连接，服务退出原因未恢复，不伪称完整命令退出0 |
| `CI=true npm --prefix frontend run test:e2e -- --workers=3 --retries=0` | 隔离重新启动测试站点，完整218 passed / 3.8m，退出0；无自动重试、无生产或测试逻辑改动。使用项目CI三并发配置 |
| `python scripts/quality/check_env_templates.py --compose` | Linux Compose + Windows overlay 实际解析通过，未启动业务服务 |
| `python scripts/quality/check_change_completion.py --root . --require-active-ready` | PASS，gated164 / strict164 / legacy128；premerge施工完成，不冒充平台交付已结束 |
| 文档、Secret、事实、治理入口检查 | 正式preflight均PASS；F3文档修复后模板/docs另行PASS |

原始输出见 [配置 Red](feishu-config-logs/epoch4-red.txt)、[定向回归](feishu-config-logs/epoch4-targeted.txt)、[完整 preflight](feishu-config-logs/epoch4-preflight.txt)、[修后完整 Browser](feishu-config-logs/epoch4-browser.txt)、[实际 Compose](feishu-config-logs/epoch4-templates.txt)。首轮仅新增测试签名格式失败已由 Ruff 收敛，保留为 [格式修复前](feishu-config-logs/epoch4-format-before.txt)。沙箱首跑解释器/临时目录访问失败属于执行环境，不计为业务 Red；另一次扩大到非正式 scripts 范围的 mypy 31错误不作为正式门禁结果，正式命令 `mypy backend/src` 480文件通过。

独立 Reviewer `/root/feishu_config_review` 按 epoch4 live Source 与增量重新闭合投影，F3指出生产模板“三处共读/旧兼容”及运维旧扁平指引矛盾，整组修复后 CLOSED；最终 NO_FINDINGS_WITHIN_SCOPE，原F1/F2继续CLOSED。模板随后仅去掉EOF多余空行，Parent确认无语义变化；代码/测试未再作行为修改。Reviewer直接读70和308结果，Parent完整读回2653/361/218与退出码。

本轮无新 Migration、依赖或 Runtime升级；0087继续保持。旧扁平登录配置按明确决定不兼容，回退仍须保留 Secret/用户配置；回退有认证漏洞版本先访问隔离。旧Linux正式wheel/UID10001凭据写读、真实Compose多行输入证据按未改变helper边界复用（helper SHA256仍为 `BFC6D4B3BC779DBBE7A459CBC0137BD048E62224FCCABB96555F85382DC14775`），由正式PR CI再证明当前Linux组合。真实企业OAuth/生产HTTPS/正式部署/Release未验证。

交付改为通过 current-head/current-base required CI 后 guarded REST merge，随后验证 main fresh CI、原生 Change Archive 与Issue Closure，清理任务分支和临时资源；平台操作事实以PR/Commit/Actions为Owner，不提前冒充。保留用户真实env、Secret、数据库与依赖，不发布、不部署、不操作生产数据。

## epoch 3 历史记录

以下为已完成前轮的原始配置补充记录；其中“旧单应用兼容”“暂停合并”和人工PENDING已被上方epoch4决定取代，不作为当前配置或交付边界。

Requirement Source：[#714](https://github.com/dingyuwen777/AIMA_UGC/issues/714) AC23，decision epoch 3。2026-10-10 重新 live 读取，`updated_at=2026-10-10T03:48:32Z`，与已通过写前及 live 校验的 candidate 字节一致。用户要求本地验证，暂停远程 main 合并。

当前基线/HEAD：`2510bd272840f73a338b123f4b8fc20324a8e7f1`。本补充仍是其上的未提交工作区；开发分支 `feat/714-role-export-preferences` 保留，Human Local Acceptance PENDING。此前 R1–R22 证据继续按原记录使用，不冒充本次全部重新执行。

## 修改与反向核对

| 文件 / 边界 | 当前行为 |
| --- | --- |
| `env.local.example`、`env.production.example` | CONNECTORS 改为外层单引号、两空格缩进的多行 JSON，每应用一对象，凭据及组配置各占一行；精简单/多应用重复说明；源码回调 5173、Compose 实际入口和生产 HTTPS 分别说明。保留用户已有非敏感 App ID/组 ID，App Secret 留空 |
| `scripts/dev/local_runtime.py` | 共享 env 赋值解析支持单引号多行值及转义单引号，不插值、不执行命令；源码启动按应用生成 Secret 文件，只把移除明文后的 Connector 传入业务进程，敏感原始配置不进入 dataclass repr |
| `backend/src/aima_ugc/bootstrap/feishu_config_input.py` | 正式 Connector 校验后拆分凭据/公开配置；缺省引用、轮换、手工文件兼容；重复字段/身份/引用、保留文件名、父子路径、链接及 Windows 文件名等价在写入前拒绝，错误不回显输入 |
| `scripts/deploy/prepare_host.py`、`compose.yaml`、`compose.windows.yaml` | bootstrap 唯一接收原始 CONNECTORS，固定已解析 root 写凭据与无明文 manifest；业务容器读取 manifest，Migration/Scheduler 也可读。Linux 文件 UID/GID 10001:10001、0600，源码 Windows 保留 owner=None |
| `backend/src/aima_ugc/platform/config/settings.py` | 内部 manifest 加载、空配置 sentinel/旧单应用兼容；绕过 launcher 直接传入 app_secret 明文失败关闭，配置异常隐藏输入 |
| `scripts/quality/check_env_templates.py`、相关配置/Release/CI Scope 测试 | 复用同一多行解析，真实 Compose render，Release smoke env 改写不破坏原 Connector；非法模板测试不再假定旧的一行空赋值 |
| `frontend/e2e/workbench.spec.ts` | 仅小时刷新计数用例复用已有 unavailableRevision fixture，隔离合法的首次修订追赶；严格次数、标签、详情和深链断言保留，生产前端未变 |
| 环境运行指南、Blueprint 安全说明、飞书身份运维手册 | 同步自动落盘、原始 env 信任边界、重启/重建顺序、旧文件及报告应用兼容、回滚说明 |

反向核对：模板每项凭据 → source/Compose 输入解析 → Secret 文件及无明文运行配置 → 正式 Settings/Connector → 原 OAuth/Session；多企业和同企业多应用均保持独立 code/App ID/身份空间。内部 manifest 路径不要求用户手填。空凭据沿用手工文件，显式凭据重启轮换；不会在读取中删除旧文件。真实 `env.local`、用户 Secret 文件和正在使用的服务未改写或重启。

## 当前直接验证

原始命令输出保存在 [本轮日志目录](feishu-config-logs/validation.txt)；最终 Browser 单独保存在 [修后完整 Browser 输出](feishu-config-logs/browser-final.txt)。

| 实际入口 | 结果与边界 |
| --- | --- |
| `python scripts/dev/validate_changed.py --base 2510bd27 --execute` | 唯一 classifier 选 full；文档/Secret/事实/治理/模板、Ruff、mypy、后端、Contract、lint、Vitest、Typecheck/Build 均 PASS；该次整条命令因首次 Browser 5 FAIL 退出 1，未篡改为退出 0 |
| `uv run pytest tests/unit tests/contracts tests/api -q` | **2645 passed、22 skipped、12 subtests passed**，165.33s；4380 个既有 deprecation/fixture warnings。Windows/POSIX 等条件跳过不冒充 Linux 通过 |
| full preflight 中配置、身份、Release 三文件 | **46 passed、1 skipped** |
| `uv run mypy backend/src` / changed Python Ruff | **480 source files PASS** / format、lint PASS |
| `scripts/contracts/generate.py --check`、`scripts/contracts/check_compatibility.py` | PASS；无 HTTP/Schema/生成 Client 变更 |
| `npm --prefix frontend run test -- --run` | **361 passed / 42 files** |
| `npm --prefix frontend run build` | PASS，含两种 Typecheck，870 modules；既有 bundle 大小提示保留 |
| `npm --prefix frontend run lint` | 首轮及仅一行测试修正后均 PASS，0 warning |
| `npm --prefix frontend run test:e2e -- e2e/workbench.spec.ts --workers=1 --retries=0` | 未改测试时原 Workbench 文件 **39 passed**，1.2m |
| `npm --prefix frontend run test:e2e -- --workers=3 --retries=0` | 修正 fixture 后当前完整 **218 passed**，3.8m，退出 0；三并发与项目 CI 并发相同，未启用自动重试 |
| `pytest tests/unit/platform/test_feishu_config_input.py -q`，Windows | **32 passed、6 skipped**；skip 为 3 个 POSIX 条件和 3 个本机无符号链接创建权限条件 |
| 同一配置文件，隔离 Linux Docker / 正式 wheel | **30 passed、8 skipped**；8 项为 Windows 专属。实际执行 symlink、防穿越、prepare_host CLI、文件 owner/mode、新子进程降为 UID/GID 10001 后加载 Settings/Secret、literal `~/host` 单根路径及 Linux 大小写兼容 |
| 源码/身份/配置定向组 | **228 passed、10 skipped**；包含新输入、单/多 Connector、OAuth HTTP/Secret 和源码环境；与完整后端覆盖重叠，不累加为唯一测试数 |
| CI Scope / fullstack harness / template fixture 修复组 | **67 passed**；只更新旧模板一行假设，Windows subprocess 以 UTF-8 测试环境读取中文输出 |
| `python scripts/quality/check_env_templates.py --compose` | 最终真实 Linux + Windows overlay render PASS；未启动业务服务 |
| 隔离实际 Compose probe 容器 | 多行 JSON、中文、转义单引号与美元字符原样进入进程，`Compose multiline literal input PASS`；仅测试值、network none、run --rm |
| `check_change_completion.py --root . --require-active-ready` | 最终 PASS，carrier=changes、gated164、strict164、legacy128；仅本地 ready_for_review，不代表人工验收或 PR Ready |
| 最终 `check_docs.py`、`scan_secrets.py`、`check_docs_facts.py` | 均 PASS，覆盖补充说明和保存的测试输出 |

完整 preflight 使用 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`，仅在测试子环境移除主机 `SSLKEYLOGFILE`（原主机值指向不可写的外部日志路径），不修改系统环境或放宽生产认证。原第一次整套后端 5 FAIL/2640 PASS 由旧模板 fixture 和 GBK 子进程解码问题造成；原失败输出保留在 [编码与 fixture 修复前日志](feishu-config-logs/validation-before-encoding.txt)，修后完整后端为上表 2645 PASS。

首次完整 Browser 为 **213 PASS / 5 FAIL**，日志包含 Chrome GPU ring-buffer 分配失败、导航/hook 超时；四项几何失败单 worker 原文件全通过，最终三 worker 全套也通过，但不将所有首次超时武断归因于 GPU。另一项小时计数原断言 2 实际 3：trace 确认初始加载、首次修订追赶、小时刷新三条合法请求。仅该测试复用现有 unavailableRevision；首修订和慢请求协调仍有独立用例。无生产 UI 修复或断言放宽。

## 独立 Review

只读 Reviewer `/root/feishu_config_review` 最终 **NO_FINDINGS_WITHIN_SCOPE**，F1/F2 全部 CLOSED。审查同一未提交工作区：

- helper SHA256：`BFC6D4B3BC779DBBE7A459CBC0137BD048E62224FCCABB96555F85382DC14775`。
- Browser 测试 SHA256：`FA3D932E393F38E264D6435E58F19B7172735718695B873CEE76AE215674720B`。
- F1：Windows 大小写/设备名/尾点/保留名/父子引用冲突，现解析阶段失败且既有 Provider 文件不变；Linux 历史大小写敏感引用保留。
- F2：CLI 目录准备与凭据写入原先展开 `~` 的路径不一致，现共用 resolved_root，真实 CLI 检查 cwd 不产生额外 `~` 目录。
- 固定 owner 非 POSIX 写前拒绝及显式 os.chown 平台分支通过相邻复核。
- 一行 Browser fixture 修正经独立对照生产刷新、默认 fixture、严格小时断言及独立修订用例后通过；没有掩盖已确认的生产缺陷。

Reviewer 已直接读取后端、平台和原 Browser/单 worker 日志；最终 218 Browser 结果由 Parent 读回并核实退出 0。审查结论不冒充真实企业 OAuth、生产验收或远程 CI。

## Migration、回滚、资源与交付边界

本补充没有新增数据库 Migration；原权限交付的 0087 仍按 R19 证据和回滚规则保留。无依赖/Runtime 升级、无生产数据操作。回退本次自动落盘功能时保留 Secret，恢复匹配 Compose，并把 Connector 改为显式文件引用、移除 app_secret；回退旧认证缺陷版本仍须先访问隔离。具体操作由正式飞书运维手册维护。

本任务 Linux 镜像 `aima-feishu-validation:714` 已删除；所有 run --rm 容器均结束，无遗留容器。最终原始结果先归档，再核对绝对路径处于工作区、目标非链接，清理 `.runtime/dev/feishu-config`（含 wheel、probe 和临时测试输入）、`frontend/dist`、`frontend/test-results` 及空 `.task-tmp`。保留用户真实 env、Secret、数据库、依赖、共享 Docker 缓存和开发分支。

本次没有真实企业 OAuth/多企业外部授权、生产 HTTPS/Origin/Cookie、完整生产 Compose/Release/离线回放验收；本轮 classifier 的 PostgreSQL Integration/Real Full-stack 为 formal CI deferred，不冒充本次重新执行，旧角色任务本地真实 PG/Full-stack 证据见原验收记录。未 push、未建 PR、无远程 CI、未 merge、未发布或部署；本地可验收，人工验收仍 PENDING。
