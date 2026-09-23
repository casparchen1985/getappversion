#!/usr/bin/env python3
"""Query per-device app version info from connected Android devices.

Default mode queries a built-in list of app package names directly.
When --paths is given, scans .apk files under those device-side folders instead.
"""

import argparse
import concurrent.futures
import csv
import io
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

DEFAULT_PATHS = [
    "/system/priv-app",
]

# Built-in (Display Name, Package Name) list used when --paths is not given.
DEFAULT_APPS = [
    ("A Demo", "sw.programme.demos"),
    ("ADC Client", "sw.application.adcclient"),
    ("AppLock", "sw.programme.applock"),
    ("App Management", "com.cipherlab.appmanagerservice.common"),
    ("BarcodeToSetting", "com.cipherlab.barcodetosetting"),
    ("BTPrtMate", "com.cipherlab.btprtmate"),
    ("Button Assignment", "sw.programme.buttonassignment"),
    ("CustomizeSetupWizard", "com.cipherlab.customizesetupwizard"),
    ("Cipherlab Assistant Service", "sw.programme.assistantservice"),
    ("Cipherlab Remote Control", "sw.programme.cipherlabremotecontrol"),
    ("CipherLab Network Assistant", "com.cipherlab.cipherLabnetworkassistant"),
    ("DeviceHealthDashboard", "sw.programme.devicehealth.dashboard"),
    ("EnDeCloud", "sw.programme.endecloud"),
    ("Enterprise Settings", "com.sw.enterprisekeypadmode"),
    ("Enterprise Service", "com.sw.enterprisesettingsservice"),
    ("EZCheck", "com.cipherlab.self_testing"),
    ("EZConfig", "sw.programme.ezconfig"),
    ("EZEdit", "sw.programme.ezedit"),
    ("HF RFID Configuration", "sw.programme.hf"),
    ("ImageToText", "com.cipherlab.imagetotext"),
    ("Image2Text Launcher", "com.cipherlab.image2textlauncher"),
    ("IntelliWorker", "sw.programme.intelliworker"),
    ("KeyMappingManager", "com.cipherlab.keymappingmanager"),
    ("LogGen", "com.cipherlab.loggen"),
    ("LaunchPad", "com.cipherlab.LaunchPad"),
    ("Ping", "sw.programme.cipherlabping"),
    ("Reader Service", "com.cipherlab.clbarcodeservice"),
    ("Reader Config", "sw.programme.readerconfig"),
    ("RFID Service", "com.cipherlab.rfidservice"),
    ("SAM Service", "com.cipherlab.clsamservice"),
    ("SDC Activation Tool", "com.sw.activationkeyhelper"),
    ("Signature Capture", "sw.programme.signature"),
    ("SIP Controller", "com.sw.android.sipcontroller"),
    ("SIP Controller Service", "com.sw.android.sipcontroller_service"),
    ("SmaPri", "com.cipherlab.smapri"),
    ("Software Trigger", "com.Cipherlab.SoftwareTrigger"),
    ("Software Trigger Service", "com.Cipherlab.SoftwareTrigger_Service"),
    ("Terminal Emulation Android for CipherLab", "sw.programme.te"),
    ("Velocity", "com.wavelink.velocity"),
    ("WMDS Agent", "sw.programme.wmdsagent"),
    ("WMDSInstaller", "sw.programme.wmdsinstaller"),
    ("Wireless INIT", "sw.programme.wirelessinit"),
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


def get_device_os_info(serial):
    build_number = adb_shell(serial, ["getprop", "ro.build.display.id"]).stdout.strip() or "N/A"
    os_version = adb_shell(serial, ["getprop", "ro.build.version.release"]).stdout.strip() or "N/A"
    api_level = adb_shell(serial, ["getprop", "ro.build.version.sdk"]).stdout.strip() or "N/A"
    return build_number, os_version, api_level


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


def get_apk_path(serial, package_name):
    result = adb_shell(serial, ["pm", "path", package_name])
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("package:"):
            return line[len("package:"):].strip()
    return "N/A"


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


def build_dir_map(pm_map):
    dir_map = {}
    for apk_path, package_name in pm_map.items():
        parent = str(Path(apk_path.replace("\\", "/")).parent)
        dir_map.setdefault(parent, package_name)
    return dir_map


def extract_via_adb_fallback(apk_path, pm_map, dir_map, serial):
    package_name = pm_map.get(apk_path)
    if package_name:
        version_name, version_code = parse_dumpsys_version(serial, package_name)
        return (
            package_name,
            package_name,
            version_name or "N/A",
            version_code or "N/A",
        )

    parent = str(Path(apk_path.replace("\\", "/")).parent)
    package_name = dir_map.get(parent)
    if package_name:
        version_name, version_code = parse_dumpsys_version(serial, package_name)
        display_name = f"{package_name} [split: {Path(apk_path).name}]"
        return (
            display_name,
            package_name,
            version_name or "N/A",
            version_code or "N/A",
        )

    return f"[unknown split] {Path(apk_path).name}", "N/A", "N/A", "N/A"


def render_csv_table(rows):
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["Display Name", "Version Name", "Version Code", "Package Name", "File Path"])
    writer.writerows(rows)
    return buf.getvalue()


