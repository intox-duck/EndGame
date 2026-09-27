@echo off
REM Operator setup for Windows. Creates a venv, installs deps, copies config.
setlocal

where uv >nul 2>nul
if %ERRORLEVEL%==0 (
    echo Using uv...
    uv venv
    uv pip install -e ".[desktop,dev]"
) else (
    echo uv not found; using python -m venv + pip...
    py -3.11 -m venv .venv 2>nul || python -m venv .venv
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -e ".[desktop,dev]"
)

if not exist config.toml (
    copy config.example.toml config.toml
    echo Created config.toml from example - edit it before running.
)
if not exist .env (
    copy .env.example .env
    echo Created .env from example - add your credentials.
)

echo.
echo Setup complete.
echo   1) Edit config.toml and .env
echo   2) Run the Windows tests:  uv run pytest -m windows
echo   3) Launch:                 run.bat
endlocal
