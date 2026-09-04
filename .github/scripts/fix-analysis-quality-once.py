from pathlib import Path


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"Unexpected source shape for {label}: count={text.count(old)}")
    return text.replace(old, new, 1)


concurrency_path = Path("backend/src/aima_ugc/modules/analysis/concurrent_labeling.py")
text = concurrency_path.read_text(encoding="utf-8")
text = replace_once(
    text,
    'from typing import Generic, TypeVar\n\n_ItemT = TypeVar("_ItemT")\n_ResultT = TypeVar("_ResultT")\n\n\n',
    "",
    label="legacy generic imports",
)
text = replace_once(
    text,
    "class ConcurrentTaskOutcome(Generic[_ItemT, _ResultT]):",
    "class ConcurrentTaskOutcome[_ItemT, _ResultT]:",
    label="ConcurrentTaskOutcome generic",
)
text = replace_once(
    text,
    "def run_bounded_concurrently(\n",
    "def run_bounded_concurrently[_ItemT, _ResultT](\n",
    label="run_bounded_concurrently generic",
)
text = replace_once(
    text,
    "def _collect_completed(\n",
    "def _collect_completed[_ItemT, _ResultT](\n",
    label="_collect_completed generic",
)
text = replace_once(
    text,
    "def _cancel_and_collect(\n",
    "def _cancel_and_collect[_ItemT, _ResultT](\n",
    label="_cancel_and_collect generic",
)
concurrency_path.write_text(text, encoding="utf-8")

worker_path = Path("backend/src/aima_ugc/bootstrap/analysis_concurrent_worker.py")
text = worker_path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "                cancel_seen = False\n",
    "                cancel_state = [False]\n",
    label="cancel state declaration",
)
old_signature = (
    "                def persist_completed(\n"
    "                    outcomes: Sequence[\n"
    "                        ConcurrentTaskOutcome[AnalysisWorkItem, ContentLabelingBatchResult]\n"
    "                    ],\n"
    "                ) -> None:\n"
    '                    """在调度线程累积完成结果，达到阈值后短事务落库并形成自然背压。"""\n'
    "\n"
    "                    nonlocal cancel_seen\n"
    "                    persistence_buffer.extend(outcomes)\n"
)
new_signature = (
    "                def persist_completed(\n"
    "                    outcomes: Sequence[\n"
    "                        ConcurrentTaskOutcome[AnalysisWorkItem, ContentLabelingBatchResult]\n"
    "                    ],\n"
    "                    persistence_buffer: list[\n"
    "                        ConcurrentTaskOutcome[AnalysisWorkItem, ContentLabelingBatchResult]\n"
    "                    ] = persistence_buffer,\n"
    "                    cancel_state: list[bool] = cancel_state,\n"
    "                ) -> None:\n"
    '                    """在调度线程累积完成结果，达到阈值后短事务落库并形成自然背压。"""\n'
    "\n"
    "                    persistence_buffer.extend(outcomes)\n"
)
text = replace_once(text, old_signature, new_signature, label="persist_completed binding")
text = replace_once(
    text,
    "                        cancel_seen = context.cancel_requested()\n",
    "                        cancel_state[0] = context.cancel_requested()\n",
    label="cancel state assignment",
)
text = replace_once(
    text,
    "                        stop_requested=lambda: cancel_seen,\n",
    "                        stop_requested=lambda cancel_state=cancel_state: cancel_state[0],\n",
    label="stop lambda binding",
)
worker_path.write_text(text, encoding="utf-8")
