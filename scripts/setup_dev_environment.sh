#!/usr/bin/env bash
# AIMA_UGC CentOS Stream 9 x86_64 开发/CI Runner 宿主环境初始化脚本。
# 目标：安装仓库锁定运行时与 Docker；不安装/注册 GitHub Actions Runner 本体。

set -Eeuo pipefail
umask 022

PYTHON_VERSION="3.14.7"
PYTHON_SHA256="3b48dac8fb59f62eaa67ac83c1eb12bda1b7a08406dd286e252c11a66be27f81"
NODE_VERSION="24.19.0"
NODE_SHA256="14b342e71204f811bde6153be8e04b62aef63c236fef92b55f9c83154b409647"
NPM_VERSION="11.17.0"
UV_VERSION="0.12.3"
DOCKER_VERSION="29.7.2"
DOCKER_COMPOSE_VERSION="5.4.0"
CONTAINERD_RPM_VERSION="2.3.3-1.el9"
BUILDX_RPM_VERSION="0.36.1-1.el9"

TOOLCHAIN_ROOT="${TOOLCHAIN_ROOT:-/opt/aima-ugc/toolchain}"
DOCKER_DATA_ROOT="${DOCKER_DATA_ROOT:-/data/docker}"
CACHE_ROOT="${CACHE_ROOT:-/data/cache}"
RUN_DOCKER_SMOKE="${RUN_DOCKER_SMOKE:-1}"
ALLOW_SYSTEM_PACKAGE_UPDATES="${ALLOW_SYSTEM_PACKAGE_UPDATES:-0}"
STOP_GITHUB_RUNNER="${STOP_GITHUB_RUNNER:-1}"

PYTHON_PREFIX="${TOOLCHAIN_ROOT}/python/${PYTHON_VERSION}"
NODE_PREFIX="${TOOLCHAIN_ROOT}/node/${NODE_VERSION}"
TOOLCHAIN_BIN="${TOOLCHAIN_ROOT}/bin"
PROFILE_PATH="/etc/profile.d/aima-ugc-toolchain.sh"
DOCKER_REPO_PATH="/etc/yum.repos.d/aima-docker-ce.repo"
CENTOS_REPO_PATH="/etc/yum.repos.d/aima-centos-stream.repo"
DOCKER_DAEMON_PATH="/etc/docker/daemon.json"
LOCK_PATH="/run/lock/aima-ugc-bootstrap.lock"

AIMA_RUNTIME_STOPPED=0
declare -a STOPPED_UNITS=()
declare -a STOPPED_CONTAINERS=()
SMOKE_CONTAINER_NAME=""

PYTHON_SOURCE_URL="https://mirrors.tuna.tsinghua.edu.cn/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tar.xz"
NODE_BASE_URL="https://npmmirror.com/mirrors/node/v${NODE_VERSION}"
NODE_ARCHIVE="node-v${NODE_VERSION}-linux-x64.tar.xz"
NODE_SOURCE_URL="${NODE_BASE_URL}/${NODE_ARCHIVE}"
NPM_REGISTRY="https://registry.npmmirror.com"
PYPI_INDEX="https://pypi.tuna.tsinghua.edu.cn/simple"
DOCKER_RPM_BASE="https://mirrors.aliyun.com/docker-ce/linux/centos"
DOCKER_REGISTRY_MIRRORS=(
  "https://docker.1panel.live"
  "https://hub.1panel.dev"
  "https://docker.m.daocloud.io"
)
CENTOS_STREAM_BASE="https://mirrors.aliyun.com/centos-stream/9-stream"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S%z')" "$*"
}

die() {
  log "错误：$*" >&2
  exit 1
}

require_root_and_platform() {
  [[ "$(id -u)" == "0" ]] || die "请以 root 执行。"
  [[ -r /etc/os-release ]] || die "缺少 /etc/os-release。"
  # shellcheck disable=SC1091
  source /etc/os-release
  [[ "${ID:-}" == "centos" && "${VERSION_ID:-}" == "9" ]] || \
    die "仅支持 CentOS Stream 9；当前为 ${PRETTY_NAME:-unknown}。"
  [[ "$(uname -m)" == "x86_64" ]] || die "仅支持 x86_64。"
  [[ -d /data && "$(findmnt -n -o FSTYPE /data 2>/dev/null || true)" != "" ]] || \
    die "/data 必须是可用文件系统挂载点。"
}

