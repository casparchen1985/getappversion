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

echo [GetVersionNames] 未偵測到 Python，嘗試自動安裝...

where winget >nul 2>&1
if not %errorlevel%==0 (
    echo [GetVersionNames] 找不到 winget，無法自動安裝 Python。
    echo 請手動至 https://www.python.org/downloads/ 下載並安裝 Python 3 後再重新執行本腳本。
    exit /b 1
)

winget install -e --id Python.Python.3.12 --scope user --silent
if not %errorlevel%==0 (
    echo [GetVersionNames] 自動安裝 Python 失敗。
    echo 請手動至 https://www.python.org/downloads/ 下載並安裝 Python 3 後再重新執行本腳本。
    exit /b 1
)

where python >nul 2>&1
if not %errorlevel%==0 (
    echo [GetVersionNames] Python 已安裝，但尚未出現在目前的 PATH 中，請重新開啟終端機後再執行本腳本。
    exit /b 1
)

:run
if defined PYCMD (
    %PYCMD% "%~dp0get_version_names.py" %*
) else (
    python "%~dp0get_version_names.py" %*
)
exit /b %errorlevel%
