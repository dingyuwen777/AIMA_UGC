"""一次性应用发声类型中文值、Prompt 表格与 Excel 清理；成功后由 Workflow 删除。"""

from __future__ import annotations

import json
import re
from pathlib import Path

PROMPT = Path("backend/src/aima_ugc/modules/analysis/prompts/content_labeling_v3.md")
EXCEL = Path("backend/src/aima_ugc/platform/export/excel.py")
PROMPT_TEST = Path("tests/unit/analysis/test_prompt_judgment_tables.py")
EXISTING_VOICE_TEST = Path("tests/unit/analysis/test_voice_type_taxonomy.py")
OLD_EXCEL_TEST = Path("tests/unit/platform/test_excel_voice_type_taxonomy.py")
ANALYSIS_README = Path("backend/src/aima_ugc/modules/analysis/README.md")
AI_APPENDIX = Path("docs/appendix/07_AI舆情打标与分析实现.md")
EXCEL_APPENDIX = Path("docs/appendix/06_Excel统一数据导出与离线调试.md")

VOICE_TYPES = [
    "真实用户发声",
    "品牌官方发声",
    "门店经销商发声",
    "营销推广发声",
    "行业从业发声",
    "媒体机构发声",
    "无法判断",
]
LEGACY_VOICE_TYPES = (
    "user_voice",
    "creator_marketing",
    "brand_official",
    "dealer_promotion",
    "media_information",
    "other_organization",
    "unknown",
)


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    """要求旧文本恰好出现一次后替换，避免误改仓库新状态。"""

    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: 预期唯一命中，实际 {count}")
    return text.replace(old, new, 1)


