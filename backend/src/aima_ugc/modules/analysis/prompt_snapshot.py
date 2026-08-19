"""一次 Analysis run 内复用不可变 Prompt/Taxonomy 快照。"""

from __future__ import annotations

from .prompt_taxonomy import PromptTaxonomy, PromptTaxonomyLoader


class FrozenPromptTaxonomyLoader(PromptTaxonomyLoader):
    """兼容 ContentLabelingService Loader 接口，但不重复读取/解析 Prompt 文件。"""

    def __init__(self, taxonomy: PromptTaxonomy) -> None:
        super().__init__()
        self._taxonomy = taxonomy

    def load(self) -> PromptTaxonomy:
        return self._taxonomy


__all__ = ["FrozenPromptTaxonomyLoader"]