def render_device_output(model, real_serial, build_number, os_version, api_level, entry_count, rows):
    header = [
        f"Model: {model}",
        f"Serial: {real_serial}",
        f"Build Number: {build_number}",
        f"OS Version: {os_version}",
        f"API Level: {api_level}",
        f"APK Count: {entry_count}",
    ]
    return "\n".join(header) + "\n\n" + render_csv_table(rows)


def process_device_by_app_list(serial, output_dir):
    model, real_serial = get_device_identity(serial)
    build_number, os_version, api_level = get_device_os_info(serial)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_file = output_dir / f"{model}_{real_serial}_{timestamp}.csv"

    rows = []
    for display_name, package_name in DEFAULT_APPS:
        version_name, version_code = parse_dumpsys_version(serial, package_name)
        apk_path = get_apk_path(serial, package_name)
        rows.append((display_name, version_name or "N/A", version_code or "N/A", package_name, apk_path))

    content = render_device_output(model, real_serial, build_number, os_version, api_level, len(DEFAULT_APPS), rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file.write_text(content, encoding="utf-8-sig")
    return serial, out_file, len(DEFAULT_APPS)


def process_device_by_paths(serial, paths, output_dir, tool_path, mode):
    model, real_serial = get_device_identity(serial)
    build_number, os_version, api_level = get_device_os_info(serial)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_file = output_dir / f"{model}_{real_serial}_{timestamp}.csv"

    apk_paths = find_apks(serial, paths)
    pm_map = {} if mode == "aapt2" else build_pm_map(serial)
    dir_map = {} if mode == "aapt2" else build_dir_map(pm_map)

    rows = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        for apk_path in apk_paths:
            info = None
            if mode == "aapt2":
                info = extract_via_aapt2(serial, apk_path, tool_path, tmp_dir)
            if info is None:
                info = extract_via_adb_fallback(apk_path, pm_map, dir_map, serial)
            display_name, package_name, version_name, version_code = info
            rows.append((display_name, version_name, version_code, package_name, apk_path))

    content = render_device_output(model, real_serial, build_number, os_version, api_level, len(apk_paths), rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file.write_text(content, encoding="utf-8-sig")
    return serial, out_file, len(apk_paths)


def run_pool(devices, submit_fn):
    successes = []
    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(submit_fn, serial): serial for serial in devices}
        for future in concurrent.futures.as_completed(futures):
            serial = futures[future]
            try:
                serial, out_file, count = future.result()
                successes.append((serial, out_file, count))
            except Exception as exc:
                failures.append((serial, str(exc)))
    return successes, failures


def main():
    parser = argparse.ArgumentParser(description="Export per-app version info per connected Android device.")
    parser.add_argument(
        "--paths",
        default=None,
        help="Comma-separated device-side folder paths to scan for .apk files. "
        "If omitted, queries the built-in app list by package name instead.",
    )
    parser.add_argument("--output", default="output", help="Output directory for the per-device txt files.")
    parser.add_argument("--aapt2", default=None, help="Explicit path to aapt2/aapt executable (only used with --paths).")
    args = parser.parse_args()

    check_adb()
    output_dir = Path(args.output)

    devices = list_devices()
    if not devices:
        print("未偵測到任何已連接的 Android 裝置。", file=sys.stderr)
        sys.exit(1)

    print(f"偵測到 {len(devices)} 台裝置：{', '.join(devices)}")

    if args.paths:
        paths = [p.strip() for p in args.paths.split(",") if p.strip()]
        tool_path = find_tool(args.aapt2)
        mode = "aapt2" if tool_path else "adb-fallback"
        if mode == "aapt2":
            print(f"偵測到 aapt2/aapt：{tool_path}，使用 aapt2 模式解析 Display Name。")
        else:
            print("未偵測到 aapt2/aapt，改用純 adb fallback 模式（多數 App 的 Display Name 將以 Package Name 顯示）。")
        print(f"已指定 --paths，掃描路徑：{', '.join(paths)}")
        successes, failures = run_pool(
            devices, lambda serial: process_device_by_paths(serial, paths, output_dir, tool_path, mode)
        )
    else:
        print(f"未指定 --paths，改用內建 App 清單查詢已安裝版本（共 {len(DEFAULT_APPS)} 筆）。")
        successes, failures = run_pool(devices, lambda serial: process_device_by_app_list(serial, output_dir))

    print("\n===== 執行結果摘要 =====")
    for serial, out_file, count in successes:
        print(f"[成功] {serial} -> {out_file} ({count} 個項目)")
    for serial, error in failures:
        print(f"[失敗] {serial} -> {error}")

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
