# GetAppVersion — 規格文件

## 背景與需求

在 Windows 10 / macOS / Ubuntu 三種平台上，自動辨識平台並執行對應邏輯，透過 adb 連接 Android 裝置，查詢 App 版本資訊，針對每一台裝置輸出一份獨立的 csv 檔案（檔名格式：`{型號}_{序號}_{YYYYMMdd}-{HHmmss}.csv`）。檔案開頭為裝置資訊（Model / Serial / OS Version / API Level / APK Count，純文字非 CSV 欄位），接著空一行後是 App 清單的 CSV 表格（表頭：Display Name、Version Name、Version Code、Package Name、File Path）。

查詢方式依是否帶 `--paths` 參數分兩種模式：未帶時用內建 App 清單直接查詢已安裝套件版本；有帶時掃描指定資料夾路徑下的實體 `.apk` 檔案。

## 設計決策

1. **技術棧**：核心邏輯以 Python 3 單一腳本撰寫（跨平台通用）。因「腳本執行環境可能沒有 Python」的雞生蛋問題，另外用兩個極簡原生 bootstrap 啟動器（`run.bat` for Windows、`run.sh` for macOS/Ubuntu）負責：偵測 Python 是否存在 → 若無則嘗試自動安裝 → 再呼叫核心 Python 腳本。
2. **查詢模式（依 `--paths` 是否提供切換）**：
   - **未帶 `--paths`（預設，App 清單模式）**：對內建的 `DEFAULT_APPS` 常數（`get_app_version.py` 中寫死的 42 組「顯示名稱、package name」，取自既有的 CipherLab 版本查詢 bat 腳本）逐一執行 `dumpsys package <package>` 取得 Version Name/Code，並用 `pm path <package>` 取得已安裝路徑；未安裝時 Version/File Path 顯示 `N/A`。不掃描檔案系統，不需要 aapt2。
   - **有帶 `--paths`（資料夾掃描模式）**：掃描裝置檔案系統中「指定資料夾路徑」下的實體 `.apk` 檔案（非僅已安裝套件清單），行為與先前版本相同（逗號分隔多個路徑）。
3. **Display Name 解析策略（僅資料夾掃描模式，混合式）**：腳本啟動時先偵測本機是否有 `aapt2`（或 `aapt`）可用：
   - **有**：直接對每個找到的 apk 執行 `aapt2 dump badging`，一次取得 Display Name（`application-label`）、Package Name、VersionName/VersionCode，準確且不受「是否已安裝」限制。
   - **沒有**：退回純 adb 模式（`pm list packages -f` + `dumpsys package`）。此模式下大多數 App 因 label 為資源 ID 無法解析成文字，Display Name 欄位會 fallback 顯示 Package Name（已知限制，非程式錯誤）。
4. **多裝置處理**：`adb devices` 自動偵測所有已連接裝置，用 ThreadPoolExecutor 最多同時 5 個執行緒平行處理，每台裝置各自獨立輸出一份 csv，單一裝置失敗不會讓整批中斷，最終列出成功/失敗摘要。
5. **輸出格式**：裝置資訊維持純文字標頭（非 CSV 欄位，避免跟 App 清單表格混在同一張表裡），App 清單部分用 Python `csv` 模組輸出標準 CSV（欄位含逗號/雙引號時自動跳脫），檔案以 `utf-8-sig`（UTF-8 with BOM）編碼寫入，避免 Excel 開啟含中文/特殊字元內容時亂碼。
6. **Python 自動安裝**：需要系統層級安裝權限（Windows UAC / macOS 系統安裝權限 / Ubuntu sudo），無法保證在所有環境下都能全自動無互動完成；自動安裝失敗時會清楚提示手動安裝方式，不會假裝安裝成功後繼續執行。

## 檔案結構

| 檔案 | 說明 |
| --- | --- |
| `get_app_version.py` | 核心邏輯，唯一包含業務邏輯的檔案，三平台共用同一份 |
| `run.bat` | Windows 啟動器 |
| `run.sh` | macOS / Ubuntu 共用啟動器（用 `uname` 分辨 Darwin vs Linux 以選擇對應套件管理器） |
| `README.md` | 使用者導向的安裝與使用說明 |
| `SPEC.md` | 本文件，記錄需求與設計決策 |

## 已知限制

- App 清單模式（預設）下，`DEFAULT_APPS` 清單為程式內寫死內容，需修改 `get_app_version.py` 才能增減查詢的 App；裝置上未安裝清單中的 package 時，Version/File Path 顯示 `N/A`。
- 純 adb fallback 模式下，多數 App 的 Display Name 欄位會以 Package Name 代替（Android label 多為資源 ID，純 adb 指令無法解析成文字）。
- 純 adb fallback 模式下，若 apk 是「split APK」（例如依 CPU 架構拆分的子檔案，`pm list packages -f` 不會單獨列出），會嘗試以所在資料夾比對回主 package，Display Name 標示為 `{package} [split: 檔名]`；連資料夾都比對不到時，標示為 `[unknown split] 檔名`，Package Name/Version 顯示 `N/A`。
- apk 檔案存在但完全找不到對應已安裝套件時，純 adb fallback 模式無法取得其 Version 資訊，欄位顯示 `N/A`。
- Python 自動安裝步驟依賴各平台套件管理器（winget / Homebrew / apt），若環境缺少這些工具或無安裝權限，需使用者手動安裝 Python 3。
- macOS 版本已於實機驗證可正常執行；Ubuntu 版本尚未在實機上驗證，僅完成 shell 語法檢查。

## 驗證方式

1. 靜態檢查：`python -m py_compile get_app_version.py`；`bash -n run.sh`。
2. 實機測試（需至少一台已開啟 USB 偵錯並 adb 已授權的 Android 裝置）：確認輸出 csv 內容與裝置「設定 > 應用程式」中看到的名稱/版本比對正確；分別測試預設 App 清單模式與 `--paths` 資料夾掃描模式（含有/無 aapt2 兩種情境）；測試多裝置平行處理；測試 adb 未安裝與未連接裝置的錯誤情境。
3. Python 自動安裝（bootstrap）情境建議在乾淨環境（如未裝 Python 的 VM）另行驗證。
