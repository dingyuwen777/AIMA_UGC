from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_canonical_compose_network_has_configurable_ipam() -> None:
    """固定 canonical app bridge 的默认 IPAM，并保留环境覆盖入口。"""
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    env_example = (ROOT / "env.production.example").read_text(encoding="utf-8")

    assert "ipam:" in compose
    assert "subnet: ${AIMA_DOCKER_SUBNET:-10.1.1.0/24}" in compose
    assert "gateway: ${AIMA_DOCKER_GATEWAY:-10.1.1.1}" in compose
    assert "AIMA_DOCKER_SUBNET=10.1.1.0/24" in env_example
    assert "AIMA_DOCKER_GATEWAY=10.1.1.1" in env_example


def test_compose_network_keeps_service_dns_and_windows_single_source() -> None:
    """保持 service DNS 与 Windows storage-only override 的单一网络事实源。"""
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    windows_compose = (ROOT / "compose.windows.yaml").read_text(encoding="utf-8")

    assert "AIMA_DB_HOST=postgres" in compose
    assert "network_mode: none" in compose
    assert "ipv4_address:" not in compose
    assert "internal: true" not in compose
    assert "\nnetworks:" not in windows_compose
