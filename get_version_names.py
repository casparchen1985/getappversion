#!/usr/bin/env python3
"""Scan Android devices for APKs under given paths and export version info per device."""

import argparse
import concurrent.futures
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

DEFAULT_PATHS = [
    "/system/app",
    "/system/priv-app",
    "/system/product/app",
    "/system/product/priv-app",
    "/vendor/app",
    "/data/app",
]

MAX_WORKERS = 5


def run(cmd, timeout=30):
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace"
    )


def check_adb():
    if shutil.which("adb") is None:
        print("錯誤：找不到 adb，請確認已安裝 Android platform-tools 並加入 PATH。", file=sys.stderr)
        sys.exit(1)


def find_tool(explicit_path):
    if explicit_path:
        p = Path(explicit_path)
        return str(p) if p.exists() else None
    for name in ("aapt2", "aapt"):
        found = shutil.which(name)
        if found:
            return found
    return None


def list_devices():
    result = run(["adb", "devices", "-l"])
    devices = []
    for line in result.stdout.splitlines()[1:]:
        line = line.strip()
        if not line or "device" not in line.split():
            continue
        serial = line.split()[0]
        devices.append(serial)
    return devices


def sanitize(name):
    return re.sub(r'[\\/:*?"<>|\s]+', "_", name.strip()) or "unknown"


def adb_shell(serial, args, timeout=30):
    return run(["adb", "-s", serial, "shell"] + args, timeout=timeout)


def get_device_identity(serial):
    model = adb_shell(serial, ["getprop", "ro.product.model"]).stdout.strip() or "UnknownModel"
    real_serial = adb_shell(serial, ["getprop", "ro.serialno"]).stdout.strip() or serial
    return sanitize(model), sanitize(real_serial)


def find_apks(serial, paths):
    apk_paths = []
    for path in paths:
        result = adb_shell(serial, ["find", path, "-name", "*.apk"], timeout=60)
        if result.returncode != 0:
            continue
        for line in result.stdout.splitlines():
            line = line.strip()
            if line:
                apk_paths.append(line)
    return apk_paths


def build_pm_map(serial):
    result = adb_shell(serial, ["pm", "list", "packages", "-f"], timeout=30)
    mapping = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line.startswith("package:"):
            continue
        body = line[len("package:"):]
        if "=" not in body:
            continue
        apk_path, pkg_name = body.rsplit("=", 1)
        mapping[apk_path.strip()] = pkg_name.strip()
    return mapping


def parse_dumpsys_version(serial, package_name):
    result = adb_shell(serial, ["dumpsys", "package", package_name], timeout=30)
    version_name = None
    version_code = None
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("versionName="):
            version_name = line[len("versionName="):].strip()
        elif line.startswith("versionCode="):
            version_code = line.split("versionCode=", 1)[1].split()[0].strip()
    return version_name, version_code


def extract_via_aapt2(serial, apk_path, aapt2_path, tmp_dir):
    local_apk = Path(tmp_dir) / Path(apk_path).name
    pull = run(["adb", "-s", serial, "pull", apk_path, str(local_apk)], timeout=60)
    if pull.returncode != 0 or not local_apk.exists():
        return None
    try:
        badging = run([aapt2_path, "dump", "badging", str(local_apk)], timeout=30)
    finally:
        try:
            local_apk.unlink()
        except OSError:
            pass

    label_match = re.search(r"application-label:'([^']*)'", badging.stdout)
    pkg_match = re.search(
        r"package: name='([^']*)' versionCode='([^']*)' versionName='([^']*)'", badging.stdout
    )
    if not pkg_match:
        return None
    package_name, version_code, version_name = pkg_match.groups()
    display_name = label_match.group(1) if label_match else package_name
    return display_name, package_name, version_name, version_code


def extract_via_adb_fallback(apk_path, pm_map, serial):
    package_name = pm_map.get(apk_path)
    if not package_name:
        return apk_path, "N/A", "N/A", "N/A"
    version_name, version_code = parse_dumpsys_version(serial, package_name)
    return (
        package_name,
        package_name,
        version_name or "N/A",
        version_code or "N/A",
    )


def process_device(serial, paths, output_dir, tool_path, mode):
    model, real_serial = get_device_identity(serial)
    out_file = output_dir / f"{model}_{real_serial}.txt"

    apk_paths = find_apks(serial, paths)
    pm_map = {} if mode == "aapt2" else build_pm_map(serial)

    lines = [f"Model: {model}", f"Serial: {real_serial}", f"APK Count: {len(apk_paths)}", ""]

    with tempfile.TemporaryDirectory() as tmp_dir:
        for apk_path in apk_paths:
            info = None
            if mode == "aapt2":
                info = extract_via_aapt2(serial, apk_path, tool_path, tmp_dir)
            if info is None:
                info = extract_via_adb_fallback(apk_path, pm_map, serial)
            display_name, package_name, version_name, version_code = info
            lines.append(f"Display Name: {display_name}")
            lines.append(f"Package Name: {package_name}")
            lines.append(f"Version: {version_name} ({version_code})")
            lines.append(f"Path: {apk_path}")
            lines.append("")

    output_dir.mkdir(parents=True, exist_ok=True)
    out_file.write_text("\n".join(lines), encoding="utf-8")
    return serial, out_file, len(apk_paths)


def main():
    parser = argparse.ArgumentParser(description="Export APK version info per connected Android device.")
    parser.add_argument("--paths", default=",".join(DEFAULT_PATHS), help="Comma-separated device-side folder paths to scan.")
    parser.add_argument("--output", default="output", help="Output directory for the per-device txt files.")
    parser.add_argument("--aapt2", default=None, help="Explicit path to aapt2/aapt executable.")
    args = parser.parse_args()

    check_adb()
    paths = [p.strip() for p in args.paths.split(",") if p.strip()]
    output_dir = Path(args.output)

    devices = list_devices()
    if not devices:
        print("未偵測到任何已連接的 Android 裝置。", file=sys.stderr)
        sys.exit(1)

    tool_path = find_tool(args.aapt2)
    mode = "aapt2" if tool_path else "adb-fallback"
    if mode == "aapt2":
        print(f"偵測到 aapt2/aapt：{tool_path}，使用 aapt2 模式解析 Display Name。")
    else:
        print("未偵測到 aapt2/aapt，改用純 adb fallback 模式（多數 App 的 Display Name 將以 Package Name 顯示）。")

    print(f"偵測到 {len(devices)} 台裝置：{', '.join(devices)}")

    successes = []
    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_device, serial, paths, output_dir, tool_path, mode): serial
            for serial in devices
        }
        for future in concurrent.futures.as_completed(futures):
            serial = futures[future]
            try:
                serial, out_file, count = future.result()
                successes.append((serial, out_file, count))
            except Exception as exc:
                failures.append((serial, str(exc)))

    print("\n===== 執行結果摘要 =====")
    for serial, out_file, count in successes:
        print(f"[成功] {serial} -> {out_file} ({count} 個 apk)")
    for serial, error in failures:
        print(f"[失敗] {serial} -> {error}")

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
