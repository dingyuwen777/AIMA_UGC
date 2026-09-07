"""真实 Full-stack Fake LLM 与当前 Prompt 协议的一致性回归。"""

from __future__ import annotations

import json

from aima_ugc.modules.analysis.content_labeling import (
    ContentLabelingModelItem,
    PromptTaxonomyLoader,
    RuntimeTaxonomyValidator,
)

from tests.fullstack import fake_openai_llm


def test_fullstack_fake_llm_emits_valid_v4_label_item() -> None:
    """Full-stack Fake 必须生成能通过当前 V4 Validator 的确定性响应。"""

    payload = {
        "item_no": 1,
        "title": "爱玛 并发验收 1",
        "text": "骑行很舒服",
        "author": {
            "display_name": "测试用户",
            "bio": "",
            "verification_label": "",
        },
    }
    raw_item = fake_openai_llm._build_v4_label_item(payload, sentiment="正面")
    model_item = ContentLabelingModelItem(
        item_no=1,
        title=payload["title"],
        text=payload["text"],
        author_display_name=payload["author"]["display_name"],
        author_bio="",
        author_verification_label="",
    )

    result = RuntimeTaxonomyValidator(PromptTaxonomyLoader().load()).validate_response(
        json.dumps({"items": [raw_item]}, ensure_ascii=False),
        expected_item_nos=(1,),
        expected_items=(model_item,),
    )

    assert result.error_codes == ()
    assert tuple(result.valid_items) == (1,)
