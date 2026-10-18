@echo off
REM One-time setup on Windows: creates .venv, installs packages, creates .env
cd /d "%~dp0"
REM Prefer 3.11-3.14: brand-new Pythons (3.15) have no prebuilt PyYAML/Pillow wheels and need a C compiler
set PY=
for %%v in (3.14 3.13 3.12 3.11) do if not defined PY (py -%%v -c "" >nul 2>nul && set PY=py -%%v)
if not defined PY where python >nul 2>nul && set PY=python
if not defined PY (echo Python not found. Install Python 3.13 from python.org and tick "Add to PATH". & pause & exit /b 1)
if not exist .venv %PY% -m venv .venv
call .venv\Scripts\python -m pip install --upgrade pip >nul
call .venv\Scripts\python -m pip install -r requirements.txt || (pause & exit /b 1)
if not exist .env copy .env.example .env >nul
if not exist .github\workflows mkdir .github\workflows
if not exist .github\workflows\autopilot.yml copy ci\autopilot.yml .github\workflows\autopilot.yml >nul
echo.
echo Setup done. Now open .env in Notepad, paste your keys, save, then run:
echo     run check
echo.
pause
