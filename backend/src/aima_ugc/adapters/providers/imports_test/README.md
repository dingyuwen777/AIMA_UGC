# Excel 离线导入测试 / 调试

本目录是临时 P1 的**人工入口**，用于在不接数据库、不接 Scheduler 的情况下验证本地 XLSX 导入。它不是第二套实现：实际 Reader、Profile、Identity、Mapper 和 JSONL 转换都来自 `aima_ugc.adapters.providers.imports`。

当前 P1B 只实现：

```text
source.xlsx
→ imports Reader/Profile/Identity/Mapper
→ CanonicalContentV1
→ output/canonical/contents.jsonl
```

关键词过滤、去重、共享 Excel Exporter、AI 打标和 `run_all()` 属于后续 P1C—P1G，本阶段不提前实现。

## 1. 配置本地文件

编辑 `test.py` 顶部：

```python
INPUT_XLSX = Path(r"E:\path\to\source.xlsx")
OUTPUT_ROOT = Path(__file__).with_name("output")
SHEET_NAME = "文章"
PROFILE = "aima-monitoring-excel.v1"
```

`KEYWORDS`、`ENABLE_REAL_LLM`、`MAX_VALIDATION_RETRIES`、`ENV_FILE` 已按完整 P1 人工入口保留为顶层配置，但 **P1B 的 `convert()` 不读取或使用它们**。不要因此认为过滤或 LLM 已实现。

本工具不增加 CLI 参数。可以直接运行 `test.py`，也可以在 IDE/调试器中单独调用：

```python
from aima_ugc.adapters.providers.imports_test.test import convert

result = convert()
```

## 2. 当前 Excel Profile

首版 Profile：

```text
aima-monitoring-excel.v1
```

默认 Sheet：

```text
文章
```

要求存在以下 13 列，允许额外列：

```text
序号
监测项名称
文章编号
标题
内文
媒体名称（中文）
版面
出版日期
媒体类型
作者
全文情感
原文链接
粉丝数
```

Reader 使用：

```python
load_workbook(path, read_only=True, data_only=True)
iter_rows(values_only=True)
```

因此不会为了约 9 万行数据构造普通可写 Workbook，也没有引入 pandas。

## 3. Canonical 映射

P1B 保持 `CanonicalContentV1` 不变，不向 Canonical 加 AI 标签。

主要映射：

- `标题` → `title`；
- `内文` → `text`；
- `媒体名称（中文）` → `platform`；
- `出版日期` 按 `Asia/Shanghai` 解释后转 UTC；
- `作者` → `author.display_name`；
- `粉丝数` → `author.follower_count`；
- `原文链接` → 经校验和规范化的 `canonical_url`；
- `文章编号` → 来源备用 ID，必要时作为主身份 fallback；
- `版面` 不进入 Canonical；
- `媒体类型` 不直接冒充 `content_type`，首版使用 `content_type="unknown"` 且不把它声明为 observed field；
- `全文情感` 仍是源 XLSX 的来源事实，不写成系统 AI Analysis，也不进入 Canonical 标签字段。

平台名称不会做模糊猜测。当前 Profile 显式识别小红书、抖音、微博、B站、快手的常见名称，也接受已经符合 Canonical `platform` 规则的英文/数字 slug；其他中文媒体名会逐行失败，需后续通过 Profile 明确增加映射，而不是静默散列或误分类。

## 4. 稳定内容身份

严格按以下顺序：

```text
平台 URL 中可验证的原生内容 ID
→ 文章编号
→ 规范化 URL 的 SHA-256
→ 无法构造则拒绝该行
```

URL fallback 的主 ID 使用：

```text
url_sha256:<64位十六进制摘要>
```

如果平台原生 ID 已作为主 ID，存在的 `文章编号` 会保存在：

```json
{"source_article_id": "..."}
```

不会用标题、作者或正文生成身份。

## 5. 输出与错误

成功输出：

```text
output/
└─ canonical/
   ├─ contents.jsonl
   └─ conversion_errors.jsonl
```

`contents.jsonl` 每行都是一个可由 `CanonicalContentV1` 重新校验的 JSON 对象。

`conversion_errors.jsonl` 只记录：

```json
{"row_number": 3, "code": "...", "message": "..."}
```

它不复制源行正文或其他单元格值。任何一行不合法时，转换会继续扫描以收集全部行号错误，但**不会发布部分 `contents.jsonl`**，最后抛出 `ExcelImportRejectedRowsError`。这样后续阶段不能误把部分成功数据当作完整批次。

## 6. `.env`

P1B 不需要 Secret，也不会读取 `.env`。`.env.example` 当前只说明这一事实；真实 OpenAI-compatible LLM 配置在 P1F 落地时再按实际 Adapter 接口定义，避免现在提前制造一套不存在的配置约定。

真实 `.env` 已由仓库根 `.gitignore` 忽略，不要提交密钥。
