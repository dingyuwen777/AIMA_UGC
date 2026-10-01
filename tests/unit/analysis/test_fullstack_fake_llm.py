"""真实 Full-stack Fake LLM 与当前 Prompt 协议的一致性回归。"""

from __future__ import annotations

import json
from io import BytesIO

import pytest
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
        "platform": "xiaohongshu",
        "title": "爱玛 并发验收 1",
        "text": "骑行很舒服",
        "author": {
            "display_name": "测试用户",
            "bio": "",
            "verification_label": "",
        },
    }
    raw_item = fake_openai_llm._build_v4_label_item(
        payload, sentiment="正面", taxonomy=PromptTaxonomyLoader().load()
    )
    model_item = ContentLabelingModelItem(
        item_no=1,
        platform=payload["platform"],
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


@pytest.mark.parametrize("renamed", [False, True])
def test_fullstack_fake_llm_alternates_frozen_prompt_sentiments(
    monkeypatch: pytest.MonkeyPatch, renamed: bool
) -> None:
    """重复分析必须产生不同的合法情感，且改名后仍只使用冻结 Prompt 的实际值。"""

    taxonomy = PromptTaxonomyLoader().load()
    prompt = taxonomy.prompt_text
    if renamed:
        prompt = prompt.replace("正面", "积极").replace("负面", "消极")
    frozen_taxonomy = PromptTaxonomyLoader.load_text(prompt)
    item = {"item_no": 1, "platform": "xiaohongshu", "title": "爱玛 Stage12 当前标题"}
    body = json.dumps(
        {"messages": [{"content": prompt}, {"content": json.dumps({"items": [item]})}]}
    ).encode("utf-8")
    responses: list[dict[str, object]] = []
    monkeypatch.setattr(fake_openai_llm._Handler, "request_no", 0)
    monkeypatch.setattr(
        fake_openai_llm._Handler, "_send_json", lambda _self, response: responses.append(response)
    )

    for _ in range(2):
        handler = object.__new__(fake_openai_llm._Handler)
        handler.path = "/v1/chat/completions"
        handler.headers = {"content-length": str(len(body))}
        handler.rfile = BytesIO(body)
        handler.do_POST()

    actual = [json.loads(response["choices"][0]["message"]["content"]) for response in responses]
    expected = ["积极", "消极"] if renamed else ["正面", "负面"]
    assert [payload["items"][0]["sentiment"] for payload in actual] == expected
    model_item = ContentLabelingModelItem(
        item_no=1,
        platform="xiaohongshu",
        title=item["title"],
        text="",
        author_display_name="",
        author_bio="",
        author_verification_label="",
    )
    for payload in actual:
        validated = RuntimeTaxonomyValidator(frozen_taxonomy).validate_response(
            json.dumps(payload, ensure_ascii=False),
            expected_item_nos=(1,),
            expected_items=(model_item,),
        )
        assert validated.error_codes == ()
        assert tuple(validated.valid_items) == (1,)
