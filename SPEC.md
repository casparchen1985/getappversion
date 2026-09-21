# GetVersionNames — 規格文件

## 背景與需求

在 Windows 10 / macOS / Ubuntu 三種平台上，自動辨識平台並執行對應邏輯，透過 adb 連接 Android 裝置，掃描裝置檔案系統中「指定資料夾路徑」下的所有 `.apk` 檔案，針對每一台裝置輸出一份獨立的 txt 純文字檔（以型號＋序號命名），內容包含每個 apk 的 Display Name、Package Name、Version Name (Version Code)。

## 設計決策

1. **技術棧**：核心邏輯以 Python 3 單一腳本撰寫（跨平台通用）。因「腳本執行環境可能沒有 Python」的雞生蛋問題，另外用兩個極簡原生 bootstrap 啟動器（`run.bat` for Windows、`run.sh` for macOS/Ubuntu）負責：偵測 Python 是否存在 → 若無則嘗試自動安裝 → 再呼叫核心 Python 腳本。
2. **掃描範圍**：掃描裝置檔案系統中「指定資料夾路徑」下的實體 `.apk` 檔案（非僅已安裝套件清單），路徑清單提供合理預設值，並可用 `--paths` 參數覆寫。
3. **Display Name 解析策略（混合式）**：腳本啟動時先偵測本機是否有 `aapt2`（或 `aapt`）可用：
   - **有**：直接對每個找到的 apk 執行 `aapt2 dump badging`，一次取得 Display Name（`application-label`）、Package Name、VersionName/VersionCode，準確且不受「是否已安裝」限制。
   - **沒有**：退回純 adb 模式（`pm list packages -f` + `dumpsys package`）。此模式下大多數 App 因 label 為資源 ID 無法解析成文字，Display Name 欄位會 fallback 顯示 Package Name（已知限制，非程式錯誤）。
4. **多裝置處理**：`adb devices` 自動偵測所有已連接裝置，用 ThreadPoolExecutor 最多同時 5 個執行緒平行處理，每台裝置各自獨立輸出一份 txt，單一裝置失敗不會讓整批中斷，最終列出成功/失敗摘要。
5. **Python 自動安裝**：需要系統層級安裝權限（Windows UAC / macOS 系統安裝權限 / Ubuntu sudo），無法保證在所有環境下都能全自動無互動完成；自動安裝失敗時會清楚提示手動安裝方式，不會假裝安裝成功後繼續執行。

## 檔案結構

| 檔案 | 說明 |
| --- | --- |
| `get_version_names.py` | 核心邏輯，唯一包含業務邏輯的檔案，三平台共用同一份 |
| `run.bat` | Windows 啟動器 |
| `run.sh` | macOS / Ubuntu 共用啟動器（用 `uname` 分辨 Darwin vs Linux 以選擇對應套件管理器） |
| `README.md` | 使用者導向的安裝與使用說明 |
| `SPEC.md` | 本文件，記錄需求與設計決策 |

## 已知限制

- 純 adb fallback 模式下，多數 App 的 Display Name 欄位會以 Package Name 代替（Android label 多為資源 ID，純 adb 指令無法解析成文字）。
- apk 檔案存在但尚未安裝於裝置上時，純 adb fallback 模式無法取得其 Version 資訊，欄位顯示 `N/A`。
- Python 自動安裝步驟依賴各平台套件管理器（winget / Homebrew / apt），若環境缺少這些工具或無安裝權限，需使用者手動安裝 Python 3。
- macOS / Ubuntu 版本因目前開發環境為 Windows，尚未在實機上驗證，僅完成 shell 語法檢查。

## 驗證方式

1. 靜態檢查：`python -m py_compile get_version_names.py`；`bash -n run.sh`。
2. 實機測試（需至少一台已開啟 USB 偵錯並 adb 已授權的 Android 裝置）：確認輸出 txt 內容與裝置「設定 > 應用程式」中看到的名稱/版本比對正確；分別測試有/無 aapt2 兩種情境；測試多裝置平行處理；測試 adb 未安裝與未連接裝置的錯誤情境。
3. Python 自動安裝（bootstrap）情境建議在乾淨環境（如未裝 Python 的 VM）另行驗證。