require_resources() {
  local available_kib root_free_kib data_free_kib
  available_kib="$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)"
  root_free_kib="$(df -Pk / | awk 'NR==2 {print $4}')"
  data_free_kib="$(df -Pk /data | awk 'NR==2 {print $4}')"
  (( available_kib >= 1572864 )) || die "可用内存不足 1.5 GiB；请先停止非必要任务后再运行。"
  (( root_free_kib >= 3145728 )) || die "根文件系统可用空间不足 3 GiB。"
  (( data_free_kib >= 8388608 )) || die "/data 可用空间不足 8 GiB。"
  log "资源门禁通过：MemAvailable=$(awk '/MemAvailable:/ {printf "%.2f GiB", $2/1048576}' /proc/meminfo)，根盘和 /data 空间充足。"
}

stop_aima_runtime() {
  [[ "${AIMA_RUNTIME_STOPPED}" == "0" ]] || return
  if [[ "${GITHUB_ACTIONS:-}" == "true" ]]; then
    die "检测到脚本正在 GitHub Actions Job 内运行；拒绝停止自身 Runner。请从独立 SSH 会话执行。"
  fi

  log "停止明确归属于 AIMA_UGC 的托管进程；不触碰 sshd、网络、Nginx、共享 PostgreSQL 或 /opt/ugc-dashboard。"
  local unit
  while IFS= read -r unit; do
    [[ -n "${unit}" ]] || continue
    if [[ "${unit}" == actions.runner.* && "${STOP_GITHUB_RUNNER}" != "1" ]]; then
      continue
    fi
    if systemctl is-active --quiet "${unit}"; then
      systemctl stop "${unit}"
      STOPPED_UNITS+=("${unit}")
    fi
  done < <(
    systemctl list-unit-files --type=service --no-legend 2>/dev/null \
      | awk '{print $1}' \
      | grep -E '^(aima-ugc([-.].*)?|actions\.runner\..*)\.service$' \
      || true
  )

  if command -v docker >/dev/null 2>&1 && systemctl is-active --quiet docker; then
    local id name compose_project managed
    while IFS=$'\t' read -r id name compose_project managed; do
      [[ -n "${id}" ]] || continue
      if [[ "${name}" =~ ^aima[-_]ugc([_-]|$) || "${compose_project}" == "aima_ugc" || "${managed}" == "true" ]]; then
        docker stop --time 30 "${id}" >/dev/null
        STOPPED_CONTAINERS+=("${id}")
      fi
    done < <(docker ps --format '{{.ID}}\t{{.Names}}\t{{.Label "com.docker.compose.project"}}\t{{.Label "com.aima_ugc.managed"}}')
  fi

  local remaining
  remaining="$(pgrep -af "^${TOOLCHAIN_ROOT}/" || true)"
  [[ -z "${remaining}" ]] || die "仍有未受 systemd/容器托管的 AIMA toolchain 进程，拒绝强杀：${remaining}"
  AIMA_RUNTIME_STOPPED=1
}

restore_aima_runtime() {
  local id unit
  if command -v docker >/dev/null 2>&1 && systemctl is-active --quiet docker; then
    for id in "${STOPPED_CONTAINERS[@]:-}"; do
      [[ -n "${id}" ]] || continue
      docker start "${id}" >/dev/null 2>&1 || log "警告：容器 ${id} 未能自动恢复，请人工检查。"
    done
  fi
  for unit in "${STOPPED_UNITS[@]:-}"; do
    [[ -n "${unit}" ]] || continue
    systemctl start "${unit}" || log "警告：服务 ${unit} 未能自动恢复，请人工检查。"
  done
}

