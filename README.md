# GetAppVersion

掃描已連接的 Android 裝置，取得 App 的 Display Name、Version Name、Version Code、Package Name，並為每台裝置輸出一份獨立的 csv 檔案。支援 Windows 10 / macOS / Ubuntu，會自動辨識平台並執行對應邏輯。

## 運作流程

1. 透過 `adb devices` 偵測所有已連接的 Android 裝置（可多台，同時平行處理）。
2. 依是否有帶 `--paths` 參數決定查詢方式：
   - 未帶 `--paths`（預設）：直接依內建的 App 清單（顯示名稱＋package name）逐一查詢已安裝版本。
   - 有帶 `--paths`：在指定的資料夾路徑下尋找所有 `.apk` 檔案，解析方式依本機是否有 `aapt2` 而不同，詳見下方「Display Name 如何解析」。
3. 每台裝置各自輸出一份 csv 檔案，檔名包含型號、序號與時間戳記。

## 前置需求

- Android 裝置需開啟「USB 偵錯」，並已授權本機電腦的 adb 存取。
- 本機需已安裝 [Android platform-tools](https://developer.android.com/tools/releases/platform-tools)（提供 `adb`），並加入系統 PATH，使 `adb devices` 可正常偵測到裝置。
- （可選）本機若安裝 Android SDK build-tools 並加入 PATH，可使用 `aapt2`（或 `aapt`），取得更準確的 App 顯示名稱，詳見下方「Display Name 如何解析」。

## 快速開始

接上裝置、確認前置需求都已滿足後，直接執行對應平台的啟動器即可，不需要另外安裝 Python——若本機尚未安裝 Python，啟動器會自動嘗試安裝（Windows 透過 `winget`，macOS 透過 Homebrew，Ubuntu 透過 `apt-get`，Ubuntu 安裝過程需要 sudo 權限會提示輸入密碼）；若自動安裝失敗，會印出手動安裝指示並中止執行。

**Windows 10**
```
run.bat
```

**macOS / Ubuntu**
```
./run.sh
```

執行完成後，輸出的 csv 檔案預設會出現在目前目錄下的 `output/` 資料夾中，內容格式請參考下方「輸出結果」。

## 進階用法（自訂參數）

`run.bat` / `run.sh` 會把收到的參數原封不動傳給核心腳本，例如 `run.bat --output C:\reports`。

| 參數 | 說明 | 預設值 |
| --- | --- | --- |
| `--paths` | 逗號分隔的裝置端資料夾路徑清單。**有帶此參數時**，改為掃描這些路徑下的所有 `.apk` 檔案（而非用內建 App 清單查詢） | 未帶時使用內建 App 清單查詢 |
| `--output` | 輸出 csv 檔案的資料夾 | `output/`（目前工作目錄下） |
| `--aapt2` | 手動指定 aapt2（或 aapt）執行檔路徑（僅在有帶 `--paths` 時生效） | 自動在 PATH 中偵測 |

範例：

```
# 預設：用內建 App 清單查詢已安裝版本
run.bat

# 改用資料夾掃描模式，指定多個掃描路徑
run.bat --paths /system/priv-app,/data/app

# 指定輸出資料夾
run.bat --output C:\reports\2026-09-21

# 資料夾掃描模式下手動指定 aapt2 路徑（本機有裝但未加入 PATH 時）
run.bat --paths /system/priv-app --aapt2 "C:\Android\build-tools\34.0.0\aapt2.exe"

# 組合多個參數
run.bat --paths /system/priv-app,/vendor/app --output C:\reports --aapt2 "C:\Android\build-tools\34.0.0\aapt2.exe"
```

macOS / Ubuntu 語法相同，把 `run.bat` 換成 `./run.sh` 即可，例如：

```
./run.sh --paths /system/priv-app,/data/app --output ~/reports/2026-09-21
```

## App 清單如何取得版本（預設模式）

未帶 `--paths` 時，腳本改用內建的 `DEFAULT_APPS` 清單（顯示名稱＋package name，直接寫在 `get_app_version.py` 裡），對每個 package name 執行 `adb shell dumpsys package <package>` 取得 Version Name/Code，並用 `adb shell pm path <package>` 取得已安裝的 apk 路徑。裝置上若未安裝該 package，Version Name/Code 與 File Path 會顯示 `N/A`（Display Name 仍照清單顯示，不受影響）。

## Display Name 如何解析（`--paths` 資料夾掃描模式）

腳本啟動時會自動偵測本機是否有 `aapt2`（或 `aapt`）可用，並在終端機明確印出目前使用哪一種模式：

- **本機有 aapt2/aapt**：對每個找到的 apk 執行 `aapt2 dump badging`，可直接取得真實的 App 顯示名稱、Package Name、Version Name/Code，不受該 apk 是否已安裝影響，準確度最高。
- **本機沒有 aapt2/aapt（純 adb fallback 模式）**：改用 `pm list packages -f` 與 `dumpsys package` 取得資訊。這個模式有兩個已知限制：
  1. 大多數 App 的顯示名稱是以資源 ID 形式儲存，純 adb 指令無法將其解析成文字，因此 Display Name 欄位會改用 Package Name 代替。
  2. 若某個 apk 是「split APK」（例如同一個 App 依 CPU 架構拆分出的子檔案，本身不是獨立套件），`pm list packages -f` 不會單獨列出它；此時腳本會嘗試依所在資料夾比對回主 package，Display Name 會標示為 `{package} [split: 檔名]`；若連資料夾都比對不到，則標示為 `[unknown split] 檔名`，Package Name 與 Version 顯示 `N/A`。

## 多裝置支援

透過 `adb devices` 自動偵測所有已連接裝置，最多同時以 5 個執行緒平行處理，每台裝置各自獨立輸出一份 csv，單一裝置失敗不會影響其他裝置。所有裝置處理完畢後，終端機會印出成功／失敗摘要。

## 輸出結果

**檔名規則**：`{型號}_{序號}_{YYYYMMdd}-{HHmmss}.csv`（型號、序號中的空白與特殊字元會自動轉換為底線，時間戳記為該檔案產出當下的本機時間）。

**檔案內容**：開頭為裝置資訊（純文字，非 CSV 欄位），接著空一行後是 App 清單的 CSV 表格（含表頭列）。範例：

```
Model: XXXXXX
Serial: XXXXXXXXXX
OS Version: 13
API Level: 33
APK Count: 2

Display Name,Version Name,Version Code,Package Name,File Path
LINE,12.3.1,1203100,jp.naver.line.android,/system/priv-app/LineApp/LineApp.apk
com.google.android.networkstack [split: NetworkStackGoogle-arm64_v8a.apk],16,361420000,com.google.android.networkstack,/system/priv-app/NetworkStackGoogle/NetworkStackGoogle-arm64_v8a.apk
```

CSV 表格部分以標準 CSV 格式輸出（欄位內含逗號/雙引號時會自動加上雙引號跳脫），可直接用 Excel 或其他 CSV 工具開啟；檔案以 UTF-8 with BOM 編碼儲存，避免 Excel 開啟中文/特殊字元時亂碼。

## 已知限制

- 內建 App 清單模式（預設）下，若裝置上未安裝清單中的某個 package，Version Name / Version Code / File Path 會顯示 `N/A`；清單本身為程式內寫死的內容，需要修改 `get_app_version.py` 的 `DEFAULT_APPS` 才能增減。
- 純 adb fallback 模式（`--paths` 掃描模式下未偵測到 aapt2）下，多數 App 的 Display Name 欄位會以 Package Name 代替（Android label 多為資源 ID，純 adb 指令無法解析成文字）。
- 純 adb fallback 模式下，apk 檔案存在但完全找不到對應已安裝套件時（非 split APK 的情況），Version Name / Version Code 會顯示 `N/A`。
- Python 自動安裝步驟依賴各平台套件管理器（winget / Homebrew / apt），若環境缺少這些工具或沒有安裝權限，需使用者手動安裝 Python 3。
