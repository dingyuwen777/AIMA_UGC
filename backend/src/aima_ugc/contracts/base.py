"""AIMA 自有 HTTP Contract 的公共序列化基类。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from aima_ugc.platform.time import serialize_beijing_datetime


class AimaHttpModel(BaseModel):
    """统一 AIMA 自有 HTTP datetime 的北京时间 JSON 序列化。"""

    model_config = ConfigDict(
        json_encoders={datetime: serialize_beijing_datetime},
    )
