# 监测 Excel 目录增量过滤

本目录是 `imports_test` 的第一阶段离线工具。它继续复用正式 Excel Reader、Mapper、Canonical、关键词过滤与单 run 去重实现，但现在会自动接管**本机**已有 `output/runs/*`，以后只解析新增 Excel，并把跨历史真正新增的帖子交给第二阶段。

真实 `output/` 仍由本目录 `.gitignore` 排除：历史数据只存在你的电脑，不需要、也不应该上传 GitHub。

## 1. 当前链路

```text
INPUT_DIR
→ 发现全部 .xlsx
→ 自动读取 output/state + output/runs
→ 已处理且未变化 Excel：跳过
→ 新增 Excel：iter_excel_rows() → map_excel_row()
→ 五平台 Canonical
→ keyword_pack OR 过滤
→ 本 run 内 deduplicate_content_jsonl()
→ 与历史 content identity index 再去重
→ runs/<run_id>/deduplicated/contents.jsonl  # 仅本次全局新增 delta
```

稳定内容身份仍是：

```text
(platform, external_content_id)
```

## 2. 第一次升级：自动识别你本机已经跑过的数据

如果 `output/state/` 还没有增量状态，代码会自动扫描：

```text
output/runs/*/run_summary.json
output/runs/*/deduplicated/contents.jsonl
```

并在 `output/state/` 下建立文件 checkpoint 与 256 分片内容身份索引：

```text
output/state/
└── content_index/
    ├── 00.jsonl
    ├── 01.jsonl
    ├── ...
    └── ff.jsonl
```

旧 run 只读使用，不修改、不删除、不覆盖。

对旧 Excel，bootstrap 只补一次：

```text
relative source path
size
mtime_ns
SHA-256
```

不会重新进入 openpyxl/Reader/Mapper/关键词过滤。对历史最终 JSONL，只扫描稳定内容身份建立 256 分片索引，不重新处理 Excel。

## 3. 后续运行怎样判断文件

对于已经登记的同一路径文件：

```text
size + mtime_ns 相同
→ 直接 skipped_unchanged
→ 不读取 Excel 内容

size/mtime 变化但 SHA-256 相同
→ 仍视为 unchanged，并刷新文件元数据

SHA-256 不同
→ fail closed
→ 报“已处理 Excel 内容发生变化”
```

原因是历史文件原地修改可能包含删除/替换行，简单增量无法安全撤销旧贡献。

对于新路径文件：

```text
SHA-256 从未出现
→ 真正新增 → 处理

SHA-256 与历史文件完全相同
→ duplicate_binary → 跳过
```

建议处理完成的历史 Excel 保持不可变，后续数据用新 Excel 追加到目录。

## 4. Pipeline Signature

增量 state 绑定：

```text
processing semantics version
profile_name
sheet_name
keyword_pack.txt SHA-256
```

如果词包、Profile 或 Sheet 配置变化，程序会拒绝沿用旧 state，因为历史 Excel 可能需要重新筛选。此时应使用新的 `output_root` 或明确重建 Stage 1 state，不能静默继续。

## 5. 输出目录

```text
output/
├── state/
│   └── content_index/*.jsonl
├── current/
│   └── <累计索引>
└── runs/
    ├── <历史旧 run>/                # 原封不动
    └── <本次 run>/
        ├── canonical/contents.jsonl
        ├── filtered/contents.jsonl
        ├── deduplicated/
        │   ├── contents.jsonl
        │   └── deduplication_conflicts.jsonl
        ├── state_delta/content_index/*.jsonl
        └── run_summary.json
```

### run 是 delta

新的：

```text
runs/<run_id>/deduplicated/contents.jsonl
```

只包含：

> 本次新增 Excel 中，命中词包、run 内去重后，并且历史 content identity index 中从未出现的帖子。

因此第二阶段直接处理最新 run 的该文件即可，不必再次扫描历史全部数据。

### current 为什么只保存轻量累计索引

第一阶段可能达到数千万条帖子。每次运行都重新复制一份全量 JSONL 会产生巨大、无业务价值的 I/O 和磁盘重复。

所以 `output/current/` 只记录所有已提交 run delta 及累计行数；完整历史事实仍由不可变 `runs/*/deduplicated/contents.jsonl` + `state/content_index` 表达。

第二、三阶段的数据规模已经明显收敛，才维护可直接查看的累计 `current` JSONL/Excel。

## 6. no-op run

如果目录中所有 Excel 都已经处理且没有变化，本次运行仍然成功：

```text
files_processed = 0
rows_seen = 0
rows_after_deduplication = 0
```

并生成稳定的空 JSONL run，不把“没有新增数据”误报为错误。

## 7. run_summary.json 关键字段

除原有统计外，增量 run 新增：

```text
input_file_count                 # 目录发现总数
files_processed                  # 本次真正打开处理的 Excel
files_skipped_unchanged
files_skipped_duplicate_binary
historical_duplicates_removed    # 本次与历史 content identity 重复数
pipeline_signature
file_decisions
```

其中 `rows_seen` 只统计本次真正处理的新 Excel，不再重复计入历史文件。

## 8. 运行

配置：

```python
INPUT_DIR = Path(r"D:\慧科数据")
KEYWORD_PACK_FILE = Path(__file__).with_name("keyword_pack.txt")
```

仓库根目录运行：

```bash
uv run python -m aima_ugc.adapters.providers.imports_test.monitoring_excel_filter.process_directory
```

第一次升级如果已有本地旧 run，会自动 bootstrap；无需手工登记旧 run。

## 9. 安全与失败边界

- 输入 Excel 始终只读；
- 旧 `runs/*` 不修改；
- 同一个 output state 通过原子目录锁禁止两个进程同时推进；
- Canonical/过滤/去重继续使用已有临时文件与原子替换；
- identity index 使用 256 个 JSONL 分片，单次只加载一个历史分片，避免把几千万 content ID 全放内存；
- 只有存在 `run_summary.json` 的完成 run 才会在下次启动时被自动 reconcile 进 state；
- state 更新意外中断时，下次运行可从不可变历史 run 自动补索引，不需要重新解析 Excel。
