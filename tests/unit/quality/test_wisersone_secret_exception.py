"""初始会话例外不得扩散到刷新文件、临时文件、其它凭据或私钥。"""

import runpy
from pathlib import Path


def test_approved_session_exception_is_exact_and_never_allows_private_keys() -> None:
    scope = runpy.run_path(
        str(Path(__file__).resolve().parents[3] / "scripts/quality/scan_secrets.py")
    )
    approved = scope["approved_initial_auth"]
    paths = scope["WISERSONE_INITIAL_AUTH"]
    assert len(paths) == 2
    for path in paths:
        assert approved(path, "SEC002")
        assert approved(path, "SEC003")
        assert not approved(path, "SEC001")
        assert not approved(path + ".tmp", "SEC003")
        assert not approved(path.replace("wisersone-auth/", "runtime/"), "SEC003")
    assert not approved("backend/other.json", "SEC003")
