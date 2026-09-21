@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
if "%~1"=="" (
    set "OUTPUT=%SCRIPT_DIR%GetAppVersion.zip"
) else (
    set "OUTPUT=%~1"
)

git -C "%SCRIPT_DIR%" archive --format=zip --prefix=GetAppVersion/ -o "%OUTPUT%" HEAD
echo [GetAppVersion] 已產出 %OUTPUT%
