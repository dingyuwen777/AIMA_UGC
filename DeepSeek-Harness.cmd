REM agent-skills:deepseek-harness:start
@echo off
cd /d "%~dp0"
call dsh web --patch "%~dp0.dsh\agent-skills.cordis.yml"
exit /b %ERRORLEVEL%
REM agent-skills:deepseek-harness:end
