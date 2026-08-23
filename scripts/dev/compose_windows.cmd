@echo off
setlocal

set "REPO_ROOT=%~dp0..\.."
pushd "%REPO_ROOT%" >nul
if errorlevel 1 exit /b 1

if not exist "env.production" (
    copy /Y "env.production.example" "env.production" >nul
    echo [ERROR] 已创建 env.production。请先填写本机需要的 TikHub/LLM/端口配置，然后重新运行本脚本。
    popd >nul
    exit /b 2
)

if "%~1"=="" (
    docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production up -d --build --wait
) else (
    docker compose -f compose.yaml -f compose.windows.yaml --env-file env.production %*
)
set "EXIT_CODE=%ERRORLEVEL%"

popd >nul
exit /b %EXIT_CODE%
