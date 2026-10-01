"""物理 HTTP 反馈乱序与内存上限不应丢失成功后的首错。"""

from dataclasses import replace
from datetime import timedelta

from aima_ugc.adapters.llm.request_audit import LLMHTTPRequestAudit
from aima_ugc.bootstrap.analysis_recovery import AnalysisRecoveryFeedback
from aima_ugc.platform.time import beijing_now


def _audit(at, status):
    """只创建物理时间/状态事实，不包含模型正文或真实凭据。"""

    return LLMHTTPRequestAudit(
        http_request_id="test",
        logical_request_id="test",
        provider="fake",
        model="fake",
        started_at=at,
        completed_at=at,
        status="completed" if status == 200 else "http_error",
        status_code=status,
    )


def test_late_success_preserves_newer_failure():
    """t1/t3 失败先到，t2 的成功迟到，t3 仍是下一窗口首错。"""

    start = beijing_now()
    feedback = AnalysisRecoveryFeedback()
    feedback.audit(_audit(start, 503))
    feedback.audit(_audit(start + timedelta(seconds=2), 503))
    feedback.audit(_audit(start + timedelta(seconds=1), 200))
    value = feedback.take()
    assert value.success_at == start + timedelta(seconds=1)
    assert value.failure_spans == ((start + timedelta(seconds=2), start + timedelta(seconds=2)),)


def test_feedback_overflow_is_bounded_and_conservative():
    """极快故障压缩为有限区间，成功切分不能把未知首错推迟到区间末尾。"""

    start = beijing_now()
    feedback = AnalysisRecoveryFeedback()
    for index in range(5000):
        feedback.audit(_audit(start + timedelta(microseconds=index), 503))
    success = start + timedelta(microseconds=1000)
    feedback.audit(_audit(success, 200))
    value = feedback.take()
    assert len(value.failure_spans) <= 4096
    assert value.failure_spans[0][0] == success
    assert max(last for _, last in value.failure_spans) == start + timedelta(microseconds=4999)


def test_v2_http_responses_and_local_wait_do_not_mean_network_outage():
    """429/503 是网络可达的响应，连接池等待不是网络故障。"""
    start = beijing_now()
    feedback = AnalysisRecoveryFeedback(mode="recovery.v2")
    for index, status in enumerate((429, 503, 200)):
        feedback.audit(_audit(start + timedelta(seconds=index), status))
    feedback.audit(
        replace(
            _audit(start + timedelta(seconds=3), None), error_code="timeout", timeout_phase="pool"
        )
    )
    value = feedback.take()
    assert value.success_at == start + timedelta(seconds=2)
    assert value.failure_spans == ()


def test_v2_response_resets_real_network_errors_without_hiding_later_failure():
    """服务端恢复响应切断连续不可达；响应后的新网络错误仍保留。"""
    start = beijing_now()
    feedback = AnalysisRecoveryFeedback(mode="recovery.v2")
    error = replace(_audit(start, None), error_code="network_error", status="network_error")
    feedback.audit(error)
    feedback.audit(_audit(start + timedelta(seconds=301), 429))
    feedback.audit(replace(error, completed_at=start + timedelta(seconds=302)))
    value = feedback.take()
    assert value.success_at == start + timedelta(seconds=301)
    assert value.failure_spans == (
        (start + timedelta(seconds=302), start + timedelta(seconds=302)),
    )
