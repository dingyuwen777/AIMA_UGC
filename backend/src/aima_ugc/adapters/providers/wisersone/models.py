"""网站导出阶段的内部输入输出；不包含登录凭据。"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExportTask:
    task_id: str


@dataclass(frozen=True)
class ExportProgress:
    ready: bool
    percent: int
    file: Path | None = None


class ExportCancelled(RuntimeError):
    """调用者已取消本地等待；不宣称远端网站任务也已取消。"""


class SubmissionUnknown(RuntimeError):
    """网站提交结果无法确定；需核对网站下载记录，禁止盲目重发。"""