write_temporary_china_repos() {
  install -d -m 0755 /etc/yum.repos.d
  cat >"${CENTOS_REPO_PATH}" <<EOF
[aima-baseos]
name=AIMA CentOS Stream 9 BaseOS - Aliyun
baseurl=${CENTOS_STREAM_BASE}/BaseOS/\$basearch/os
enabled=0
gpgcheck=1
repo_gpgcheck=0
gpgkey=https://mirrors.aliyun.com/centos/RPM-GPG-KEY-CentOS-Official

[aima-appstream]
name=AIMA CentOS Stream 9 AppStream - Aliyun
baseurl=${CENTOS_STREAM_BASE}/AppStream/\$basearch/os
enabled=0
gpgcheck=1
repo_gpgcheck=0
gpgkey=https://mirrors.aliyun.com/centos/RPM-GPG-KEY-CentOS-Official

[aima-crb]
name=AIMA CentOS Stream 9 CRB - Aliyun
baseurl=${CENTOS_STREAM_BASE}/CRB/\$basearch/os
enabled=0
gpgcheck=1
repo_gpgcheck=0
gpgkey=https://mirrors.aliyun.com/centos/RPM-GPG-KEY-CentOS-Official
EOF

  cat >"${DOCKER_REPO_PATH}" <<EOF
[aima-docker-ce]
name=AIMA Docker CE Stable - Aliyun
baseurl=${DOCKER_RPM_BASE}/9/\$basearch/stable
enabled=0
gpgcheck=1
repo_gpgcheck=0
gpgkey=${DOCKER_RPM_BASE}/gpg
EOF
}

dnf_china() {
  dnf -y \
    --disablerepo='*' \
    --enablerepo=aima-baseos \
    --enablerepo=aima-appstream \
    --enablerepo=aima-crb \
    --setopt=max_parallel_downloads=1 \
    --setopt=install_weak_deps=False \
    "$@"
}

