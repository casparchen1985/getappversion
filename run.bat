@echo off
setlocal
chcp 65001 >nul

where python >nul 2>&1
if %errorlevel%==0 goto :run

py -3 --version >nul 2>&1
if %errorlevel%==0 (
    set "PYCMD=py -3"
    goto :run
)

echo [GetAppVersion] Python not found. Trying to install it automatically...

where winget >nul 2>&1
if not %errorlevel%==0 (
    echo [GetAppVersion] winget not found. Cannot install Python automatically.
    echo Please install Python 3 manually from https://www.python.org/downloads/ and run this script again.
    exit /b 1
)

winget install -e --id Python.Python.3.12 --scope user --silent
if not %errorlevel%==0 (
    echo [GetAppVersion] Automatic Python installation failed.
    echo Please install Python 3 manually from https://www.python.org/downloads/ and run this script again.
    exit /b 1
)

where python >nul 2>&1
if not %errorlevel%==0 (
    echo [GetAppVersion] Python was installed but is not yet on PATH. Please reopen your terminal and run this script again.
    exit /b 1
)

:run
if defined PYCMD (
    %PYCMD% "%~dp0get_app_version.py" %*
) else (
    python "%~dp0get_app_version.py" %*
)
exit /b %errorlevel%