def update_prompt() -> None:
    """更新机器 Taxonomy，并把主要判断标准整理成表格和边界示例。"""

    prompt = PROMPT.read_text(encoding="utf-8")
    pattern = re.compile(
        r"(<!-- AIMA_TAXONOMY_START -->\s*```json\s*)(.*?)(\s*```\s*<!-- AIMA_TAXONOMY_END -->)",
        flags=re.DOTALL,
    )
    match = pattern.search(prompt)
    if match is None:
        raise RuntimeError("未找到机器 Taxonomy")
    payload = json.loads(match.group(2))
    payload["voice_types"] = VOICE_TYPES
    taxonomy_json = json.dumps(payload, ensure_ascii=False, indent=2)
    prompt = prompt[: match.start(2)] + taxonomy_json + prompt[match.end(2) :]

    start = prompt.index("## 语义相关性判断标准")
    end = prompt.index("## 一级/二级标签判断标准")
    middle = '''## 语义相关性判断标准

先判断 `relevance`，这是关键词粗筛之后的第二层语义复核。

| 判定结果 | 核心定义 | 说明 |
| --- | --- | --- |
| `relevant` | 内容与爱玛品牌、产品、购买、使用、服务、渠道、营销、事件或对比存在可用于舆情分析的实质语义关联 | 包括爱玛产品/车型、购买与价格、使用体验、质量故障、电池续航、智能功能、销售售后、渠道门店、营销传播/代言/活动，以及与爱玛有明确比较、评价、争议或事件关系的内容 |
| `irrelevant` | 可见内容无法形成任何有效的爱玛舆情含义 | 仅关键词碰撞、同名实体、标签/热词堆砌、正文主体完全是其他品牌/话题且爱玛只是无实质信息带过、模板尾巴等情况均判无关 |

### 相关性高混淆场景与示例

1. 竞品内容只有在明确比较或提及爱玛，并形成对爱玛的判断时才是 `relevant`；只讨论竞品本身是 `irrelevant`。
2. “信息少但确实在问/说爱玛”仍是 `relevant`，不能因为文本短就删除。
3. 转发、新闻、官方稿、营销稿只要主体确实与爱玛相关，仍是 `relevant`；相关性与发声类型是两个独立判断。
4. 作者名含“爱玛”不能替代正文语义判断；反过来，标题已经建立明确爱玛语境时，正文不重复品牌名也不能机械判无关。
5. 示例：正文讨论一个名叫“爱玛”的人物，与爱玛电动车品牌、产品、服务、渠道、营销和相关事件均无实质关系 → `irrelevant`。
6. 示例：用户只问“爱玛 Q7 冬天能跑多少公里？”虽然很短，但明确询问爱玛车型续航 → `relevant`。

## 发声类型判断标准

`voice_type` 是**当前内容的发声属性**，不是对账号真实身份、职业或商业合作关系作法律或事实认定。合法值以机器 Taxonomy `voice_types` 为准；当前值本身就是最终业务值和展示值，不存在英文机器名与中文展示名两套命名。

| 推荐名称 | 核心定义 | 说明 |
| --- | --- | --- |
| **真实用户发声** | 普通消费者基于真实购买、使用、咨询、投诉、推荐、提车等自然表达；没有明显品牌、行业、营销或组织化传播特征 | 作者名称不包含明显品牌/电动车行业经营相关词；标题、正文不存在明显营销推广、活动任务、二手交易等内容。出现“爱玛骑遇团”“出二手车/转让车辆/收车”等组织化或交易性内容时，不判为真实用户 |
| **品牌官方发声** | 爱玛品牌、子品牌、官方认证账号或明确以品牌第一方身份发布的产品、活动、声明等 | 作者名称为爱玛电动车、爱玛三轮电动车、爱玛精品周边、爱玛东二楼、我是玛小爱、元宇宙女孩的实验室、爱玛官方旗舰店、爱玛电动车生活服务旗舰店、爱玛本地直播间、爱玛马赫、爱玛电动三轮车、爱玛科学实验室、爱玛官方骑行装备、爱玛三轮官方团购直播间、爱玛服务、爱玛金标电池、AAA电动车批发王总、B爱玛马赫等时，可作为品牌第一方主体的强证据；仍需结合正文判断当前内容是否确为品牌第一方发声 |
| **门店经销商发声** | 爱玛门店、经销商、销售、加盟商等渠道主体发布的车型展示、报价、优惠、到店、成交、上牌等内容 | 作者名称出现“爱玛+车行/门店/专卖店/销售/经销/当地地名”等渠道特征，或正文具有明显卖车、报价、优惠、现车、到店等获客目的 |
| **营销推广发声** | 非官方、非门店主体发布的品牌活动、达人/KOC种草、合作推广、任务打卡、爱玛骑遇团等组织化营销内容 | 作者名称看起来不是爱玛官方或门店，但标题/正文出现“爱玛骑遇团”、品牌活动、合作体验、统一种草、导购、活动打卡等明显营销传播特征 |
| **行业从业发声** | 修车、电动车行业、二手车、车行、竞品从业者等行业相关主体，以维修、行业讨论、交易或专业视角发声 | 作者名称出现“修车、维修、二手车、车业、车行、电动车、三轮车、雅迪”等行业属性，但不能确认属于爱玛官方或爱玛经销体系 |
| **媒体机构发声** | 新闻媒体、资讯号、政府、协会、学校、企业机构等以报道、资讯、公告、公共事务等形式发布 | 内容主体主要是新闻报道、行业资讯、政策公告、合作通知等，而非个人体验、卖车或营销种草 |
| **无法判断** | 可见信息不足，无法可靠确定属于哪一类 | 综合以上信息仍无法进行可靠分类时使用，不要为了提高覆盖率硬猜 |

### 先组合两层证据，再分类

**主体证据**回答“谁在说”：综合作者展示名、公开简介、认证文案判断账号呈现出的主体属性。昵称、简介或认证中的任意一个单独信号都不能自动决定类型，更不能据此断言账号真实法律身份或存在商业合作。

**表达目的证据**回答“这条内容为什么这样说”：综合标题和正文判断当前内容主要是在表达个人体验/观点/求助，品牌第一方传播，门店获客，组织化营销，行业专业/交易信息，还是媒体机构资讯/公告。

必须同时阅读 `title`、`text`、`author.display_name`、`author.bio`、`author.verification_label` 中实际提供的内容。作者信息和标题/正文相互印证时可以加强判断；两者冲突时，以**当前内容的主要表达目的**为主，作者信息只作为辅助。不得因为某一个词、某一种口吻或某一个昵称机械分类。

### 七类边界与高混淆场景

1. **真实用户发声 vs 营销推广发声**
   - 第一人称使用经历、长期体验、故障投诉、个人比较、咨询求助、真实购买意愿等，是“真实用户发声”的强证据。
   - “博主、达人、KOC、测评”等作者标签本身不是营销证据；创作者没有可见合作、带货、导购、任务或组织化传播目的时，真实个人体验仍可判“真实用户发声”。
   - 明确品牌合作/赞助、直播间/购物入口、领券、统一卖点式种草、活动打卡、“爱玛骑遇团”等组织化营销证据出现时，优先判“营销推广发声”。
   - 仅出现“推荐、好用、值得买”等普通个人评价，不能单独判营销。

2. **真实用户发声 vs 门店经销商发声**
   - 普通用户讨论门店价格、销售态度、优惠是否划算、到店体验，仍是“真实用户发声”。
   - 作者呈现为爱玛门店/经销商/销售，且正文包含报价、现车、限时优惠、到店、私信留资、联系方式、成交引导等获客目的时，判“门店经销商发声”。
   - 即使销售人员使用第一人称，只要主要目的是获客成交，也不是“真实用户发声”。

3. **真实用户发声 vs 行业从业发声**
   - 普通车主描述自己的维修经历、故障体验仍可判“真实用户发声”。
   - 作者呈现为修车、维修、电动车/三轮车行业、二手车、车行、竞品从业者，并以专业维修、行业分析、车辆交易等视角发声时，判“行业从业发声”。
   - “出二手车/转让车辆/收车”等交易性表达原则上不判真实用户；结合作者和正文判断为行业/交易主体时判“行业从业发声”。

4. **品牌官方发声 vs 门店经销商发声**
   - 品牌第一方产品发布、品牌活动、代言官宣、公司声明、统一品牌传播判“品牌官方发声”。
   - 地方门店、经销商、销售围绕价格、库存、到店和成交发布内容判“门店经销商发声”，不能因为同时使用品牌 Logo 或品牌名称就判官方。
   - 作者昵称含“爱玛”但缺乏其他官方或门店证据时，不得只凭昵称定类。

5. **品牌官方发声 vs 营销推广发声**
   - 爱玛第一方主体发布自己的活动、产品、声明，判“品牌官方发声”。
   - 非官方、非门店主体参与品牌活动、合作体验、达人/KOC种草、任务打卡或“爱玛骑遇团”等组织化传播，判“营销推广发声”。
   - 被品牌邀请或参与活动不等于发布者本身是品牌官方。

6. **媒体机构发声 vs 其他类型**
   - 新闻媒体、资讯号以第三方报道/编辑方式传播爱玛新闻，判“媒体机构发声”；被报道对象是爱玛，不等于发声主体是品牌官方。
   - 政府、协会、学校、企业机构发布合作通知、政策公告、公共事务，也判“媒体机构发声”。
   - 个人转发资讯后加入大量自己的使用体验、评价、投诉或购买判断，且个人表达成为主体时，可判“真实用户发声”。
   - 行业从业者以自己的专业分析、维修或交易视角发声时，优先判“行业从业发声”，不因内容具有资讯性就自动判媒体机构。

7. **无法判断的使用**
   - 证据不足时使用“无法判断”，不要为了提高分类覆盖率硬猜。
   - 作者资料缺失不等于必须“无法判断”：如果标题/正文已经清楚显示个人体验、门店获客、营销活动、行业交易或媒体公告等目的，应正常分类。
   - 极短、模板化或主体/目的均含混的内容，才优先“无法判断”。

### 判断顺序

1. 先独立完成 `relevance` 判断；相关性与发声类型不能互相替代。
2. 阅读标题和正文，识别当前内容的主要表达目的和信息量分布。
3. 再结合作者展示名、公开简介和认证文案识别主体证据，并检查是否与内容目的相互支持。
4. 对上述高混淆类型逐对排除，选择证据最充分、最符合当前内容主要目的的一类。
5. 如果两个或多个类型仍没有足够证据区分，返回“无法判断”，不要臆测。

### 发声类型示例

- 作者“通勤小林”，简介“分享日常通勤和骑行体验”，正文“爱玛 Q7 骑了一年，冬天续航短一些但通勤够用” → `真实用户发声`。
- 作者“骑行阿Ken”，简介显示出行博主，但正文只是自费使用后的个人优缺点体验，没有合作、导购、任务或转化信息 → `真实用户发声`，不能因创作者身份自动判营销。
- 同一创作者正文明确写品牌合作、直播间下单、领券、活动打卡或“爱玛骑遇团” → `营销推广发声`。
- 作者“爱玛XX旗舰店/销售小王”，正文强调现车、到店优惠、报价、私信咨询 → `门店经销商发声`。
- 明确爱玛品牌第一方主体发布新品、活动或声明 → `品牌官方发声`。
- 作者“修车老张/XX二手电动车”，正文从维修专业视角分析爱玛故障，或发布收车/转让交易信息 → `行业从业发声`。
- 作者“XX财经/电动车观察”等媒体资讯主体报道爱玛事件，或政府/协会/学校发布与爱玛有关的合作/公共事务通知 → `媒体机构发声`。
- 作者和正文都极少，无法可靠判断属于哪一类 → `无法判断`。

## 情感判断标准

| 情感 | 核心定义 | 说明 |
| --- | --- | --- |
| **正面** | 对爱玛品牌、产品、服务、价格政策、渠道或使用体验有明确认可、满意、推荐、支持或表扬 | 必须是对爱玛本身的正向态度；只陈述事实不算正面 |
| **中性** | 主要是客观信息、事实、新闻、配置、价格或政策说明，没有明确正负态度 | 信息不足以形成明确态度时也使用中性，不因事件主题天然偏正/偏负就猜测作者态度 |
| **负面** | 对爱玛存在明确投诉、批评、质疑、不满、失望、风险指控或负面体验 | 负面对象必须实际指向爱玛品牌、产品、服务、渠道或相关行为 |
| **混合** | 对爱玛本身同时存在具有实质信息量的正面和负面评价，且任何一方都不能忽略 | 只有同一内容对爱玛同时存在实质正负评价才使用；对竞品负面、同时对爱玛正面，不等于对爱玛“混合” |

### 情感高混淆场景与示例

1. 新闻、配置、价格、政策、活动公告等纯事实陈述，没有明确评价时判“中性”。
2. “外观很好看，但骑了三个月反复坏”同时包含对爱玛的实质正面与负面评价，可判“混合”。
3. “雅迪太难骑，还是爱玛舒服”对竞品是负面、对爱玛是正面；爱玛情感应判“正面”，不是“混合”。
4. “爱玛这次召回了某批次车辆”如果只是客观报道召回事实、没有评价，仍按可见表达判“中性”；不能因为事件风险天然存在就自动判负面。
5. “售后拖了一个月没人处理，太失望了”明确批评爱玛售后体验，判“负面”。

'''
    prompt = prompt[:start] + middle + prompt[end:]

    for old, new in {
        "user_voice": "真实用户发声",
        "creator_marketing": "营销推广发声",
        "brand_official": "品牌官方发声",
        "dealer_promotion": "门店经销商发声",
        "media_information": "媒体机构发声",
        "other_organization": "媒体机构发声",
        "unknown": "无法判断",
    }.items():
        prompt = prompt.replace(old, new)

    PROMPT.write_text(prompt, encoding="utf-8")


