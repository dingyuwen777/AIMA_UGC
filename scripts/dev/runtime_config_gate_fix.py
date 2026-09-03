#!/usr/bin/env python3
"""Temporary gate fixer for PR #318; removed by its one-shot workflow."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def patch_runtime_acceptance() -> None:
    path = ".github/workflows/runtime.yml"
    text = read(path)

    old = '''          sudo test ! -e "${AIMA_RUNTIME_ROOT}/shared/secrets/tikhub_api_key"
          sudo test ! -e "${AIMA_RUNTIME_ROOT}/shared/secrets/llm_api_key"
          compose exec -T worker sh -ec \\
            'test "$(cat /run/secrets/tikhub_api_key)" = "ci-placeholder-not-a-real-provider-secret"'
          compose exec -T api test ! -e /run/secrets/tikhub_api_key
'''
    new = '''          sudo test ! -e "${AIMA_RUNTIME_ROOT}/shared/secrets/tikhub_api_key"
          sudo test ! -e "${AIMA_RUNTIME_ROOT}/shared/secrets/llm_api_key"
          sudo test -s "${AIMA_RUNTIME_ROOT}/shared/provider-secrets/tikhub_api_key"
          test "$(sudo stat -c '%u:%g:%a' "${AIMA_RUNTIME_ROOT}/shared/provider-secrets/tikhub_api_key")" = "10001:10001:600"
          compose exec -T worker sh -ec \\
            'test "$(cat /run/provider-secrets/tikhub_api_key)" = "ci-placeholder-not-a-real-provider-secret"'
          compose exec -T api sh -ec \\
            'test "$(cat /run/provider-secrets/tikhub_api_key)" = "ci-placeholder-not-a-real-provider-secret"'
          compose exec -T worker test ! -e /run/secrets/tikhub_api_key
          compose exec -T api test ! -e /run/secrets/tikhub_api_key
          PROVIDER_SECRET_HASH_BEFORE="$(sudo sha256sum "${AIMA_RUNTIME_ROOT}/shared/provider-secrets/tikhub_api_key" | cut -d' ' -f1)"

          # 通过正式管理员 API 轮换 TikHub 配置；新配置必须无需重启立即写入 DB/Secret Store。
          PROVIDER_ID="$(compose exec -T postgres psql -U aima_ugc -d aima_ugc -Atc \\
            "SELECT id FROM provider_configs WHERE display_name = 'TikHub Internal V1';")"
          cat > "${RUNNER_TEMP}/provider-update.json" <<'JSON'
          {
            "display_name": "TikHub Internal V1",
            "base_url": "https://api.tikhub.dev",
            "model": null,
            "api_key": "ci-rotated-provider-secret-not-real",
            "timeout_seconds": 52,
            "max_retries": 4,
            "max_concurrency": 6,
            "max_rps": 2,
            "enabled": true,
            "is_default": false
          }
          JSON
          curl -fsS \\
            -X PUT \\
            -H 'Content-Type: application/json' \\
            --data-binary @"${RUNNER_TEMP}/provider-update.json" \\
            "http://127.0.0.1:18080/api/v1/provider-configs/${PROVIDER_ID}" \\
            > "${RUNNER_TEMP}/provider-update-response.json"
          python3 - "${RUNNER_TEMP}/provider-update-response.json" <<'PY'
          import json
          import sys
          from pathlib import Path

          payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
          assert payload["provider_kind"] == "collection"
          assert payload["provider"] == "tikhub"
          assert payload["base_url"] == "https://api.tikhub.dev"
          assert payload["timeout_seconds"] == 52
          assert payload["max_retries"] == 4
          assert payload["max_concurrency"] == 6
          assert payload["max_rps"] == 2
          assert payload["revision"] == 2
          assert payload["secret_configured"] is True
          assert "api_key" not in payload
          assert "secret_ref" not in payload
          PY
          PROVIDER_RUNTIME_ROW="$(compose exec -T postgres psql -U aima_ugc -d aima_ugc -Atc \\
            "SELECT base_url || '|' || secret_ref || '|' || timeout_seconds || '|' || max_retries || '|' || max_concurrency || '|' || max_rps || '|' || revision FROM provider_configs WHERE id = '${PROVIDER_ID}';")"
          IFS='|' read -r ROTATED_BASE_URL ROTATED_SECRET_REF ROTATED_TIMEOUT ROTATED_RETRIES ROTATED_CONCURRENCY ROTATED_RPS ROTATED_REVISION <<<"${PROVIDER_RUNTIME_ROW}"
          test "${ROTATED_BASE_URL}" = "https://api.tikhub.dev"
          test "${ROTATED_TIMEOUT}" = "52"
          test "${ROTATED_RETRIES}" = "4"
          test "${ROTATED_CONCURRENCY}" = "6"
          test "${ROTATED_RPS}" = "2"
          test "${ROTATED_REVISION}" = "2"
          test "${ROTATED_SECRET_REF}" != "tikhub_api_key"
          sudo test -s "${AIMA_RUNTIME_ROOT}/shared/provider-secrets/${ROTATED_SECRET_REF}"
          test "$(sudo stat -c '%u:%g:%a' "${AIMA_RUNTIME_ROOT}/shared/provider-secrets/${ROTATED_SECRET_REF}")" = "10001:10001:600"
          test "$(sudo cat "${AIMA_RUNTIME_ROOT}/shared/provider-secrets/${ROTATED_SECRET_REF}")" = "ci-rotated-provider-secret-not-real"
          compose exec -T worker sh -ec \\
            "test \"\$(cat /run/provider-secrets/${ROTATED_SECRET_REF})\" = \"ci-rotated-provider-secret-not-real\""
          PROVIDER_JSON_AFTER_ROTATION="$(compose exec -T postgres psql -U aima_ugc -d aima_ugc -Atc \\
            "SELECT row_to_json(p)::text FROM provider_configs p WHERE id = '${PROVIDER_ID}';")"
          if grep -Fq 'ci-rotated-provider-secret-not-real' <<<"${PROVIDER_JSON_AFTER_ROTATION}"; then
            echo "Rotated Provider Secret leaked into provider_configs"
            exit 1
          fi
          if grep -Fq 'ci-rotated-provider-secret-not-real' "${RUNNER_TEMP}/provider-update-response.json"; then
            echo "Rotated Provider Secret leaked into API response"
            exit 1
          fi
          ROTATED_SECRET_HASH_BEFORE="$(sudo sha256sum "${AIMA_RUNTIME_ROOT}/shared/provider-secrets/${ROTATED_SECRET_REF}" | cut -d' ' -f1)"
'''
    text = replace_once(text, old, new, "canonical provider secret assertions")

    old = '''          mounts = {item["Destination"]: item for item in api["Mounts"]}
          expected = {
              "/app/data": (root / "runtime/data", True),
              "/app/logs": (root / "runtime/logs", True),
              "/run/internal-secrets": (root / "shared/secrets", False),
              "/data/aima-historical-input": (root / "historical-input", False),
          }
          for destination, (source, writable) in expected.items():
              actual = mounts[destination]
              assert actual["Type"] == "bind"
              assert Path(actual["Source"]).resolve() == source.resolve()
              assert actual["RW"] is writable

          postgres_mounts = {item["Destination"]: item for item in inspect(postgres_id)["Mounts"]}
'''
    new = '''          mounts = {item["Destination"]: item for item in api["Mounts"]}
          expected = {
              "/app/data": (root / "runtime/data", True),
              "/app/logs": (root / "runtime/logs", True),
              "/run/internal-secrets": (root / "shared/secrets", False),
              "/data/aima-historical-input": (root / "historical-input", False),
              "/run/provider-secrets": (root / "shared/provider-secrets", True),
          }
          for destination, (source, writable) in expected.items():
              actual = mounts[destination]
              assert actual["Type"] == "bind"
              assert Path(actual["Source"]).resolve() == source.resolve()
              assert actual["RW"] is writable

          worker_mounts = {item["Destination"]: item for item in worker["Mounts"]}
          worker_provider_secrets = worker_mounts["/run/provider-secrets"]
          assert worker_provider_secrets["Type"] == "bind"
          assert Path(worker_provider_secrets["Source"]).resolve() == (root / "shared/provider-secrets").resolve()
          assert worker_provider_secrets["RW"] is False

          postgres_mounts = {item["Destination"]: item for item in inspect(postgres_id)["Mounts"]}
'''
    text = replace_once(text, old, new, "canonical provider mount assertions")

    old = '''          PROVIDER_COUNT="$(compose exec -T postgres psql -U aima_ugc -d aima_ugc -Atc \\
            "SELECT count(*) FROM provider_configs WHERE display_name = 'TikHub Internal V1';")"
          test "${PROVIDER_COUNT}" = "1"
          compose exec -T api sh -ec 'test "$(cat /app/data/compose-startup-marker)" = persistence'
'''
    new = '''          PROVIDER_COUNT="$(compose exec -T postgres psql -U aima_ugc -d aima_ugc -Atc \\
            "SELECT count(*) FROM provider_configs WHERE display_name = 'TikHub Internal V1';")"
          test "${PROVIDER_COUNT}" = "1"
          # configure 再次执行也不得用 `.env` 把管理员保存的 DB Provider 配置覆盖回去。
          PROVIDER_RUNTIME_ROW_AFTER_RESTART="$(compose exec -T postgres psql -U aima_ugc -d aima_ugc -Atc \\
            "SELECT base_url || '|' || secret_ref || '|' || timeout_seconds || '|' || max_retries || '|' || max_concurrency || '|' || max_rps || '|' || revision FROM provider_configs WHERE id = '${PROVIDER_ID}';")"
          test "${PROVIDER_RUNTIME_ROW_AFTER_RESTART}" = "${PROVIDER_RUNTIME_ROW}"
          test "$(sudo sha256sum "${AIMA_RUNTIME_ROOT}/shared/provider-secrets/${ROTATED_SECRET_REF}" | cut -d' ' -f1)" = "${ROTATED_SECRET_HASH_BEFORE}"
          test "$(sudo sha256sum "${AIMA_RUNTIME_ROOT}/shared/provider-secrets/tikhub_api_key" | cut -d' ' -f1)" = "${PROVIDER_SECRET_HASH_BEFORE}"
          compose exec -T api sh -ec 'test "$(cat /app/data/compose-startup-marker)" = persistence'
'''
    text = replace_once(text, old, new, "provider restart authority assertion")

    old = '''          PROVIDER_COUNT="$(compose exec -T postgres psql -U aima_ugc -d aima_ugc -Atc \\
            "SELECT count(*) FROM provider_configs WHERE display_name = 'TikHub Internal V1';")"
          test "${PROVIDER_COUNT}" = "1"
          test "$(sudo sha256sum "${AIMA_RUNTIME_ROOT}/shared/secrets/postgres_password" | cut -d' ' -f1)" = "${PASSWORD_HASH_BEFORE}"
'''
    new = '''          PROVIDER_COUNT="$(compose exec -T postgres psql -U aima_ugc -d aima_ugc -Atc \\
            "SELECT count(*) FROM provider_configs WHERE display_name = 'TikHub Internal V1';")"
          test "${PROVIDER_COUNT}" = "1"
          PROVIDER_RUNTIME_ROW_AFTER_RECOVERY="$(compose exec -T postgres psql -U aima_ugc -d aima_ugc -Atc \\
            "SELECT base_url || '|' || secret_ref || '|' || timeout_seconds || '|' || max_retries || '|' || max_concurrency || '|' || max_rps || '|' || revision FROM provider_configs WHERE id = '${PROVIDER_ID}';")"
          test "${PROVIDER_RUNTIME_ROW_AFTER_RECOVERY}" = "${PROVIDER_RUNTIME_ROW}"
          test "$(sudo sha256sum "${AIMA_RUNTIME_ROOT}/shared/provider-secrets/${ROTATED_SECRET_REF}" | cut -d' ' -f1)" = "${ROTATED_SECRET_HASH_BEFORE}"
          test "$(sudo sha256sum "${AIMA_RUNTIME_ROOT}/shared/secrets/postgres_password" | cut -d' ' -f1)" = "${PASSWORD_HASH_BEFORE}"
'''
    text = replace_once(text, old, new, "provider recovery authority assertion")

    old = '''              "bootstrap": {
                  "/host/runtime/data": "bind",
                  "/host/runtime/logs": "bind",
                  "/host/postgres": "volume",
                  "/host/shared/secrets": "volume",
              },
'''
    new = '''              "bootstrap": {
                  "/host/runtime/data": "bind",
                  "/host/runtime/logs": "bind",
                  "/host/postgres": "volume",
                  "/host/shared/secrets": "volume",
                  "/host/shared/provider-secrets": "volume",
              },
'''
    text = replace_once(text, old, new, "windows bootstrap provider volume assertion")

    for service in ("configure", "api", "worker"):
        old = f'''              "{service}": {{
                  "/app/data": "bind",
                  "/app/logs": "bind",
                  "/run/internal-secrets": "volume",
                  "/data/aima-historical-input": "bind",
              }},
'''
        new = f'''              "{service}": {{
                  "/app/data": "bind",
                  "/app/logs": "bind",
                  "/run/internal-secrets": "volume",
                  "/data/aima-historical-input": "bind",
                  "/run/provider-secrets": "volume",
              }},
'''
        text = replace_once(text, old, new, f"windows {service} provider volume assertion")

    text = replace_once(
        text,
        '          assert {"windows_postgres", "windows_internal_secrets"}.issubset(model["volumes"])\n',
        '          assert {"windows_postgres", "windows_internal_secrets", "windows_provider_secrets"}.issubset(model["volumes"])\n',
        "windows provider volume declaration assertion",
    )

    old = '''          API_CONTAINER="$(compose ps -q api)"
          POSTGRES_CONTAINER="$(compose ps -q postgres)"
          python3 - "${API_CONTAINER}" "${POSTGRES_CONTAINER}" "${AIMA_WINDOWS_HOST_ROOT}" <<'PY'
'''
    new = '''          API_CONTAINER="$(compose ps -q api)"
          WORKER_CONTAINER="$(compose ps -q worker)"
          POSTGRES_CONTAINER="$(compose ps -q postgres)"
          python3 - "${API_CONTAINER}" "${WORKER_CONTAINER}" "${POSTGRES_CONTAINER}" "${AIMA_WINDOWS_HOST_ROOT}" <<'PY'
'''
    text = replace_once(text, old, new, "windows worker inspect argument")

    old = '''          api_id, postgres_id, host_root_raw = sys.argv[1:]
          host_root = Path(host_root_raw).resolve()
'''
    new = '''          api_id, worker_id, postgres_id, host_root_raw = sys.argv[1:]
          host_root = Path(host_root_raw).resolve()
'''
    text = replace_once(text, old, new, "windows worker inspect unpack")

    old = '''          assert api_mounts["/run/internal-secrets"]["Type"] == "volume"
          assert api_mounts["/run/internal-secrets"]["RW"] is False

          postgres_mounts = mounts(postgres_id)
'''
    new = '''          assert api_mounts["/run/internal-secrets"]["Type"] == "volume"
          assert api_mounts["/run/internal-secrets"]["RW"] is False
          assert api_mounts["/run/provider-secrets"]["Type"] == "volume"
          assert api_mounts["/run/provider-secrets"]["RW"] is True
          worker_mounts = mounts(worker_id)
          assert worker_mounts["/run/provider-secrets"]["Type"] == "volume"
          assert worker_mounts["/run/provider-secrets"]["RW"] is False

          postgres_mounts = mounts(postgres_id)
'''
    text = replace_once(text, old, new, "windows provider mount permissions")

    write(path, text)


def patch_api_docs() -> None:
    path = "docs/03_API接口说明.md"
    text = read(path)
    anchor = "\n---\n\n# 4. Collection Runtime API\n"
    section = '''
---

## 3.1 管理员 Provider 配置 API

LLM 与采集 Provider 的运行时配置统一由管理员配置中心维护；Secret 明文只在写请求进入后端 Secret Store，读取响应、数据库审计和日志均不得返回 API Key 或内部 `secret_ref`。

### `GET /api/v1/provider-configs`

管理员读取 LLM/TikHub Provider 的安全投影。可按 `provider_kind=llm|collection` 筛选；响应通过 `secret_configured` 表示密钥是否已经配置。

### `POST /api/v1/provider-configs`

创建新的 Provider 配置。LLM 需要 `model`；Collection Provider 不使用 `model`。提交 `api_key` 时服务端创建不可变 Secret 引用，数据库仅保存该引用。

### `PUT /api/v1/provider-configs/{provider_config_id}`

完整更新可变 Provider 字段。省略 `api_key` 表示保持当前 Secret；提供新 `api_key` 表示轮换到新的不可变 Secret 版本。保存成功后**无需重启服务**：之后新建的 Analysis/Collection Run 读取当前数据库配置；已创建 Run 与同 Run 自动重试继续使用创建时冻结的运行时快照。

实现边界：

- [`backend/src/aima_ugc/contracts/administration.py`](../backend/src/aima_ugc/contracts/administration.py)
- [`backend/src/aima_ugc/bootstrap/administration_http.py`](../backend/src/aima_ugc/bootstrap/administration_http.py)
- [`backend/src/aima_ugc/bootstrap/runtime_config.py`](../backend/src/aima_ugc/bootstrap/runtime_config.py)
- [`backend/src/aima_ugc/platform/security/secrets.py`](../backend/src/aima_ugc/platform/security/secrets.py)

---

# 4. Collection Runtime API
'''
    text = replace_once(text, anchor, "\n" + section, "provider API docs")
    write(path, text)


def main() -> None:
    patch_runtime_acceptance()
    patch_api_docs()


if __name__ == "__main__":
    main()
