#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OS_NAME="$(uname -s)"

if command -v python3 >/dev/null 2>&1; then
    :
else
    echo "[GetAppVersion] 未偵測到 python3，嘗試自動安裝..."

    if [ "$OS_NAME" = "Darwin" ]; then
        if command -v brew >/dev/null 2>&1; then
            brew install python3
        else
            echo "[GetAppVersion] 找不到 Homebrew，無法自動安裝 Python。"
            echo "請手動至 https://www.python.org/downloads/ 下載並安裝 Python 3 後再重新執行本腳本。"
            exit 1
        fi
    elif [ "$OS_NAME" = "Linux" ]; then
        if command -v apt-get >/dev/null 2>&1; then
            sudo apt-get update && sudo apt-get install -y python3 python3-pip
        else
            echo "[GetAppVersion] 找不到 apt-get，無法自動安裝 Python。"
            echo "請手動安裝 Python 3 後再重新執行本腳本。"
            exit 1
        fi
    else
        echo "[GetAppVersion] 不支援的作業系統：$OS_NAME"
        exit 1
    fi

    if ! command -v python3 >/dev/null 2>&1; then
        echo "[GetAppVersion] 自動安裝 Python 失敗，請手動安裝 Python 3 後再重新執行本腳本。"
        exit 1
    fi
fi

python3 "$SCRIPT_DIR/get_app_version.py" "$@"
exit $?