def update_excel() -> None:
    """删除发声类型展示转换层，直接导出 Analysis Result 实际值。"""

    excel = EXCEL.read_text(encoding="utf-8")
    excel, count = re.subn(
        r"_VOICE_TYPE_DISPLAY_NAMES = \{\n.*?\n\}\n",
        "",
        excel,
        count=1,
        flags=re.DOTALL,
    )
    if count != 1:
        raise RuntimeError("未唯一删除 _VOICE_TYPE_DISPLAY_NAMES")
    excel, count = re.subn(
        r"\n\ndef _voice_type_display_name\(value: str \| None\) -> str \| None:\n.*?return _VOICE_TYPE_DISPLAY_NAMES\.get\(value, value\)\n",
        "",
        excel,
        count=1,
        flags=re.DOTALL,
    )
    if count != 1:
        raise RuntimeError("未唯一删除 _voice_type_display_name")
    excel = replace_once(
        excel,
        "_voice_type_display_name(analysis.voice_type) if analysis is not None else None",
        "analysis.voice_type if analysis is not None else None",
        label="Excel voice_type 展示调用",
    )
    excel = replace_once(
        excel,
        '''                voice_type = (\n                    record.analysis.voice_type\n                    if isinstance(record.analysis, ContentLabelAnalysisV3)\n                    else "unknown"\n                )''',
        '''                voice_type = (\n                    record.analysis.voice_type\n                    if isinstance(record.analysis, ContentLabelAnalysisV3)\n                    else None\n                )''',
        label="V1/V2 voice_type 默认值",
    )
    EXCEL.write_text(excel, encoding="utf-8")