install_missing_china_packages() {
  local package preview
  local -a missing=()
  for package in "$@"; do
    rpm -q "${package}" >/dev/null 2>&1 || missing+=("${package}")
  done
  if (( ${#missing[@]} == 0 )); then
    log "系统基础依赖已满足，跳过 DNF 安装。"
    return
  fi

  preview="$(dnf_china --assumeno install "${missing[@]}" 2>&1 || true)"
  if [[ "${ALLOW_SYSTEM_PACKAGE_UPDATES}" != "1" ]] && grep -Eq '^Upgrading:|^Downgrading:|^Upgrade[[:space:]]+[1-9]|^Downgrade[[:space:]]+[1-9]' <<<"${preview}"; then
    printf '%s\n' "${preview}" >&2
    die "补齐依赖会升级/降级已装系统包，默认拒绝。确认维护窗口后可显式设置 ALLOW_SYSTEM_PACKAGE_UPDATES=1。"
  fi
  stop_aima_runtime
  log "从阿里云 CentOS Stream 镜像串行安装缺失依赖：${missing[*]}"
  dnf_china install "${missing[@]}"
}

install_base_packages() {
  install_missing_china_packages \
    ca-certificates curl git jq tar gzip xz unzip rsync which \
    gcc make pkgconf-pkg-config patch \
    bzip2-devel expat-devel gdbm-devel libffi-devel libnsl2-devel \
    libtirpc-devel libuuid-devel libxcrypt-devel ncurses-devel \
    openssl-devel readline-devel sqlite-devel xz-devel zlib-devel libzstd-devel \
    libicu krb5-libs openssl-libs zlib libcurl libgcc libstdc++
  update-ca-trust
  if ! ldconfig -p | grep -q 'libpq.so.5'; then
    install_missing_china_packages libpq
  fi
}

sha256_check() {
  local expected="$1" file="$2"
  printf '%s  %s\n' "${expected}" "${file}" | sha256sum -c -
}

install_python() {
  if [[ -x "${PYTHON_PREFIX}/bin/python3.14" ]]; then
    [[ "$("${PYTHON_PREFIX}/bin/python3.14" --version 2>&1)" == "Python ${PYTHON_VERSION}" ]] || \
      die "${PYTHON_PREFIX} 已存在但版本不匹配。"
    log "Python ${PYTHON_VERSION} 已存在，跳过编译。"
    return
  fi
  [[ ! -e "${PYTHON_PREFIX}" ]] || die "${PYTHON_PREFIX} 是不完整目录；请人工检查后处理。"
  stop_aima_runtime

  local archive source_dir
  archive="${WORK_DIR}/Python-${PYTHON_VERSION}.tar.xz"
  source_dir="${WORK_DIR}/Python-${PYTHON_VERSION}"
  log "从清华 TUNA 下载并校验 Python ${PYTHON_VERSION} 源码。"
  curl --fail --location --silent --show-error --retry 3 --connect-timeout 10 \
    "${PYTHON_SOURCE_URL}" --output "${archive}"
  sha256_check "${PYTHON_SHA256}" "${archive}"
  tar -xJf "${archive}" -C "${WORK_DIR}"

  log "以低优先级、单任务编译 Python；不会启用 PGO/LTO。"
  (
    cd "${source_dir}"
    ./configure \
      --prefix="${PYTHON_PREFIX}" \
      --with-ensurepip=install \
      --with-system-expat \
      --with-lto=no
    nice -n 15 ionice -c 3 make -j1
    nice -n 15 ionice -c 3 make -j1 install
  )

  "${PYTHON_PREFIX}/bin/python3.14" - <<'PY'
import bz2
import ctypes
import lzma
import readline
import sqlite3
import ssl
import zlib
import compression.zstd

print("Python stdlib native modules: ok")
PY
}

install_node_and_npm() {
  if [[ -x "${NODE_PREFIX}/bin/node" ]]; then
    [[ "$("${NODE_PREFIX}/bin/node" --version)" == "v${NODE_VERSION}" ]] || \
      die "${NODE_PREFIX} 已存在但版本不匹配。"
    log "Node.js ${NODE_VERSION} 已存在，跳过解压。"
  else
    [[ ! -e "${NODE_PREFIX}" ]] || die "${NODE_PREFIX} 是不完整目录；请人工检查后处理。"
    stop_aima_runtime
    local archive extracted staging
    archive="${WORK_DIR}/${NODE_ARCHIVE}"
    extracted="${WORK_DIR}/node-v${NODE_VERSION}-linux-x64"
    staging="${TOOLCHAIN_ROOT}/node/.${NODE_VERSION}.installing"
    log "从 npmmirror 下载并校验 Node.js ${NODE_VERSION}。"
    curl --fail --location --silent --show-error --retry 3 --connect-timeout 10 \
      "${NODE_SOURCE_URL}" --output "${archive}"
    sha256_check "${NODE_SHA256}" "${archive}"
    tar -xJf "${archive}" -C "${WORK_DIR}"
    install -d -m 0755 "$(dirname "${NODE_PREFIX}")"
    [[ ! -e "${staging}" ]] || die "发现遗留安装暂存目录 ${staging}。"
    mv "${extracted}" "${staging}"
    mv "${staging}" "${NODE_PREFIX}"
  fi

  if [[ "$(PATH="${NODE_PREFIX}/bin:${PATH}" "${NODE_PREFIX}/bin/npm" --version 2>/dev/null || true)" == "${NPM_VERSION}" ]]; then
    log "npm ${NPM_VERSION} 已存在，跳过安装。"
    return
  fi
  stop_aima_runtime
  log "从 npmmirror 精确安装 npm ${NPM_VERSION}（单连接）。"
  PATH="${NODE_PREFIX}/bin:${PATH}" \
  npm_config_registry="${NPM_REGISTRY}" \
  npm_config_maxsockets=1 \
  npm_config_audit=false \
  npm_config_fund=false \
  "${NODE_PREFIX}/bin/npm" install --global --prefix "${NODE_PREFIX}" "npm@${NPM_VERSION}"
  [[ "$(PATH="${NODE_PREFIX}/bin:${PATH}" "${NODE_PREFIX}/bin/npm" --version)" == "${NPM_VERSION}" ]] || \
    die "npm 版本验证失败。"
}

install_uv() {
  if [[ -x "${PYTHON_PREFIX}/bin/uv" ]] && \
    [[ "$("${PYTHON_PREFIX}/bin/uv" --version | awk '{print $2}')" == "${UV_VERSION}" ]]; then
    log "uv ${UV_VERSION} 已存在，跳过安装。"
    return
  fi
  stop_aima_runtime
  log "从清华 TUNA PyPI 精确安装 uv ${UV_VERSION}。"
  "${PYTHON_PREFIX}/bin/python3.14" -m pip install \
    --disable-pip-version-check \
    --no-cache-dir \
    --index-url "${PYPI_INDEX}" \
    "uv==${UV_VERSION}"
  [[ "$("${PYTHON_PREFIX}/bin/uv" --version | awk '{print $2}')" == "${UV_VERSION}" ]] || \
    die "uv 版本验证失败。"
}

write_toolchain_entrypoints() {
  install -d -m 0755 "${TOOLCHAIN_BIN}"
  ln -sfn "${PYTHON_PREFIX}/bin/python3.14" "${TOOLCHAIN_BIN}/python"
  ln -sfn "${PYTHON_PREFIX}/bin/python3.14" "${TOOLCHAIN_BIN}/python3"
  ln -sfn "${PYTHON_PREFIX}/bin/pip3.14" "${TOOLCHAIN_BIN}/pip"
  ln -sfn "${PYTHON_PREFIX}/bin/uv" "${TOOLCHAIN_BIN}/uv"
  ln -sfn "${PYTHON_PREFIX}/bin/uvx" "${TOOLCHAIN_BIN}/uvx"
  ln -sfn "${NODE_PREFIX}/bin/node" "${TOOLCHAIN_BIN}/node"
  ln -sfn "${NODE_PREFIX}/bin/npm" "${TOOLCHAIN_BIN}/npm"
  ln -sfn "${NODE_PREFIX}/bin/npx" "${TOOLCHAIN_BIN}/npx"
  cat >"${PROFILE_PATH}" <<EOF
# AIMA_UGC locked CI/development toolchain.
export PATH="${TOOLCHAIN_BIN}:\$PATH"
EOF
  chmod 0644 "${PROFILE_PATH}"
}

check_docker_conflicts() {
  local package
  for package in docker docker-client docker-client-latest docker-common docker-latest \
    docker-latest-logrotate docker-logrotate docker-engine moby-engine podman-docker; do
    if rpm -q "${package}" >/dev/null 2>&1; then
      die "检测到可能冲突的软件包 ${package}；脚本不会自动卸载，请人工评估。"
    fi
  done
}

install_docker() {
  local package expected actual preview
  local -a docker_requirements=(
    "docker-ce:${DOCKER_VERSION}"
    "docker-ce-cli:${DOCKER_VERSION}"
    "containerd.io:${CONTAINERD_RPM_VERSION%%-*}"
    "docker-buildx-plugin:${BUILDX_RPM_VERSION%%-*}"
    "docker-compose-plugin:${DOCKER_COMPOSE_VERSION}"
  )
  local docker_packages_ready=1
  for expected in "${docker_requirements[@]}"; do
    package="${expected%%:*}"
    expected="${expected#*:}"
    if rpm -q "${package}" >/dev/null 2>&1; then
      actual="$(rpm -q --qf '%{VERSION}' "${package}")"
      [[ "${actual}" == "${expected}" ]] || \
        die "已安装 ${package} ${actual}，与目标 ${expected} 不一致；脚本不会自动升级、降级或卸载。"
    else
      docker_packages_ready=0
    fi
  done

  if [[ "${docker_packages_ready}" == "0" ]]; then
    check_docker_conflicts
    preview="$(dnf --assumeno \
      --disablerepo='*' \
      --enablerepo=aima-baseos \
      --enablerepo=aima-appstream \
      --enablerepo=aima-crb \
      --enablerepo=aima-docker-ce \
      --setopt=max_parallel_downloads=1 \
      --setopt=install_weak_deps=False \
      install \
        "docker-ce-3:${DOCKER_VERSION}-1.el9" \
        "docker-ce-cli-1:${DOCKER_VERSION}-1.el9" \
        "containerd.io-${CONTAINERD_RPM_VERSION}" \
        "docker-buildx-plugin-${BUILDX_RPM_VERSION}" \
        "docker-compose-plugin-${DOCKER_COMPOSE_VERSION}-1.el9" 2>&1 || true)"
    if [[ "${ALLOW_SYSTEM_PACKAGE_UPDATES}" != "1" ]] && grep -Eq '^Upgrading:|^Downgrading:|^Upgrade[[:space:]]+[1-9]|^Downgrade[[:space:]]+[1-9]' <<<"${preview}"; then
      printf '%s\n' "${preview}" >&2
      die "安装 Docker 会升级/降级已装系统包，默认拒绝。确认维护窗口后可显式设置 ALLOW_SYSTEM_PACKAGE_UPDATES=1。"
    fi
    stop_aima_runtime
    log "从阿里云 Docker CE 镜像安装缺失的精确版本。"
    dnf -y \
      --disablerepo='*' \
      --enablerepo=aima-baseos \
      --enablerepo=aima-appstream \
      --enablerepo=aima-crb \
      --enablerepo=aima-docker-ce \
      --setopt=max_parallel_downloads=1 \
      --setopt=install_weak_deps=False \
      install \
        "docker-ce-3:${DOCKER_VERSION}-1.el9" \
        "docker-ce-cli-1:${DOCKER_VERSION}-1.el9" \
        "containerd.io-${CONTAINERD_RPM_VERSION}" \
        "docker-buildx-plugin-${BUILDX_RPM_VERSION}" \
        "docker-compose-plugin-${DOCKER_COMPOSE_VERSION}-1.el9"
  else
    log "Docker/Containerd/Buildx/Compose 精确版本已满足，跳过 RPM 安装。"
  fi

  install -d -m 0755 /etc/docker "${DOCKER_DATA_ROOT}"
  local desired existing backup merged config_changed was_active mirrors_json
  config_changed=0
  was_active=0
  systemctl is-active --quiet docker && was_active=1
  mirrors_json="$(printf '%s\n' "${DOCKER_REGISTRY_MIRRORS[@]}" | jq -R . | jq -s .)"
  desired="$(jq -n \
    --arg data_root "${DOCKER_DATA_ROOT}" \
    --argjson mirrors "${mirrors_json}" \
    '{"data-root":$data_root,"registry-mirrors":$mirrors,"max-download-attempts":5,"log-driver":"local","log-opts":{"max-size":"20m","max-file":"5"}}')"
  if [[ -s "${DOCKER_DAEMON_PATH}" ]]; then
    jq empty "${DOCKER_DAEMON_PATH}" || die "现有 ${DOCKER_DAEMON_PATH} 不是合法 JSON。"
    existing="$(cat "${DOCKER_DAEMON_PATH}")"
    merged="$(jq -s '.[0] * .[1]' <(printf '%s\n' "${existing}") <(printf '%s\n' "${desired}"))"
    if [[ "$(jq -S . <<<"${existing}")" != "$(jq -S . <<<"${merged}")" ]]; then
      stop_aima_runtime
      if [[ "${was_active}" == "1" && -n "$(docker ps -q)" ]]; then
        die "Docker 配置需变更，但仍有非 AIMA 容器运行；拒绝重启 Docker。"
      fi
      backup="${DOCKER_DAEMON_PATH}.aima-backup-$(date '+%Y%m%d%H%M%S')"
      cp -a "${DOCKER_DAEMON_PATH}" "${backup}"
      printf '%s\n' "${merged}" >"${DOCKER_DAEMON_PATH}.tmp"
      mv "${DOCKER_DAEMON_PATH}.tmp" "${DOCKER_DAEMON_PATH}"
      config_changed=1
      log "已保留现有 Docker 配置备份：${backup}"
    else
      log "Docker daemon 配置已满足，跳过改写和重启。"
    fi
  else
    stop_aima_runtime
    printf '%s\n' "${desired}" >"${DOCKER_DAEMON_PATH}"
    config_changed=1
  fi
  chmod 0644 "${DOCKER_DAEMON_PATH}"
  dockerd --validate --config-file "${DOCKER_DAEMON_PATH}"

  if [[ "${was_active}" == "1" ]]; then
    [[ "${config_changed}" == "0" ]] || systemctl restart docker
    systemctl enable docker >/dev/null
  else
    systemctl enable --now docker
  fi
  systemctl is-active --quiet docker || die "Docker 服务未运行。"
  [[ "$(docker version --format '{{.Server.Version}}')" == "${DOCKER_VERSION}" ]] || die "Docker Server 版本不匹配。"
  [[ "$(docker compose version --short | sed 's/^v//')" == "${DOCKER_COMPOSE_VERSION}" ]] || \
    die "Docker Compose 版本不匹配。"
  docker info --format '{{json .DockerRootDir}} {{json .RegistryConfig.Mirrors}}'
}

docker_postgres_smoke() {
  [[ "${RUN_DOCKER_SMOKE}" == "1" ]] || {
    log "RUN_DOCKER_SMOKE=${RUN_DOCKER_SMOKE}，跳过 PostgreSQL 容器 smoke。"
    return
  }
  local name password attempt
  name="aima-bootstrap-postgres-smoke-$$"
  SMOKE_CONTAINER_NAME="${name}"
  password="aima-bootstrap-smoke-only"
  log "通过 Docker Hub registry mirrors 拉取官方 postgres:18.4，并运行不映射宿主端口的临时 smoke。"
  if docker image inspect postgres:18.4 >/dev/null 2>&1; then
    log "postgres:18.4 已缓存，跳过重复拉取。"
  else
    for attempt in 1 2 3; do
      docker pull postgres:18.4 && break
      [[ "${attempt}" == "3" ]] && die "Docker Hub 镜像连续 3 次拉取 postgres:18.4 失败。"
      log "镜像拉取第 ${attempt} 次失败，10 秒后串行重试。"
      sleep 10
    done
  fi
  docker run --detach --rm \
    --name "${name}" \
    --memory=512m \
    --cpus=1 \
    --health-cmd='pg_isready -U postgres' \
    --health-interval=2s \
    --health-timeout=3s \
    --health-retries=20 \
    -e "POSTGRES_PASSWORD=${password}" \
    postgres:18.4 >/dev/null
  local i state
  for i in $(seq 1 40); do
    state="$(docker inspect --format '{{.State.Health.Status}}' "${name}" 2>/dev/null || true)"
    [[ "${state}" == "healthy" ]] && break
    [[ "${state}" == "unhealthy" ]] && {
      docker logs "${name}" || true
      docker rm -f "${name}" >/dev/null 2>&1 || true
      die "PostgreSQL 18.4 容器健康检查失败。"
    }
    sleep 2
  done
  [[ "${state}" == "healthy" ]] || {
    docker logs "${name}" || true
    docker rm -f "${name}" >/dev/null 2>&1 || true
    die "PostgreSQL 18.4 容器未在时限内就绪。"
  }
  docker exec "${name}" postgres --version
  docker rm -f "${name}" >/dev/null
  SMOKE_CONTAINER_NAME=""
}

verify_runner_prerequisites() {
  log "验证 GitHub Runner 宿主前置条件（不下载、不注册 Runner）。"
  command -v git >/dev/null
  command -v curl >/dev/null
  ldconfig -p | grep -q 'libpq.so.5' || die "缺少 libpq.so.5；Linux 下 psycopg 3 需要该运行库。"

  local url code attempt
  for url in https://github.com https://api.github.com https://github-releases.githubusercontent.com; do
    code="000"
    for attempt in 1 2 3; do
      code="$(curl -4 -LIsS --connect-timeout 10 --max-time 30 -o /dev/null -w '%{http_code}' "${url}" || true)"
      [[ "${code}" != "000" ]] && break
      [[ "${attempt}" == "3" ]] || sleep 10
    done
    [[ "${code}" != "000" ]] || die "无法访问 GitHub 必需域名：${url}"
    printf 'GitHub connectivity: %s %s\n' "${code}" "${url}"
  done

  PATH="${TOOLCHAIN_BIN}:${PATH}" python --version
  PATH="${TOOLCHAIN_BIN}:${PATH}" node --version
  PATH="${TOOLCHAIN_BIN}:${PATH}" npm --version
  PATH="${TOOLCHAIN_BIN}:${PATH}" uv --version
  git --version
  docker --version
  docker compose version
}

cleanup() {
  local candidate="${WORK_DIR:-}"
  if [[ -n "${SMOKE_CONTAINER_NAME:-}" && "${SMOKE_CONTAINER_NAME}" == aima-bootstrap-postgres-smoke-* ]] && \
    command -v docker >/dev/null 2>&1; then
    docker rm -f "${SMOKE_CONTAINER_NAME}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${candidate}" && -d "${candidate}" && "${candidate}" == "${CACHE_ROOT}"/aima-bootstrap.* ]]; then
    rm -rf -- "${candidate}"
  fi
}

on_exit() {
  local status=$?
  set +e
  restore_aima_runtime
  cleanup
  return "${status}"
}

main() {
  require_root_and_platform
  exec 9>"${LOCK_PATH}"
  flock -n 9 || die "另一个 AIMA_UGC 初始化任务正在运行。"
  require_resources
  install -d -m 0755 "${CACHE_ROOT}" "${TOOLCHAIN_ROOT}"
  WORK_DIR="$(mktemp -d -p "${CACHE_ROOT}" aima-bootstrap.XXXXXX)"
  trap on_exit EXIT
  export MAKEFLAGS='-j1'
  export CMAKE_BUILD_PARALLEL_LEVEL=1
  export TMPDIR="${WORK_DIR}"

  write_temporary_china_repos
  install_base_packages
  install_python
  install_node_and_npm
  install_uv
  write_toolchain_entrypoints
  install_docker
  docker_postgres_smoke
  verify_runner_prerequisites
  restore_aima_runtime
  STOPPED_UNITS=()
  STOPPED_CONTAINERS=()
  log "AIMA_UGC CentOS 9 Runner 宿主环境初始化完成。"
  log "新登录 shell 会自动使用 ${TOOLCHAIN_BIN}；当前 shell 可执行：source ${PROFILE_PATH}"
}

main "$@"