@echo off
REM Usage: run check ^| run next ^| run topic "EF Core N+1" --track sql ^| run file samples\sample-article.md --dry-run
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (echo Run setup.bat first. & pause & exit /b 1)
REM Double-click (no arguments) = run check and keep the window open
if "%~1"=="" (.venv\Scripts\python run.py check & pause & exit /b)
.venv\Scripts\python run.py %*
