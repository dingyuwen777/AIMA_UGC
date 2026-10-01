"""正式进程关闭边界，确认虚拟环境启动器退出时不会遗留实际解释器。"""

import ctypes
import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from threading import Event
from time import monotonic

import pytest


def _stop_owned_test_process(process, *, owned_group, grace_seconds=8):
    """只回收本用例创建的进程树，Linux 要求调用方建立并记录独占 session。"""
    if os.name == "nt":
        if process.poll() is None:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=True,
                capture_output=True,
            )
        process.wait(timeout=grace_seconds)
        return
    assert owned_group == process.pid
    assert owned_group != os.getpgrp(), "禁止回收测试运行器的共享进程组"
    if process.poll() is None:
        assert os.getpgid(process.pid) == owned_group
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            os.killpg(owned_group, signal.SIGKILL)
            process.wait(timeout=5)
    # 父进程也可能已退出而后代仍在；组身份来自创建时的独占 session。
    try:
        os.killpg(owned_group, signal.SIGKILL)
    except ProcessLookupError:
        pass


@pytest.mark.skipif(os.name == "nt", reason="Linux 独占 session 强制回收回归")
def test_linux_stalled_owned_process_group_is_reclaimed_without_hiding_failure(tmp_path):
    """实际父子进程忽略协作信号；超时后仅杀本组，原始行为错误仍可识别。"""
    ready = tmp_path / "owned-child.json"
    script = tmp_path / "stalled_owned.py"
    script.write_text(
        "import json, os, signal, subprocess, sys, time\n"
        "from pathlib import Path\n"
        "signal.signal(signal.SIGINT, signal.SIG_IGN)\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "child = subprocess.Popen([sys.executable, '-B', '-c', 'import time; time.sleep(60)'])\n"
        "Path(sys.argv[1]).write_text(json.dumps({'child':child.pid,'group':os.getpgrp()}))\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )
    process = subprocess.Popen(
        [sys.executable, "-B", str(script), str(ready)], start_new_session=True
    )
    owned_group = os.getpgid(process.pid)
    try:
        deadline = monotonic() + 5
        while not ready.exists() and monotonic() < deadline:
            Event().wait(0.01)
        assert ready.exists()
        child = json.loads(ready.read_text())
        assert child["group"] == owned_group == process.pid
        started = monotonic()
        with pytest.raises(AssertionError, match="原始行为失败"):
            try:
                raise AssertionError("原始行为失败")
            finally:
                _stop_owned_test_process(process, owned_group=owned_group, grace_seconds=0.1)
        assert monotonic() - started < 5
        assert process.returncode == -signal.SIGKILL
        state = Path(f"/proc/{child['child']}/stat")
        deadline = monotonic() + 5
        while state.exists() and state.read_text().split(")", 1)[1].split()[0] != "Z":
            assert monotonic() < deadline
            Event().wait(0.01)
        # Zombie 已退出且不持有连接；容器 PID1 是 pytest 时顺便回收其退出身份。
        try:
            os.waitpid(child["child"], os.WNOHANG)
        except ChildProcessError:
            pass
    finally:
        _stop_owned_test_process(process, owned_group=owned_group, grace_seconds=0.1)


@pytest.mark.skipif(os.name != "nt", reason="Windows 虚拟环境启动器专属回归")
def test_stopping_venv_launcher_also_stops_its_real_interpreter(tmp_path):
    """只启动本用例的等待进程；持有原生进程句柄验证后代确实退出。"""
    ready = tmp_path / "ready.json"
    script = tmp_path / "wait_owned.py"
    script.write_text(
        "import json, os, sys, time\n"
        "from pathlib import Path\n"
        "Path(sys.argv[1]).write_text(json.dumps({'pid': os.getpid()}))\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )
    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    handle = None
    original_error = None
    process = subprocess.Popen([sys.executable, "-B", str(script), str(ready)])
    try:
        deadline = monotonic() + 5
        while not ready.exists() and monotonic() < deadline:
            Event().wait(0.01)
        assert ready.exists(), "本次虚拟环境进程未产生 ready 文件"
        actual_pid = json.loads(ready.read_text())["pid"]
        assert actual_pid != process.pid, "此环境未复现虚拟环境 PID 包装层"
        handle = kernel.OpenProcess(0x00100001, False, actual_pid)
        assert handle
        process.terminate()
        assert process.wait(timeout=5) is not None
        assert kernel.WaitForSingleObject(handle, 5000) == 0
    except BaseException as error:
        original_error = error
        raise
    finally:
        # 从 Popen 创建起回收，句柄取得之前的断言失败也不能遗留本次进程。
        try:
            _stop_owned_test_process(process, owned_group=None, grace_seconds=5)
            if handle is not None and kernel.WaitForSingleObject(handle, 0) != 0:
                kernel.TerminateProcess(handle, 1)
                assert kernel.WaitForSingleObject(handle, 5000) == 0
        except Exception as cleanup_error:
            if original_error is None:
                raise
            original_error.add_note(f"本次 venv 测试进程回收失败：{cleanup_error!r}")
        finally:
            if handle is not None:
                kernel.CloseHandle(handle)


@pytest.mark.skipif(os.name != "nt", reason="Windows 句柄建立前失败回收回归")
def test_failed_ready_observation_stops_owned_venv_tree_and_preserves_assertion(
    tmp_path, monkeypatch
):
    """真实启动 venv 父子进程，仅隐藏 ready 观测，验证早期失败也回收实际解释器。"""
    ready = tmp_path / "ready.json"
    real_exists = Path.exists
    real_popen = subprocess.Popen
    processes = []
    handles = []
    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]

    def observe_hidden(path):
        """保留实际进程句柄用于退出证明，同时使原测试走 ready 超时失败分支。"""
        if path == ready:
            if real_exists(path) and not handles:
                actual_pid = json.loads(path.read_text())["pid"]
                handle = kernel.OpenProcess(0x00100000, False, actual_pid)
                assert handle
                handles.append(handle)
            return False
        return real_exists(path)

    def track_process(*args, **kwargs):
        """记录本测试创建的 Popen，绝不从名称寻找用户进程。"""
        process = real_popen(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(Path, "exists", observe_hidden)
    monkeypatch.setattr(subprocess, "Popen", track_process)
    try:
        with pytest.raises(AssertionError, match="未产生 ready 文件"):
            test_stopping_venv_launcher_also_stops_its_real_interpreter(tmp_path)
        assert processes[0].poll() is not None
        assert handles
        assert kernel.WaitForSingleObject(handles[0], 5000) == 0
    finally:
        if processes:
            _stop_owned_test_process(processes[0], owned_group=None, grace_seconds=5)
        for handle in handles:
            kernel.CloseHandle(handle)