def update_tests() -> None:
    """迁移已有断言并删除只验证旧翻译层的测试。"""

    text = EXISTING_VOICE_TEST.read_text(encoding="utf-8")
    text = replace_once(
        text,
        'assert "## 内容发声类型判断标准" in prompt',
        'assert "## 发声类型判断标准" in prompt',
        label="旧发声类型标题断言",
    )
    EXISTING_VOICE_TEST.write_text(text, encoding="utf-8")

    if not OLD_EXCEL_TEST.exists():
        raise RuntimeError("旧 Excel voice_type 映射测试不存在")
    OLD_EXCEL_TEST.unlink()

    text = PROMPT_TEST.read_text(encoding="utf-8")
    marker = "    assert taxonomy.voice_types == _EXPECTED_VOICE_TYPES\n"
    addition = '''    assert taxonomy.voice_types == _EXPECTED_VOICE_TYPES

    prompt = CONTENT_LABELING_PROMPT_PATH.read_text(encoding="utf-8")
    for legacy_value in (
        "user_voice",
        "creator_marketing",
        "brand_official",
        "dealer_promotion",
        "media_information",
        "other_organization",
        "unknown",
    ):
        assert legacy_value not in prompt
'''
    text = replace_once(text, marker, addition, label="Prompt 旧值检查插入点")
    PROMPT_TEST.write_text(text, encoding="utf-8")


