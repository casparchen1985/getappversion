#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT="${1:-$SCRIPT_DIR/GetAppVersion.zip}"

git -C "$SCRIPT_DIR" archive --format=zip --prefix=GetAppVersion/ -o "$OUTPUT" HEAD
echo "[GetAppVersion] 已產出 $OUTPUT"
