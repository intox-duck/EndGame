@echo off
REM Launch Operator.
setlocal
where uv >nul 2>nul
if %ERRORLEVEL%==0 (
    uv run operator %*
) else (
    call .venv\Scripts\activate.bat
    operator %*
)
endlocal
