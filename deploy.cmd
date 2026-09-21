@echo off
REM ============================================================================
REM AIMA_UGC 飞书登录模块 · 本地重建与重启（一键，含 nginx 缓存修复）
REM ============================================================================
REM
REM ════════ 为什么需要这个脚本 ════════
REM
REM 重建 backend 镜像后，api 容器会拿到**新的容器 IP**；
REM 而 nginx 在**启动时**解析一次 `api` 主机名并缓存结果，
REM 因此它仍会把请求转发到**旧 IP** → 客户端看到 502 Bad Gateway。
REM
REM 这个坑在本项目实际踩过两次。`docker compose up -d` **不会**重启
REM 没有配置变化的容器，所以 frontend 必须**显式重启**。
REM
REM ════════ 用法 ════════
REM
REM   deploy.cmd              只重建 backend + 重启 api/worker/scheduler/frontend
REM   deploy.cmd both         同时重建 backend 与 frontend
REM
REM ════════ 前置 ════════
REM
REM   1. 本目录即仓库根（脚本会自己 cd 到这里）
REM   2. env.local 已存在（含飞书配置与 AIMA_HOST_ROOT）
REM   3. Docker Desktop 已启动
REM
REM ============================================================================

setlocal
cd /d "%~dp0"

set "COMPOSE=docker compose --env-file env.local -f compose.yaml -f compose.windows.yaml"
set "TARGET=api"

if /i "%~1"=="both" set "TARGET=api frontend"

echo.
echo [1/4] 重建镜像（目标：%TARGET%）...
%COMPOSE% build %TARGET%
if errorlevel 1 (
  echo   构建失败（exit=%ERRORLEVEL%），中止。
  exit /b %ERRORLEVEL%
)
echo   构建完成。

echo.
echo [2/4] 执行数据库迁移（幂等；无新迁移时是空操作）...
%COMPOSE% run --rm migrate
if errorlevel 1 (
  echo   迁移失败（exit=%ERRORLEVEL%），中止。
  exit /b %ERRORLEVEL%
)
echo   迁移完成。

echo.
echo [3/4] 启动服务...
%COMPOSE% up -d --wait api worker scheduler frontend
if errorlevel 1 (
  echo   启动失败（exit=%ERRORLEVEL%），中止。
  exit /b %ERRORLEVEL%
)
echo   启动完成。

echo.
echo [4/4] 重启 frontend —— 让 nginx 重新解析 api 主机名。
echo       （不做这一步，重建 api 后会出现 502：nginx 缓存了旧容器 IP）
%COMPOSE% restart frontend
if errorlevel 1 (
  echo   重启 frontend 失败（exit=%ERRORLEVEL%）。
  exit /b %ERRORLEVEL%
)

echo.
echo 等待 frontend 健康...
set /a _TRIES=0
:waitloop
set /a _TRIES+=1
for /f "delims=" %%s in ('docker inspect aima-ugc-frontend-1 --format "{{.State.Health.Status}}" 2^>nul') do set "HEALTH=%%s"
if /i "%HEALTH%"=="healthy" goto ready
if %_TRIES% GEQ 30 goto notready
timeout /t 2 /nobreak >nul
goto waitloop

:ready
echo   frontend 已健康。

echo.
echo === 服务状态 ===
%COMPOSE% ps --format "{{.Name}} | {{.Status}}"

echo.
echo === 访问地址 ===
echo   本机   : http://127.0.0.1:8080/
echo   局域网 : http://^<本机局域网 IP^>:8080/    ^(手机用这个^)
echo.
echo 完成。
exit /b 0

:notready
echo   警告：frontend 60 秒内未变为 healthy，请检查 docker logs aima-ugc-frontend-1
exit /b 1
