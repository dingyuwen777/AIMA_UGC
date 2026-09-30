"""本地校验打标 Markdown，按需导出与生产入口相同的编译快照。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aima_ugc.contracts.administration import AnalysisSchemeDefinitionRequest
from aima_ugc.modules.analysis.prompt_taxonomy import CONTENT_LABELING_PROMPT_PATH
from aima_ugc.modules.analysis.schemes import compile_analysis_scheme


def main() -> int:
    """只编译文件，不连接数据库、发布 Scheme 或发送模型请求。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=CONTENT_LABELING_PROMPT_PATH)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        compiled = compile_analysis_scheme(
            AnalysisSchemeDefinitionRequest(
                prompt_template=args.input.read_text(encoding="utf-8-sig")
            )
        )
    except (ValueError, OSError) as exc:
        parser.exit(1, f"编译失败：{exc}\n")
    taxonomy = compiled.to_prompt_taxonomy()
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            compiled.definition.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            {
                "prompt_version": taxonomy.prompt_version,
                "output_protocol": taxonomy.output_protocol_version,
                "voice_types": len(taxonomy.voice_types),
                "sentiments": len(taxonomy.sentiments),
                "primary_labels": len(taxonomy.primary_labels),
                "secondary_labels": len(taxonomy.all_secondary_labels),
                "prompt_sha256": taxonomy.prompt_sha256,
                "taxonomy_sha256": taxonomy.taxonomy_sha256,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