def update_docs() -> None:
    """只同步因中文实际值和 Excel 直出而过期的实时文档。"""

    readme = ANALYSIS_README.read_text(encoding="utf-8")
    readme = replace_once(
        readme,
        '''真实用户发声唯一业务判断：

```text
voice_type == user_voice
```

不要再增加 `is_user_voice`/`is_real_user_voice` 平行字段。''',
        '''需要判断“真实用户发声”时，直接使用当前 Analysis Result 的 `voice_type` 实际值；当前合法值与业务定义以 Prompt Taxonomy 为准，不再维护英文机器名或平行展示名。

不要再增加 `is_user_voice`/`is_real_user_voice` 平行字段。''',
        label="Analysis README 旧 user_voice 示例",
    )
    ANALYSIS_README.write_text(readme, encoding="utf-8")

    appendix = AI_APPENDIX.read_text(encoding="utf-8")
    appendix = replace_once(
        appendix,
        '"voice_type": "user_voice"',
        '"voice_type": "真实用户发声"',
        label="AI Appendix V3 示例",
    )
    AI_APPENDIX.write_text(appendix, encoding="utf-8")

    excel_doc = EXCEL_APPENDIX.read_text(encoding="utf-8")
    excel_doc = replace_once(
        excel_doc,
        '`voice_type` Excel 中文投影可通过 `_VOICE_TYPE_DISPLAY_NAMES` 为既有机器值提供展示别名，但这张映射不是合法 Taxonomy 白名单。合法值只由当前 Prompt 的机器 Taxonomy 决定；已有值继续保持既有中文展示，Prompt 新增而尚未配置展示别名的机器值会在 Excel 中原样输出，不会因为导出层未认识该值而失败。数据库/Contract 继续保存稳定机器值。',
        '`voice_type` 不再经过 Excel 展示映射。当前 Prompt 的机器 Taxonomy 直接使用最终中文业务值，Analysis Result、数据库、API 与 Excel 使用同一个实际值；Exporter 只原样输出 `analysis.voice_type`。历史旧 Analysis Result 不迁移、不改写，因此历史英文值再次导出时也保持原值；V1/V2 历史结果本身没有 `voice_type` 时保持空值。',
        label="Excel Appendix voice_type 映射说明",
    )
    EXCEL_APPENDIX.write_text(excel_doc, encoding="utf-8")


def main() -> None:
    """顺序应用所有正式修改。"""

    update_prompt()
    update_excel()
    update_tests()
    update_docs()


if __name__ == "__main__":
    main()
