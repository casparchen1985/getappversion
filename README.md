# GetVersionNames

掃描已連接的 Android 裝置，取得指定資料夾路徑下所有 APK 的 Display Name、Package Name、Version Name (Version Code)，並為每台裝置輸出一份獨立的 txt 檔案。

## 前置需求

- Android 裝置需開啟「USB 偵錯」，並已授權本機電腦的 adb 存取。
- 本機需已安裝 [Android platform-tools](https://developer.android.com/tools/releases/platform-tools)（提供 `adb`），並加入系統 PATH，使 `adb devices` 可正常偵測到裝置。
- （可選）本機若安裝 Android SDK build-tools 並加入 PATH，可使用 `aapt2`（或 `aapt`）取得更準確的 App 顯示名稱，詳見下方「Display Name 解析模式」。

## 執行方式

### Windows 10

```
run.bat
```

若本機尚未安裝 Python，腳本會嘗試透過 `winget` 自動安裝；若安裝失敗會印出手動安裝指示。

### macOS / Ubuntu

```
chmod +x run.sh
./run.sh
```

若本機尚未安裝 `python3`，腳本會嘗試自動安裝（macOS 透過 Homebrew，Ubuntu 透過 `apt-get`，Ubuntu 安裝過程需要 sudo 權限，會提示輸入密碼）；若安裝失敗會印出手動安裝指示。

## CLI 參數

可透過 `run.bat` / `run.sh` 直接傳遞給核心腳本，例如 `run.bat --output C:\reports`。

| 參數 | 說明 | 預設值 |
| --- | --- | --- |
| `--paths` | 逗號分隔的裝置端資料夾路徑清單，掃描這些路徑下的所有 `.apk` 檔案 | `/system/app,/system/priv-app,/system/product/app,/system/product/priv-app,/vendor/app,/data/app` |
| `--output` | 輸出 txt 檔案的資料夾 | `output/`（目前工作目錄下） |
| `--aapt2` | 手動指定 aapt2（或 aapt）執行檔路徑 | 自動在 PATH 中偵測 |

## Display Name 解析模式

腳本啟動時會自動偵測本機是否有 `aapt2`（或 `aapt`）可用：

- **有 aapt2/aapt**：直接對每個找到的 apk 執行 `aapt2 dump badging`，可取得真實的 App 顯示名稱（Display Name）、Package Name、Version Name/Code，不受該 apk 是否已安裝影響。
- **沒有 aapt2/aapt（純 adb fallback 模式）**：改用 `pm list packages -f` 與 `dumpsys package` 取得資訊。**已知限制**：大多數 App 的顯示名稱是以資源 ID 形式儲存，純 adb 指令無法將其解析成文字，因此 Display Name 欄位會以 Package Name 代替；若該 apk 檔案存在但尚未安裝於裝置上，Version 欄位會顯示 `N/A`。

腳本執行時會在終端機明確印出目前使用哪一種模式。

## 多裝置處理

透過 `adb devices` 自動偵測所有已連接裝置，最多同時以 5 個執行緒平行處理，每台裝置各自獨立輸出一份 txt，單一裝置失敗不會影響其他裝置。所有裝置處理完畢後，會印出成功／失敗摘要。

## 輸出格式

輸出檔名規則：`{型號}_{序號}.txt`（型號、序號中的空白與特殊字元會自動轉換為底線）。

每個檔案內容範例：

```
Model: XXXXXX
Serial: XXXXXXXXXX
APK Count: 2

Display Name: LINE
Package Name: jp.naver.line.android
Version: 12.3.1 (1203100)
Path: /data/app/~~xxxx/jp.naver.line.android-xxxx/base.apk

Display Name: com.example.app
Package Name: com.example.app
Version: N/A (N/A)
Path: /data/app/com.example.app-1/base.apk
```
