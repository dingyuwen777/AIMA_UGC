@echo off
REM Windows 源码本地重建入口；日常启停仍使用 scripts/deploy/start_compose.py。
REM 用法：deploy.cmd 只重建 backend；deploy.cmd both 同时重建 frontend。
REM 前置：仓库根 env.local、Docker Desktop 和仓库锁定的 uv/Python 环境。
REM 本脚本会执行本地迁移与服务重建；不要用于公司服务器或离线 Release。
REM 资源分配、完整常驻服务和健康等待复用正式启动入口，不复制容量算法。

setlocal
cd /d "%~dp0"
if errorlevel 1 exit /b 1
if not "%~1"=="" if /i not "%~1"=="both" (
  echo 用法：deploy.cmd [both]
  exit /b 2
)
if not "%~2"=="" exit /b 2

set "COMPOSE=docker compose --env-file env.local -f compose.yaml -f compose.windows.yaml -f compose.auto.yaml"
set "TARGET=api"
if /i "%~1"=="both" set "TARGET=api frontend"

echo [1/5] 重建镜像（目标：%TARGET%）...
docker compose --env-file env.local -f compose.yaml -f compose.windows.yaml build %TARGET%
if errorlevel 1 exit /b %ERRORLEVEL%

echo [2/5] 使用正式启动入口生成并校验资源配额...
uv run --locked python scripts/deploy/start_compose.py --env-file env.local --dry-run
if errorlevel 1 exit /b %ERRORLEVEL%

echo [3/5] 执行本地数据库迁移...
%COMPOSE% run --rm migrate
if errorlevel 1 exit /b %ERRORLEVEL%

echo [4/5] 使用正式启动入口启动全部服务并等待健康...
uv run --locked python scripts/deploy/start_compose.py --env-file env.local
if errorlevel 1 exit /b %ERRORLEVEL%

REM api 重建后 frontend 必须重新创建，确保 nginx 重新解析其当前地址。
REM --no-deps 防止重建其他服务，--wait 直接检查当前 Compose 项目的实际容器。
echo [5/5] 重新创建 frontend 并等待健康...
%COMPOSE% up -d --no-deps --no-build --pull never --force-recreate --wait frontend
if errorlevel 1 exit /b %ERRORLEVEL%

%COMPOSE% ps --format "{{.Name}} | {{.Status}}"
if errorlevel 1 exit /b %ERRORLEVEL%
echo 本地重建完成。环境与端口说明见 docs/guides/03_Windows_Docker_Desktop_Compose运行.md。
exit /b 0
