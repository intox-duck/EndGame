@echo off
REM Build Operator into a single Windows installer: Output\OperatorSetup.exe
REM Run this on Windows. Requires: uv (or a venv), and Inno Setup 6 (iscc on PATH).
setlocal

echo [1/3] Installing build deps...
where uv >nul 2>nul
if %ERRORLEVEL%==0 (
    uv pip install -e ".[desktop,dev]" pyinstaller
) else (
    call .venv\Scripts\activate.bat
    pip install -e ".[desktop,dev]" pyinstaller
)

echo [2/3] Building Operator.exe with PyInstaller...
where uv >nul 2>nul
if %ERRORLEVEL%==0 (
    uv run pyinstaller --noconfirm operator.spec
) else (
    pyinstaller --noconfirm operator.spec
)
if not exist dist\Operator.exe (
    echo ERROR: dist\Operator.exe was not produced. See the PyInstaller output above.
    exit /b 1
)

echo [3/3] Wrapping in an installer with Inno Setup...
where iscc >nul 2>nul
if %ERRORLEVEL%==0 (
    iscc installer.iss
    echo.
    echo Done: Output\OperatorSetup.exe
) else (
    echo Inno Setup ^(iscc^) not found on PATH.
    echo dist\Operator.exe is ready; install Inno Setup 6 and run: iscc installer.iss
)
endlocal
